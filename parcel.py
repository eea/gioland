import os
from cgi import escape
import flask
import blinker
from werkzeug.utils import secure_filename
from datetime import datetime
from path import path
from dateutil import tz
from definitions import (METADATA_FIELDS, STAGES, STAGE_ORDER,
                         INITIAL_STAGE, COUNTRIES, THEMES,
                         PROJECTIONS, RESOLUTIONS, EXTENTS)
import notification
import auth
from warehouse import get_warehouse


parcel_views = flask.Blueprint('parcel', __name__)

parcel_signals = blinker.Namespace()
parcel_created = parcel_signals.signal('parcel-created')
file_uploaded = parcel_signals.signal('file-uploaded')
parcel_finalized = parcel_signals.signal('parcel-finalized')
parcel_deleted = parcel_signals.signal('parcel-deleted')
parcel_file_deleted = parcel_signals.signal('parcel-file-deleted')

@parcel_views.route('/')
def index():
    return flask.render_template('index.html')


@parcel_views.route('/overview')
def overview():
    wh = get_warehouse()
    filter_arguments = {k:v for k,v in flask.request.args.items() \
                        if k in METADATA_FIELDS and v }
    parcels = filter_parcels(chain_tails(wh), **filter_arguments)
    return flask.render_template('overview.html', **{
        'parcels': parcels,
    })


@parcel_views.route('/country/<string:code>')
def country(code):
    wh = get_warehouse()
    all_parcels = [p for p in chain_tails(wh)
                   if p.metadata['country'] == code]
    return flask.render_template('country.html', **{
        'code': code,
        'all_parcels': all_parcels,
    })


@parcel_views.route('/parcel/new', methods=['GET', 'POST'])
def new():
    if flask.request.method == 'POST':
        if not authorize_for_parcel(None):
            return flask.abort(403)

        wh = get_warehouse()
        form = flask.request.form.to_dict()
        metadata = {k: form.get(k, '') for k in METADATA_FIELDS}
        metadata['stage'] = INITIAL_STAGE
        parcel = wh.new_parcel()
        parcel.save_metadata(metadata)
        add_history_item_and_notify(
            parcel, "New upload", datetime.utcnow(), flask.g.username, "")
        parcel_created.send(parcel)
        url = flask.url_for('parcel.view', name=parcel.name)
        return flask.redirect(url)

    else:
        return flask.render_template('parcel_new.html')


@parcel_views.route('/parcel/<string:name>/file', methods=['POST'])
def upload(name):
    posted_file = flask.request.files['file']
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    stage = STAGES[parcel.metadata['stage']]
    if not authorize_for_parcel(parcel):
        return flask.abort(403)
    if not parcel.uploading:
        flask.abort(403)
    if stage.get('last'):
        return flask.abort(403)

    filename = secure_filename(posted_file.filename)
    file_path = flask.safe_join(parcel.get_path(), filename)
    if file_path.exists():
        flask.flash("File %s already exists." % filename, 'system')
    else:
        if posted_file:
            posted_file.save(file_path)
            file_uploaded.send(parcel, filename=filename)
        else:
            flask.flash("Please upload a valid file", 'system')
    return flask.redirect(flask.url_for('parcel.view', name=name))


@parcel_views.route('/parcel/<string:name>/finalize', methods=['GET', 'POST'])
def finalize(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    stage = STAGES[parcel.metadata['stage']]
    if not authorize_for_parcel(parcel):
        return flask.abort(403)
    if stage.get('last'):
        return flask.abort(403)

    reject = bool(flask.request.values.get('reject'))

    if flask.request.method == "POST":
        finalize_parcel(wh, parcel, reject)
        url = flask.url_for('parcel.view', name=parcel.name)
        return flask.redirect(url)

    else:
        return flask.render_template("parcel_confirm_finalize.html",
                                     reject=reject)


@parcel_views.route('/parcel/<string:name>')
def view(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    return flask.render_template('parcel.html', parcel=parcel)


@parcel_views.route('/parcel/<string:name>/download/<string:filename>')
def download(name, filename):
    from werkzeug.security import safe_join
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    file_path = safe_join(parcel.get_path(), filename)
    if not path(file_path).isfile():
        flask.abort(404)
    return flask.send_file(file_path,
                           as_attachment=True,
                           attachment_filename=filename)


@parcel_views.route('/parcel/<string:name>/delete', methods=['GET', 'POST'])
def delete(name):
    wh = get_warehouse()
    app = flask.current_app
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)

    if not app.config['ALLOW_PARCEL_DELETION']:
        flask.abort(403)
    if not auth.authorize(['ROLE_ADMIN']):
        return flask.abort(403)

    if flask.request.method == 'POST':
        delete_parcel_chain(wh, parcel.name)
        flask.flash("Parcel %s was deleted." % name, 'system')
        return flask.redirect(flask.url_for('parcel.index'))
    else:
        return flask.render_template('parcel_delete.html', parcel=parcel)


@parcel_views.route('/parcel/<string:name>/file/<string:filename>/delete',
                    methods=['GET', 'POST'])
def delete_file(name, filename):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)

    if not authorize_for_parcel(parcel):
        flask.abort(403)
    if not parcel.uploading:
        flask.abort(403)

    if flask.request.method == 'POST':
        filename = secure_filename(filename)
        file_path = flask.safe_join(parcel.get_path(), filename)
        try:
            os.unlink(file_path)
            parcel_file_deleted.send(parcel)
            flask.flash("File %s was deleted." % name, 'system')
        except OSError:
            flask.flash("File %s was not deleted." % name, 'system')
        return flask.redirect(flask.url_for('parcel.view', name=name))
    else:
        return flask.render_template('parcel_file_delete.html',
                                     parcel=parcel,
                                     filename=filename)


@parcel_views.route('/parcel/<string:name>/comment', methods=['POST'])
def comment(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    if not flask.g.username:
        return flask.abort(403)

    comment = flask.request.form.get("comment", "").strip()
    if comment:
        add_history_item_and_notify(
            parcel, "Comment", datetime.utcnow(),
            flask.g.username, escape(comment))
    return flask.redirect(flask.url_for('parcel.view', name=name))


def delete_parcel_chain(wh, name):
    parcels = set()
    for p in walk_parcels(wh, name):
        parcels.add(p)
    for p in walk_parcels(wh, name, metadata_key='prev_parcel'):
        parcels.add(p)
    for p in parcels:
        wh.delete_parcel(p.name)
        parcel_deleted.send(p)


def walk_parcels(wh, name, metadata_key='next_parcel'):
    while True:
        parcel = wh.get_parcel(name)
        yield parcel
        name = parcel.metadata.get(metadata_key)
        if name is None:
            return


def add_history_item_and_notify(parcel, *args, **kwargs):
    item = parcel.add_history_item(*args, **kwargs)
    notification.notify(item)


@parcel_views.route('/parcel/<string:name>/chain')
def chain(name):
    wh = get_warehouse()
    first_parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)

    previous_parcels = list(walk_parcels(wh, name, 'prev_parcel'))
    if len(previous_parcels) > 1:
        first_parcel = previous_parcels[-1]
        url = flask.url_for('parcel.chain', name=first_parcel.name)
        return flask.redirect(url)

    workflow_parcels = list(walk_parcels(wh, name))
    return flask.render_template('parcel_chain.html', **{
        'first_parcel': first_parcel,
        'workflow_parcels': workflow_parcels,
    })


@parcel_views.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    if flask.request.method == 'POST':
        filters = {}
        for name in ['country', 'extent', 'projection',
                     'resolution', 'theme']:
            value = flask.request.form.get(name, '')
            if value:
                filters[name] = value
        notification.subscribe(flask.g.username, filters)
        flask.flash("Subscription was successful.", 'system')
        return flask.redirect(flask.url_for('parcel.index'))

    return flask.render_template('subscribe.html')


def get_or_404(func, *args, **kwargs):
    exc = kwargs.pop('_exc')
    try:
        return func(*args, **kwargs)
    except exc:
        flask.abort(404)


def chain_tails(wh):
    for parcel in wh.get_all_parcels():
        if 'next_parcel' not in parcel.metadata:
            yield parcel


def filter_parcels(parcels, **kwargs):
    for p in parcels:
        if all(p.metadata.get(k) == v for k, v in kwargs.items()):
            yield p


def authorize_for_parcel(parcel):
    stage = INITIAL_STAGE if parcel is None else parcel.metadata['stage']
    return auth.authorize(STAGES[stage]['roles'] + ['ROLE_ADMIN'])


def date(value, format):
    """ Formats a date according to the given format. """
    timezone = flask.current_app.config.get("TIME_ZONE")
    if timezone:
        from_zone = tz.gettz("UTC")
        to_zone = tz.gettz(timezone)
        # Tell the datetime object that it's in UTC time zone since
        # datetime objects are 'naive' by default
        value = value.replace(tzinfo=from_zone)
        # Convert time zone
        value = value.astimezone(to_zone)
    return value.strftime(format)


def finalize_parcel(wh, parcel, reject):
    parcel.finalize()
    stage = parcel.metadata['stage']
    if reject and not STAGES[stage].get('reject'):
        flask.abort(403)

    if reject:
        next_stage = STAGE_ORDER[STAGE_ORDER.index(stage) - 1]
    else:
        next_stage = STAGE_ORDER[STAGE_ORDER.index(stage) + 1]

    next_parcel = wh.new_parcel()
    next_parcel.save_metadata({
        'prev_parcel': parcel.name,
        'stage': next_stage,
    })
    next_parcel.save_metadata({k: parcel.metadata.get(k, '')
                               for k in METADATA_FIELDS})
    parcel.save_metadata({'next_parcel': next_parcel.name})

    next_url = flask.url_for('parcel.view', name=next_parcel.name)
    description_html = '<p>Next step: <a href="%s">%s</a></p>' % (
        next_url, STAGES[next_parcel.metadata['stage']]['label'])

    title = "Finalized (rejected)" if reject else "Finalized"
    add_history_item_and_notify(
        parcel, title, datetime.utcnow(),
        flask.g.username, description_html)

    prev_url = flask.url_for('parcel.view', name=parcel.name)
    next_description_html = '<p>Previous step: <a href="%s">%s</a></p>' % (
        prev_url, STAGES[parcel.metadata['stage']]['label'])
    add_history_item_and_notify(
        next_parcel, "Next stage", datetime.utcnow(),
        flask.g.username, next_description_html)

    parcel_finalized.send(parcel, next_parcel=next_parcel)


def register_on(app):
    app.register_blueprint(parcel_views)
    app.context_processor(lambda: metadata_template_context)
    app.context_processor(lambda: {
        'authorize': auth.authorize,
        'authorize_for_parcel': authorize_for_parcel,
        'can_subscribe_to_notifications': notification.can_subscribe,
    })
    app.jinja_env.filters["date"] = date


metadata_template_context = {
    'STAGES': STAGES,
    'STAGE_MAP': {k: STAGES[k]['label'] for k in STAGES},
    'COUNTRIES': COUNTRIES,
    'COUNTRY_MAP': dict(COUNTRIES),
    'THEMES': THEMES,
    'THEME_MAP': dict(THEMES),
    'RESOLUTIONS': RESOLUTIONS,
    'RESOLUTION_MAP': dict(RESOLUTIONS),
    'PROJECTIONS': PROJECTIONS,
    'PROJECTION_MAP': dict(PROJECTIONS),
    'EXTENTS': EXTENTS,
    'EXTENT_MAP': dict(EXTENTS),
}

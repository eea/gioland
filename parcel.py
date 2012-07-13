import flask
import blinker
from datetime import datetime
import transaction
from path import path
from dateutil import tz
from definitions import (METADATA_FIELDS, STAGES, STAGE_ORDER, INITIAL_STAGE,
                         STAGE_ROLES, COUNTRIES, THEMES, PROJECTIONS,
                         RESOLUTIONS, EXTENTS)
import notification


parcel_views = flask.Blueprint('parcel', __name__)

parcel_signals = blinker.Namespace()
parcel_created = parcel_signals.signal('parcel-created')
file_uploaded = parcel_signals.signal('file-uploaded')
parcel_finalized = parcel_signals.signal('parcel-finalized')
parcel_deleted = parcel_signals.signal('parcel-deleted')


@parcel_views.route('/')
def index():
    return flask.render_template('index.html')


@parcel_views.route('/overview')
def overview():
    with warehouse() as wh:
        all_parcels = [p for p in chain_tails(wh)]
        return flask.render_template('overview.html', **{
            'all_parcels': all_parcels,
        })


@parcel_views.route('/country/<string:code>')
def country(code):
    with warehouse() as wh:
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

        with warehouse() as wh:
            form = flask.request.form.to_dict()
            metadata = {k: form.get(k, '') for k in METADATA_FIELDS}
            metadata['stage'] = INITIAL_STAGE
            parcel = wh.new_parcel()
            parcel.save_metadata(metadata)
            add_history_item_and_notify(
                parcel, "New upload", datetime.utcnow(), flask.g.username, "")
            parcel_created.send(parcel)
            transaction.commit()
            url = flask.url_for('parcel.view', name=parcel.name)
            return flask.redirect(url)

    else:
        return flask.render_template('parcel_new.html')


@parcel_views.route('/parcel/<string:name>/file', methods=['POST'])
def upload(name):
    posted_file = flask.request.files['file']
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        if not authorize_for_parcel(parcel):
            return flask.abort(403)
        if not parcel.uploading:
            flask.abort(403)
        # TODO make sure filename is safe and within the folder
        filename = posted_file.filename.rsplit('/', 1)[-1]
        posted_file.save(parcel.get_path() / filename)
        file_uploaded.send(parcel, filename=filename)
        return flask.redirect(flask.url_for('parcel.view', name=name))


@parcel_views.route('/parcel/<string:name>/finalize', methods=['POST'])
def finalize(name):
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        if not authorize_for_parcel(parcel):
            return flask.abort(403)
        parcel.finalize()
        stage = parcel.metadata['stage']
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
            next_url, dict(STAGES)[next_parcel.metadata['stage']])
        add_history_item_and_notify(
            parcel, "Finalized", datetime.utcnow(),
            flask.g.username, description_html)

        prev_url = flask.url_for('parcel.view', name=parcel.name)
        next_description_html = '<p>Previous step: <a href="%s">%s</a></p>' % (
            prev_url, dict(STAGES)[parcel.metadata['stage']])
        add_history_item_and_notify(
            next_parcel, "Next stage", datetime.utcnow(),
            flask.g.username, next_description_html)

        parcel_finalized.send(parcel, next_parcel=next_parcel)

        transaction.commit()
        return flask.redirect(flask.url_for('parcel.view', name=parcel.name))


@parcel_views.route('/parcel/<string:name>')
def view(name):
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        return flask.render_template('parcel.html', parcel=parcel)


@parcel_views.route('/parcel/<string:name>/download/<string:filename>')
def download(name, filename):
    from werkzeug.security import safe_join
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        file_path = safe_join(parcel.get_path(), filename)
        if not path(file_path).isfile():
            flask.abort(404)
    return flask.send_file(file_path,
                           as_attachment=True,
                           attachment_filename=filename)


@parcel_views.route('/parcel/<string:name>/delete', methods=['GET', 'POST'])
def delete(name):
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        if not authorize(['ROLE_ADMIN']):
            return flask.abort(403)
        if flask.request.method == 'POST':
            wh.delete_parcel(name)
            parcel_deleted.send(parcel)
            transaction.commit()
            flask.flash("Parcel %s was deleted." % name, 'system')
            return flask.redirect(flask.url_for('parcel.index'))
        else:
            return flask.render_template('parcel_delete.html', name=name)


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
    with warehouse() as wh:
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


def warehouse():
    return flask.current_app.extensions['warehouse_connector'].warehouse()


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


def authorize(role_names):
    config = flask.current_app.config
    return any(flask.g.username in config.get(role_name, [])
               for role_name in role_names)


def authorize_for_parcel(parcel):
    stage = INITIAL_STAGE if parcel is None else parcel.metadata['stage']
    return authorize(STAGE_ROLES[stage] + ['ROLE_ADMIN'])


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


def register_on(app):
    app.register_blueprint(parcel_views)
    app.context_processor(lambda: metadata_template_context)
    app.context_processor(lambda: {
        'authorize': authorize,
        'authorize_for_parcel': authorize_for_parcel,
    })
    app.jinja_env.filters["date"] = date


metadata_template_context = {
    'STAGES': STAGES,
    'STAGE_MAP': dict(STAGES),
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

import os
import re
import tempfile

from cgi import escape
from itertools import groupby
from datetime import datetime

import flask
import blinker

from werkzeug.utils import secure_filename
from werkzeug.security import safe_join

from path import path

import notification
import auth
from definitions import (
    EDITABLE_METADATA, METADATA, STAGES, STAGE_ORDER, INITIAL_STAGE, COUNTRIES_MC,
    COUNTRIES_CC, COUNTRIES, THEMES, THEMES_FILTER, THEMES_IDS, PROJECTIONS,
    RESOLUTIONS, EXTENTS, ALL_ROLES, UNS_FIELD_DEFS, CATEGORIES, REPORT_METADATA,
    DOCUMENTS)
from warehouse import get_warehouse, _current_user
from utils import format_datetime, exclusive_lock


parcel_views = flask.Blueprint('parcel', __name__)

parcel_signals = blinker.Namespace()
parcel_created = parcel_signals.signal('parcel-created')
report_created = parcel_signals.signal('report-created')
file_uploaded = parcel_signals.signal('file-uploaded')
parcel_finalized = parcel_signals.signal('parcel-finalized')
parcel_deleted = parcel_signals.signal('parcel-deleted')
parcel_file_deleted = parcel_signals.signal('parcel-file-deleted')


@parcel_views.route('/')
def index():
    return flask.render_template('index.html')


def get_filter_arguments():
    return {k: v for k, v in flask.request.args.items()
            if k in METADATA and v}


@parcel_views.route('/search')
def search():
    wh = get_warehouse()
    filter_arguments = get_filter_arguments()
    all_reports = []
    if 'country' in filter_arguments:
        all_reports = [r for r in wh.get_all_reports()
                       if r.country == filter_arguments['country']]
    parcels = list(filter_parcels(chain_tails(wh), **filter_arguments))
    parcels.sort(key=lambda p: p.last_modified, reverse=True)
    return flask.render_template('search.html', **{
        'parcels': parcels,
        'all_reports': all_reports,
    })


@parcel_views.route('/api/find_parcels')
def api_find_parcels():
    wh = get_warehouse()
    parcels = filter_parcels(wh.get_all_parcels(), **get_filter_arguments())
    return flask.jsonify({
        'parcels': [p.name for p in parcels],
    })


@parcel_views.route('/api/parcel/<string:name>')
def parcel_metadata(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    return flask.jsonify({'metadata': dict(parcel.metadata)})


@parcel_views.route('/country/<string:code>')
def country(code):
    wh = get_warehouse()
    all_parcels = [p for p in chain_tails(wh)
                   if p.metadata['country'] == code]
    all_reports = [r for r in wh.get_all_reports()
                   if r.country == code]
    grouped_parcels = group_parcels(all_parcels)
    return flask.render_template('country.html', **{
        'code': code,
        'grouped_parcels': grouped_parcels,
        'all_reports': all_reports,
    })


@parcel_views.route('/parcel/new', methods=['GET', 'POST'])
def new():
    if flask.request.method == 'POST':
        if not authorize_for_parcel(None):
            return flask.abort(403)

        wh = get_warehouse()
        form = flask.request.form.to_dict()
        if form['extent'] == 'full':
            form['coverage'] = ''

        metadata = {k: form.get(k, '') for k in EDITABLE_METADATA}
        metadata['stage'] = INITIAL_STAGE
        data_map = zip(
            ['country', 'theme', 'projection', 'resolution', 'extent', 'stage'],
            [COUNTRIES, THEMES, PROJECTIONS, RESOLUTIONS, EXTENTS, STAGES])
        if not validate_metadata(metadata, data_map):
            flask.abort(400)

        parcel = wh.new_parcel()
        parcel.save_metadata(metadata)
        parcel.add_history_item("New upload", datetime.utcnow(),
                                flask.g.username, "")
        parcel_created.send(parcel)
        url = flask.url_for('parcel.view', name=parcel.name)
        return flask.redirect(url)

    else:
        return flask.render_template('parcel_new.html')


@parcel_views.route('/parcel/<string:name>/chunk', methods=['POST'])
def upload(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    form = flask.request.form.to_dict()

    if not authorize_for_upload(parcel):
        flask.abort(403)

    identifier = form['resumableIdentifier']
    chunk_number = int(form['resumableChunkNumber'])

    parcel_path = parcel.get_path()
    temp = parcel_path.joinpath(identifier)
    if not os.path.isdir(temp):
        os.makedirs(temp)
    filename = secure_filename(form['resumableFilename'])
    if parcel_path.joinpath(filename).exists():
        return "File already exists", 415

    posted_file = flask.request.files['file']
    tmp_file = tempfile.NamedTemporaryFile(dir=temp, delete=False)
    tmp = path(tmp_file.name)
    tmp_file.close()
    posted_file.save(tmp)

    with exclusive_lock():
        chunk_path = temp.joinpath('%s_%s' % (chunk_number, identifier))
        wh.logger.info("Begin chunked upload file %r for parcel %r (user %s)",
                       filename, parcel.name, _current_user())
        tmp.rename(chunk_path)

    return flask.jsonify({'status': 'success'})


@parcel_views.route('/parcel/<string:name>/chunk')
@exclusive_lock
def check_chunk(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)

    if not authorize_for_upload(parcel):
        flask.abort(403)

    form = flask.request.args.to_dict()
    chunk_number = form['resumableChunkNumber']
    chunk_size = int(form['resumableChunkSize'])
    identifier = form['resumableIdentifier']

    temp = parcel.get_path().joinpath(identifier)
    chunk_path = temp.joinpath('%s_%s' % (chunk_number, identifier))

    if not chunk_path.exists():
        flask.abort(404)
    if not chunk_path.stat().st_size >= chunk_size:
        flask.abort(404)
    return flask.Response()


@parcel_views.route('/parcel/<string:name>/file', methods=['POST'])
@exclusive_lock
def upload_single_file(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)

    if not authorize_for_upload(parcel):
        flask.abort(403)

    posted_file = flask.request.files['file']

    filename = secure_filename(posted_file.filename)
    file_path = parcel.get_path().joinpath(filename)

    if file_path.exists():
        flask.flash("File %s already exists." % filename, 'system')
    else:
        if posted_file:
            posted_file.save(file_path)
            file_uploaded.send(parcel, filename=filename)
            wh.logger.info("Finished upload %r for parcel %r (user %s)",
                           filename, parcel.name, _current_user())
        else:
            flask.flash("Please upload a valid file", 'system')
    return flask.redirect(flask.url_for('parcel.view', name=name))


@parcel_views.route('/parcel/<string:name>/finalize_upload', methods=['POST'])
@exclusive_lock
def finalize_upload(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    response = {'status': 'success'}

    form = flask.request.form.to_dict()
    filename = secure_filename(form['resumableFilename'])
    identifier = form['resumableIdentifier']
    total_size = int(form['resumableTotalSize'])

    temp = parcel.get_path().joinpath(identifier)
    if all_chunks_uploaded(temp, total_size):
        create_file_from_chunks(parcel, temp, filename)
        wh.logger.info("Finished chunked upload %r for parcel %r (user %s)",
                       filename, parcel.name, _current_user())
    else:
        response['status'] = 'error'
        response['message'] = "Upload didn't finalize. an error occurred"
    return flask.jsonify(response)


@parcel_views.route('/parcel/<string:name>/files')
def files(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    app = flask.current_app

    if (parcel.uploading and parcel.file_uploading and
        authorize_for_parcel(parcel)):
        file_authorize = True
    else:
        file_authorize = False

    template = app.jinja_env.get_template('bits.html')
    return template.module.files_table(parcel, delete_buttons=file_authorize)


def all_chunks_uploaded(temp, total_size):
    pattern = re.compile('^\d+_')
    chunk_sizes = [f.stat().st_size for f in temp.listdir()
                   if pattern.match(f.name)]
    if sum(chunk_sizes) >= total_size:
        return True
    return False


def create_file_from_chunks(parcel, temp, filename):

    def read_chunk(f):
        while True:
            data = f.read(131072)
            if not data:
                break
            yield data

    def sorted_listdir(temp_path):
        name = lambda f: int(f.name.split('_')[0])
        return sorted(temp_path.listdir(), key=name)

    file_path = parcel.get_path().joinpath(filename)
    with open(file_path, 'wb') as original_file:
        for chunk_path in sorted_listdir(temp):
            with open(chunk_path, 'rb') as chunk_file:
                for chunk in read_chunk(chunk_file):
                    original_file.write(chunk)
    file_uploaded.send(parcel, filename=filename)
    temp.rmtree()


@parcel_views.route('/parcel/<string:name>/finalize', methods=['GET', 'POST'])
@exclusive_lock
def finalize(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    stage_def = STAGES[parcel.metadata['stage']]

    if not authorize_for_parcel(parcel):
        return flask.abort(403)
    if stage_def.get('last'):
        return flask.abort(403)
    if not parcel.uploading:
        return flask.abort(403)

    if stage_def.get('reject'):
        reject = bool(flask.request.values.get('reject'))
    else:
        reject = None
        if flask.request.values.get('reject'):
            flask.abort(403)

    if flask.request.method == "POST":
        if flask.request.form.get('merge') == 'on':
            finalize_and_merge_parcel(wh, parcel)
        else:
            finalize_parcel(wh, parcel, reject)
        url = flask.url_for('parcel.view', name=parcel.name)
        return flask.redirect(url)
    else:
        flask.abort(405)


@parcel_views.route('/parcel/<string:name>')
def view(name):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    return flask.render_template('parcel.html', parcel=parcel)


@parcel_views.route('/parcel/<string:name>/download/<string:filename>')
def download(name, filename):
    wh = get_warehouse()
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    file_path = safe_join(parcel.get_path(), filename)
    if not path(file_path).isfile():
        flask.abort(404)
    return flask.send_file(file_path,
                           as_attachment=True,
                           attachment_filename=filename)


@parcel_views.route('/parcel/<string:name>/delete', methods=['GET', 'POST'])
@exclusive_lock
def delete(name):
    wh = get_warehouse()
    app = flask.current_app
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)

    if not app.config['ALLOW_PARCEL_DELETION']:
        flask.abort(403)
    if not auth.authorize(['ROLE_ADMIN']):
        return flask.abort(403)

    if flask.request.method == 'POST':
        delete_parcel_and_followers(wh, parcel.name)
        flask.flash("Parcel %s was deleted." % name, 'system')
        return flask.redirect(flask.url_for('parcel.index'))

    else:
        will_remove = list(walk_parcels(wh, name))
        will_not_remove = list(walk_parcels(wh, name, forward=False))[1:]
        will_not_remove.reverse()
        return flask.render_template('parcel_delete.html', **{
            'parcel': parcel,
            'will_remove': will_remove,
            'will_not_remove': will_not_remove,
        })


@parcel_views.route('/parcel/<string:name>/file/<string:filename>/delete',
                    methods=['GET', 'POST'])
@exclusive_lock
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
        wh.logger.info("Delete file %r for parcel %r (user %s)",
                       filename, parcel.name, _current_user())
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
    comment = flask.request.form.get("comment", "").strip()
    if comment:
        add_history_item_and_notify(
            parcel, 'comment', "Comment", datetime.utcnow(),
            flask.g.username, escape(comment))
    return flask.redirect(flask.url_for('parcel.view', name=name))


def get_parcel_chain(wh, name):
    parcels = set()
    for p in walk_parcels(wh, name):
        parcels.add(p)
    for p in walk_parcels(wh, name, forward=False):
        parcels.add(p)
    return parcels


def delete_parcel_and_followers(wh, name):
    parcel = wh.get_parcel(name)
    for prev_name in parcel.metadata.get('prev_parcel_list', []):
        prev = wh.get_parcel(prev_name)
        del prev.metadata['upload_time'], prev.metadata['next_parcel']
        prev.add_history_item('Next step deleted',
                              datetime.utcnow(),
                              flask.g.username,
                              'Next step deleted (%s)' % name)
    for p in walk_parcels(wh, name):
        wh.delete_parcel(p.name)
        parcel_deleted.send(p)


def change_metadata(wh, name, new_meta):
    for p in get_parcel_chain(wh, name):
        p.save_metadata(new_meta)
        p.link_in_tree()


def walk_parcels(wh, name, forward=True):
    while True:
        parcel = wh.get_parcel(name)
        yield parcel
        if forward:
            name = parcel.metadata.get('next_parcel')
        else:
            values = parcel.metadata.get('prev_parcel_list', [])
            if not values or len(values) > 1:
                return
            name = values[0]
        if name is None:
            return


def get_parcels_by_stage(name):
    wh = get_warehouse()
    stages_with_parcels = dict([(stage, None) for stage in STAGES])
    for parcel in walk_parcels(wh, name, forward=False):
        stage = parcel.metadata['stage']
        if not stages_with_parcels[stage]:
            stages_with_parcels[stage] = parcel
    return stages_with_parcels


def add_history_item_and_notify(parcel, event_type,
                                title, time, actor, description_html,
                                rejected=None):
    item = parcel.add_history_item(title, time, actor, description_html)
    notification.notify(item, event_type, rejected)


@parcel_views.route('/parcel/<string:name>/chain')
def chain(name):
    wh = get_warehouse()
    first_parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)

    previous_parcels = list(walk_parcels(wh, name, forward=False))
    if len(previous_parcels) > 1:
        first_parcel = previous_parcels[-1]
        url = flask.url_for('parcel.chain', name=first_parcel.name)
        return flask.redirect(url)

    workflow_parcels = list(walk_parcels(wh, name))
    return flask.render_template('parcel_chain.html', **{
        'first_parcel': first_parcel,
        'workflow_parcels': workflow_parcels,
    })


def group_parcels(parcels):
    # order parcels based on THEMES order
    def sort_parcels_key(parcel):
        return THEMES_IDS.index(parcel.metadata['theme'])
    sorted_parcels = sorted(parcels, key=sort_parcels_key)
    return groupby(sorted_parcels, key=lambda p: p.metadata['theme'])


@parcel_views.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    if flask.request.method == 'POST':
        filters = {}
        for name in ['country', 'extent', 'projection', 'resolution', 'theme',
                     'decision', 'stage', 'event_type']:
            value = flask.request.form.get(name, '')
            if value:
                filters[name] = value
        notification.subscribe(flask.g.username, filters)
        flask.flash("Subscription was successful.", 'system')
        return flask.redirect(flask.url_for('parcel.index'))

    return flask.render_template('subscribe.html')


@parcel_views.route('/report/new', methods=['GET', 'POST'])
def new_report():
    if not authorize_for_cdr():
        return flask.abort(403)
    if flask.request.method == 'POST':
        wh = get_warehouse()
        form = flask.request.form.to_dict()
        metadata = {k: form.get(k, '') for k in REPORT_METADATA}
        data_map = zip(['country', 'category'], [COUNTRIES, CATEGORIES])
        if not validate_metadata(metadata, data_map):
            flask.abort(400)
        posted_file = flask.request.files.get('file')
        if posted_file and extension(posted_file.filename) in DOCUMENTS:
            report = wh.new_report(**metadata)
            save_report_file(reports_path=wh.reports_path,
                             posted_file=posted_file,
                             report=report)
            report_created.send(report)
            url = flask.url_for('parcel.country', code=report.country)
            return flask.redirect(url)
        else:
            flask.flash("File field is missing or it's not a document.", 'system')
    return flask.render_template('report_new.html')


@parcel_views.route('/report/<int:report_id>/download')
def download_report_file(report_id):
    wh = get_warehouse()
    report = get_or_404(wh.get_report, report_id, _exc=KeyError)
    file_path = safe_join(wh.reports_path, report.filename)
    if not path(file_path).isfile():
        flask.abort(404)
    return flask.send_file(file_path, as_attachment=True,
                           attachment_filename=report.filename)


@parcel_views.route('/report/<int:report_id>/delete', methods=['GET', 'POST'])
def delete_report(report_id):
    if not auth.authorize(['ROLE_ADMIN']):
        return flask.abort(403)
    wh = get_warehouse()
    report = get_or_404(wh.get_report, report_id, _exc=KeyError)
    country_code = report.country
    if flask.request.method == 'POST':
        file_path = safe_join(wh.reports_path, report.filename)
        if file_path.exists():
            file_path.unlink()
        wh.delete_report(report_id)
        flask.flash('Report was deleted.', 'system')
        url = flask.url_for('parcel.country', code=country_code)
        return flask.redirect(url)

    return flask.render_template('report_delete.html', report=report)


def save_report_file(reports_path, posted_file, report):
    # filename = 'CDR_%s_%s_V%s.%s' % (report.country.upper(), report.category.upper(),
    #     report.pk if report.pk >= 10 else '0%s' % report.pk,
    #     extension(posted_file.filename),
    # )
    filename = posted_file.filename
    file_path = reports_path / filename
    if file_path.exists():
        flask.flash("File %s already exists." % filename, 'system')
    else:
        posted_file.save(file_path)
    report.filename = filename


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
    return auth.authorize(STAGES[stage]['roles'])


def authorize_for_upload(parcel):
    stage = STAGES[parcel.metadata['stage']]
    if not authorize_for_parcel(parcel):
        return False
    if not parcel.uploading:
        return False
    if not parcel.file_uploading:
        return False
    if stage.get('last'):
        return False
    return True


def authorize_for_cdr():
    return auth.authorize(['ROLE_ADMIN', 'ROLE_SP'])


def clear_chunks(parcel_path):
    for d in parcel_path.dirs():
        d.rmtree()


def create_next_parcel(wh, parcels, next_stage, stage_def, next_stage_def):
    next_parcel = wh.new_parcel()
    next_parcel.save_metadata({
        'prev_parcel_list': [p.name for p in parcels],
        'stage': next_stage,
    })
    next_parcel.save_metadata({k: parcels[0].metadata.get(k, '')
                               for k in EDITABLE_METADATA})

    links = []
    for p in parcels:
        url = flask.url_for('.view', name=p.name)
        if p.metadata['extent'] == 'partial':
            links.append('<a href="%s">%s (%s)</a>' % (
                url, stage_def['label'], p.metadata['coverage']))
        else:
            links.append('<a href="%s">%s</a>' % (url, stage_def['label']))

    next_description_html = '<p>Previous step: %s</p>' % ', '.join(links)
    next_parcel.add_history_item('Ready for %s' % next_stage_def['label'],
                                 datetime.utcnow(),
                                 flask.g.username,
                                 next_description_html)
    return next_parcel


def close_prev_parcel(parcel, reject=False):
    parcel.finalize()
    clear_chunks(parcel.get_path())
    if reject:
        parcel.save_metadata({'rejection': 'true'})
    parcel.link_in_tree()


def link_to_next_parcel(next_parcel, parcel, stage_def, next_stage_def,
                        reject=False):
    next_url = flask.url_for('parcel.view', name=next_parcel.name)
    description_html = '<p>Next step: <a href="%s">%s</a></p>' % (
        next_url, next_stage_def['label'])

    parcel.save_metadata({'next_parcel': next_parcel.name})

    title = "%s finished" % stage_def['label']
    if reject:
        title += " (rejected)"

    add_history_item_and_notify(
        parcel, 'stage_finished', title, datetime.utcnow(),
        flask.g.username, description_html, rejected=reject)


def finalize_parcel(wh, parcel, reject):
    stage = parcel.metadata['stage']
    stage_def = STAGES[stage]

    if reject:
        next_stage = STAGE_ORDER[STAGE_ORDER.index(stage) - 1]
    else:
        next_stage = STAGE_ORDER[STAGE_ORDER.index(stage) + 1]
    next_stage_def = STAGES[next_stage]

    close_prev_parcel(parcel, reject)
    next_parcel = create_next_parcel(wh, [parcel], next_stage, stage_def,
                                     next_stage_def)
    link_to_next_parcel(next_parcel, parcel, stage_def, next_stage_def, reject)
    parcel_finalized.send(parcel, next_parcel=next_parcel)


def finalize_and_merge_parcel(wh, parcel):
    if parcel.metadata['extent'] != 'partial':
        flask.abort(400)

    def similar(parcel_item):
        return parcel_item.metadata == parcel.metadata
    partial_parcels = filter(similar, chain_tails(wh))

    stage = parcel.metadata['stage']
    stage_def = STAGES[stage]
    next_stage = STAGE_ORDER[STAGE_ORDER.index(stage) + 1]
    next_stage_def = STAGES[next_stage]

    for partial_parcel in partial_parcels:
        close_prev_parcel(partial_parcel)
    next_parcel = create_next_parcel(wh, partial_parcels, next_stage,
                                     stage_def, next_stage_def)
    next_parcel.save_metadata({'extent': 'full'})
    for partial_parcel in partial_parcels:
        link_to_next_parcel(next_parcel, partial_parcel, stage_def,
                            next_stage_def)


def validate_metadata(metadata, data_map):
    data_map = dict(data_map)
    for key, value in metadata.items():
        if key == 'coverage':
            if metadata['extent'] == 'partial' and not value:
                return False
            continue
        if value and value in dict(data_map[key]).keys():
            continue
        return False
    return True


def register_on(app):
    app.register_blueprint(parcel_views)
    app.context_processor(lambda: metadata_template_context)
    app.context_processor(lambda: {
        'authorize': auth.authorize,
        'authorize_for_parcel': authorize_for_parcel,
        'authorize_for_upload': authorize_for_upload,
        'authorize_for_cdr': authorize_for_cdr,
        'can_subscribe_to_notifications': notification.can_subscribe,
        'get_parcels_by_stage': get_parcels_by_stage,
    })
    app.jinja_env.filters["datetime"] = format_datetime


@parcel_views.before_request
def authorize_for_view():
    if flask.g.username is None:
        url = flask.request.url
        return flask.redirect(flask.url_for('auth.login', next=url))
    if not auth.authorize(ALL_ROLES):
        return flask.render_template('not_authorized.html')


# parse extension from FileStorage object
def extension(filename):
    return filename.rsplit('.', 1)[-1]


STAGES_PICKLIST = [(k, s['label']) for k, s in STAGES.items()]

metadata_template_context = {
    'STAGES': STAGES,
    'STAGES_PICKLIST': STAGES_PICKLIST,
    'STAGE_MAP': dict(STAGES_PICKLIST),
    'CATEGORIES': CATEGORIES,
    'CATEGORIES_MAP': dict(CATEGORIES),
    'COUNTRIES_MC': COUNTRIES_MC,
    'COUNTRIES_CC': COUNTRIES_CC,
    'COUNTRIES': COUNTRIES,
    'COUNTRY_MAP': dict(COUNTRIES),
    'THEMES': THEMES,
    'THEMES_FILTER': THEMES_FILTER,
    'THEME_MAP': dict(THEMES),
    'RESOLUTIONS': RESOLUTIONS,
    'RESOLUTION_MAP': dict(RESOLUTIONS),
    'PROJECTIONS': PROJECTIONS,
    'PROJECTION_MAP': dict(PROJECTIONS),
    'EXTENTS': EXTENTS,
    'EXTENT_MAP': dict(EXTENTS),
    'UNS_FIELD_DEFS': UNS_FIELD_DEFS,
}

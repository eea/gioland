import json
import os
import re
import tempfile

from cgi import escape
from itertools import groupby
from datetime import datetime

import flask
import blinker

from flask.views import MethodView
from werkzeug.utils import secure_filename
from werkzeug.security import safe_join

from path import path

import notification
import auth
from definitions import ALL_STAGES_MAP, ALL_ROLES, CATEGORIES, COUNTRIES
from definitions import COUNTRIES_CC, COUNTRIES_MC, COUNTRY_PRODUCTS, COUNTRY
from definitions import COUNTRY_LOT_PRODUCTS, DOCUMENTS, EDITABLE_METADATA
from definitions import EXTENTS, FULL_LOT_STAGES, FULL_LOT_STAGES_ORDER
from definitions import INITIAL_STAGE, LOT, LOTS, LOT_STAGES, METADATA, PARTIAL
from definitions import PARTIAL_LOT_STAGES, PARTIAL_LOT_STAGES_ORDER
from definitions import PRODUCTS, PRODUCTS_FILTER, PRODUCTS_IDS, REFERENCES
from definitions import REPORT_METADATA, RESOLUTIONS, SIMILAR_METADATA
from definitions import STAGE_ORDER, STAGES, STAGES_FOR_MERGING, STREAM
from definitions import STREAM_LOTS, STREAM_STAGES, STREAM_STAGES_ORDER
from definitions import UNS_FIELD_DEFS
from warehouse import get_warehouse, _current_user
from utils import format_datetime, exclusive_lock, isoformat_to_datetime
from forms import CountryDeliveryForm, LotDeliveryForm, StreamDeliveryForm
from forms import get_lot_products

parcel_views = flask.Blueprint('parcel', __name__)

parcel_signals = blinker.Namespace()
parcel_created = parcel_signals.signal('parcel-created')
report_created = parcel_signals.signal('report-created')
file_uploaded = parcel_signals.signal('file-uploaded')
parcel_finalized = parcel_signals.signal('parcel-finalized')
parcel_deleted = parcel_signals.signal('parcel-deleted')
parcel_file_deleted = parcel_signals.signal('parcel-file-deleted')


@parcel_views.route('/', defaults={'delivery': LOT})
@parcel_views.route('/<string:delivery>', endpoint='switch_delivery')
def index(delivery):
    return flask.render_template('index.html', **{'delivery': delivery})


def get_filter_arguments():
    return {k: v for k, v in flask.request.args.items()
            if k in METADATA and v}


@parcel_views.route('/search', defaults={'delivery_type': COUNTRY})
@parcel_views.route('/search/<string:delivery_type>')
def search(delivery_type):
    wh = get_warehouse()
    filter_arguments = get_filter_arguments()
    all_reports = []
    # right now the reports are showed only when a lot is selected
    if 'lot' in filter_arguments and delivery_type == LOT:
        all_reports = [r for r in wh.get_all_reports()
                       if r.lot == filter_arguments['lot']]
    parcels = list(filter_parcels(chain_tails(wh), **filter_arguments))
    parcels = [p for p in parcels
               if p.metadata.get('delivery_type', COUNTRY) == delivery_type]
    parcels.sort(key=lambda p: p.last_modified, reverse=True)
    return flask.render_template('search.html', **{
        'parcels': parcels,
        'all_reports': all_reports,
        'delivery_type': delivery_type,
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
    all_parcels = [p for p in chain_tails(wh) if
                   p.metadata['delivery_type'] == COUNTRY and
                   p.metadata['country'] == code]

    grouped_parcels = group_parcels(all_parcels)
    return flask.render_template('country.html', **{
        'code': code,
        'grouped_parcels': grouped_parcels,
    })


@parcel_views.route('/lot/<string:code>')
def lot(code):
    wh = get_warehouse()
    all_parcels = [p for p in chain_tails(wh) if
                   p.metadata['delivery_type'] == LOT and
                   p.metadata['lot'] == code]
    all_reports = [r for r in wh.get_all_reports()
                   if r.lot == code]

    grouped_parcels = group_parcels(all_parcels)
    return flask.render_template('lot.html', **{
        'code': code,
        'grouped_parcels': grouped_parcels,
        'all_reports': all_reports,
    })


@parcel_views.route('/stream/<string:code>')
def stream(code):
    wh = get_warehouse()
    all_parcels = [p for p in chain_tails(wh) if
                   p.metadata['delivery_type'] == STREAM and
                   p.metadata['lot'] == code]
    grouped_parcels = group_parcels(all_parcels)
    return flask.render_template('stream.html', **{
        'code': code,
        'grouped_parcels': grouped_parcels,
    })


class _BaseDelivery(MethodView):

    def get(self):
        form = getattr(self, 'form_class')()
        return flask.render_template(
            'parcel_new.html',
            form=form,
            delivery_type=getattr(self, 'delivery_type'))

    def post(self):
        if not authorize_for_parcel(None):
            return flask.abort(403)
        form = getattr(self, 'form_class')(flask.request.form)
        if form.validate():
            parcel = form.save()
            parcel_created.send(parcel)
            url = flask.url_for('parcel.view', name=parcel.name)
            return flask.redirect(url)
        flask.abort(400)


class CountryDelivery(_BaseDelivery):

    form_class = CountryDeliveryForm
    delivery_type = COUNTRY


class LotDelivery(_BaseDelivery):

    form_class = LotDeliveryForm
    delivery_type = LOT


class StreamDelivery(_BaseDelivery):

    form_class = StreamDeliveryForm
    delivery_type = STREAM

parcel_views.add_url_rule(
    '/parcel/new/country',
    view_func=CountryDelivery.as_view('country_delivery'))
parcel_views.add_url_rule(
    '/parcel/new/lot',
    view_func=LotDelivery.as_view('lot_delivery'))
parcel_views.add_url_rule(
    '/parcel/new/stream',
    view_func=StreamDelivery.as_view('stream_delivery'))


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


class Finalize(MethodView):

    decorators = (exclusive_lock,)

    def dispatch_request(self, name, *args, **kwargs):
        self.wh = get_warehouse()
        self.parcel = get_or_404(self.wh.get_parcel, name, _exc=KeyError)

        DELIVERY_STAGES, _ = _get_stages_for_parcel(self.parcel)
        if DELIVERY_STAGES:
            stage_def = DELIVERY_STAGES[self.parcel.metadata['stage']]
        else:
            flask.abort(400)

        if (not authorize_for_parcel(self.parcel) or stage_def.get('last') or
           not self.parcel.uploading):
            flask.abort(403)

        if stage_def.get('reject'):
            self.reject = bool(flask.request.values.get('reject'))
        else:
            self.reject = None
            if flask.request.values.get('reject'):
                flask.abort(403)
        return super(Finalize, self).dispatch_request(name, *args, **kwargs)

    def get(self, name):
        if not flask.request.args.get('merge') == 'on':
            flask.abort(405)
        partial_parcels = filter(lambda i: similar_parcel(self.parcel, i),
                                 chain_tails(self.wh))
        return flask.render_template('finalize_and_merge_parcel.html',
                                     parcel=self.parcel,
                                     partial_parcels=partial_parcels)

    def post(self, name):
        if flask.request.form.get('merge') == 'on':
            finalize_and_merge_parcel(self.wh, self.parcel)
        else:
            finalize_parcel(self.wh, self.parcel, self.reject)
        url = flask.url_for('parcel.view', name=self.parcel.name)
        return flask.redirect(url)


parcel_views.add_url_rule('/parcel/<string:name>/finalize',
                          view_func=Finalize.as_view('finalize'))


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
    parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
    DELIVERY_STAGES, _ = _get_stages_for_parcel(parcel)
    stages_with_parcels = {stage: None for stage in DELIVERY_STAGES}
    for parcel in walk_parcels(wh, name, forward=False):
        stage = parcel.metadata['stage']
        if not stages_with_parcels[stage]:
            stages_with_parcels[stage] = parcel
    prev_parcel_list = parcel.metadata.get('prev_parcel_list', [])
    if len(prev_parcel_list) > 1:
        prev_parcel = wh.get_parcel(prev_parcel_list[0])
        stages_with_parcels[prev_parcel.metadata['stage']] = \
            'Merged with %s other parcels.' % len(prev_parcel_list)
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
    prev_parcels = []
    if workflow_parcels:
        prev_parcel_list = workflow_parcels[0].metadata.get(
            'prev_parcel_list', [])
        if len(prev_parcel_list) > 1:
            prev_parcels = [wh.get_parcel(p) for p in prev_parcel_list]

    return flask.render_template('parcel_chain.html', **{
        'first_parcel': first_parcel,
        'workflow_parcels': workflow_parcels,
        'prev_parcels': prev_parcels,
    })


def group_parcels(parcels):
    # order parcels based on PRODUCTS order
    def sort_parcels_key(parcel):
        return PRODUCTS_IDS.index(parcel.metadata['product'])
    sorted_parcels = sorted(parcels, key=sort_parcels_key)
    return groupby(sorted_parcels, key=lambda p: p.metadata['product'])


@parcel_views.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    if flask.request.method == 'POST':
        filters = {}
        for name in ['country', 'lot', 'extent', 'resolution', 'product',
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
        data_map = zip(REPORT_METADATA,
                       [LOTS, COUNTRY_LOT_PRODUCTS.get(metadata['lot'], ())])
        if not validate_metadata(metadata, data_map):
            flask.abort(400)
        posted_file = flask.request.files.get('file')
        if posted_file and extension(posted_file.filename) in DOCUMENTS:
            report = wh.new_report(**metadata)
            save_report_file(reports_path=wh.reports_path,
                             posted_file=posted_file,
                             report=report)
            report_created.send(report)
            url = flask.url_for('parcel.lot', code=report.lot)
            return flask.redirect(url)
        else:
            flask.flash("File field is missing or it's not a document.",
                        'system')
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
    lot_code = report.lot
    if flask.request.method == 'POST':
        file_path = safe_join(wh.reports_path, report.filename)
        if file_path.exists():
            file_path.unlink()
        wh.delete_report(report_id)
        flask.flash('Report was deleted.', 'system')
        url = flask.url_for('parcel.lot', code=lot_code)
        return flask.redirect(url)

    return flask.render_template('report_delete.html', report=report)


def save_report_file(reports_path, posted_file, report):
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
    stage = INITIAL_STAGE[LOT] \
        if parcel is None else parcel.metadata['stage']
    DELIVERY_STAGES, _ = _get_stages_for_parcel(parcel)
    return auth.authorize(DELIVERY_STAGES[stage]['roles'])


def authorize_for_upload(parcel):

    DELIVERY_STAGES, _ = _get_stages_for_parcel(parcel)
    stage = DELIVERY_STAGES[parcel.metadata['stage']]
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
    metadata = {k: parcels[0].metadata.get(k, '') for k in EDITABLE_METADATA}
    metadata['delivery_type'] = parcels[0].metadata.get('delivery_type',
                                                        COUNTRY)
    next_parcel.save_metadata(metadata)

    links = []
    for p in parcels:
        url = flask.url_for('.view', name=p.name)
        if p.metadata['delivery_type'] == LOT and \
           p.metadata['extent'] == 'partial':
            links.append('<a href="%s">%s</a>' % (
                url, stage_def['label']))
        else:
            links.append('<a href="%s">%s</a>' % (url, stage_def['label']))
    next_description_html = '<p>Previous step: %s</p>' % ', '.join(links)
    next_parcel.add_history_item('Ready for %s' % next_stage_def['label'],
                                 datetime.utcnow(),
                                 flask.g.username,
                                 next_description_html)
    return next_parcel


def close_prev_parcel(parcel, reject=False, merged=False):
    parcel.finalize()
    clear_chunks(parcel.get_path())
    if reject:
        parcel.save_metadata({'rejection': 'true'})
    if merged:
        parcel.save_metadata({'merged': '1'})
    parcel.link_in_tree()


def copy_files_from_parcel(parcel_from, parcel_to):
    files = parcel_from.get_files()
    for f in files:
        f.copyfile(parcel_to.get_path() / f.name)


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


def similar_parcel(parcel, parcel_item):
    parcel_item_metadata = {k: parcel_item.metadata.get(k, '')
                            for k in SIMILAR_METADATA}
    parcel_metadata = {k: parcel.metadata.get(k, '')
                       for k in SIMILAR_METADATA}
    parcel_item_metadata['stage'] = parcel_item.metadata['stage']
    parcel_metadata['stage'] = parcel.metadata['stage']
    return parcel_item_metadata == parcel_metadata


def finalize_parcel(wh, parcel, reject):
    stages, stage_order = _get_stages_for_parcel(parcel)
    stage = parcel.metadata['stage']
    stage_def = stages[stage]
    if reject:
        reject_stage = stage_def.get('reject_stage', None)
        if reject_stage:
            next_stage = reject_stage
        else:
            next_stage = stage_order[stage_order.index(stage) - 1]
    else:
        next_stage = stage_order[stage_order.index(stage) + 1]
    next_stage_def = stages[next_stage]

    close_prev_parcel(parcel, reject)
    next_parcel = create_next_parcel(wh, [parcel], next_stage, stage_def,
                                     next_stage_def)

    DELIVERY_STAGES = _get_stages_for_parcel(parcel)
    if next_parcel.metadata['stage'] == DELIVERY_STAGES[-1]:
        try:
            [final_int_parcel_name] = parcel.metadata['prev_parcel_list']
            final_int_parcel = wh.get_parcel(final_int_parcel_name)
        except ValueError:
            final_int_parcel = None
        copy_files_from_parcel(final_int_parcel, next_parcel)

    link_to_next_parcel(next_parcel, parcel, stage_def, next_stage_def, reject)
    parcel_finalized.send(parcel, next_parcel=next_parcel)


def finalize_and_merge_parcel(wh, parcel):
    if parcel.metadata['delivery_type'] != LOT:
        flask.abort(400)
    if parcel.metadata['extent'] != 'partial':
        flask.abort(400)
    if parcel.metadata['stage'] not in STAGES_FOR_MERGING:
        flask.abort(400)

    partial_parcels = filter(lambda i: similar_parcel(parcel, i),
                             chain_tails(wh))
    if len(partial_parcels) <= 1:
        flask.abort(400)
    stage = parcel.metadata['stage']
    stage_def = STAGES[stage]
    next_stage = STAGE_ORDER[STAGE_ORDER.index(stage) + 1]
    next_stage_def = STAGES[next_stage]

    for partial_parcel in partial_parcels:
        close_prev_parcel(partial_parcel, merged=True)
    next_parcel = create_next_parcel(wh, partial_parcels, next_stage,
                                     stage_def, next_stage_def)
    next_parcel.save_metadata({'extent': 'full'})
    for partial_parcel in partial_parcels:
        link_to_next_parcel(next_parcel, partial_parcel, stage_def,
                            next_stage_def)


def validate_metadata(metadata, data_map):
    data_map = dict(data_map)
    for key, value in metadata.items():
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
        'get_stages_for_parcel': _get_stages_for_parcel,
    })
    app.jinja_env.filters["datetime"] = format_datetime
    app.jinja_env.filters["isoformat_to_datetime"] = isoformat_to_datetime


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


def _get_stages_for_parcel(parcel):
    if not parcel:
        return FULL_LOT_STAGES, FULL_LOT_STAGES_ORDER
    delivery_type = parcel.metadata.get('delivery_type', COUNTRY)
    if delivery_type == COUNTRY:
        return STAGES, STAGE_ORDER
    elif delivery_type == LOT:
        extent = parcel.metadata.get('extent', '')
        if extent == PARTIAL:
            return PARTIAL_LOT_STAGES, PARTIAL_LOT_STAGES_ORDER
        else:
            return FULL_LOT_STAGES, FULL_LOT_STAGES_ORDER
    elif delivery_type == STREAM:
        return STREAM_STAGES, STREAM_STAGES_ORDER
    flask.abort(400)


@parcel_views.route('/pick_products', methods=['GET'])
def pick_products():
    if flask.request.method == "GET":
        lot_id = flask.request.args.get('id', 'lot1')
        delivery_type = flask.request.args.get('delivery_type', 'lot')
        product = get_lot_products(lot_id, delivery_type)
        if product:
            return json.dumps(product)
    flask.abort(400)

STAGES_PICKLIST = [(k, s['label']) for k, s in STAGES.items()]
PARTIAL_LOT_STAGES_PICKLIST = [(k, s['label']) for k, s
                                in PARTIAL_LOT_STAGES.items()]
FULL_LOT_STAGES_PICKLIST = [(k, s['label']) for k, s in FULL_LOT_STAGES.items()]
STREAM_STAGES_PICKLIST = [(k, s['label']) for k, s in STREAM_STAGES.items()]

metadata_template_context = {
    'ALL_STAGES_MAP': ALL_STAGES_MAP,
    'STAGES': STAGES,
    'FULL_LOT_STAGES': FULL_LOT_STAGES,
    'PARTIAL_LOT_STAGES': PARTIAL_LOT_STAGES,
    'STAGES_PICKLIST': STAGES_PICKLIST,
    'FULL_LOT_STAGES_PICKLIST': FULL_LOT_STAGES_PICKLIST,
    'PARTIAL_LOT_STAGES_PICKLIST': PARTIAL_LOT_STAGES_PICKLIST,
    'LOT_STAGES': LOT_STAGES,
    'STREAM_STAGES': STREAM_STAGES,
    'STREAM_STAGES_PICKLIST': STREAM_STAGES_PICKLIST,
    'CATEGORIES': CATEGORIES,
    'CATEGORIES_MAP': dict(CATEGORIES),
    'COUNTRIES_MC': COUNTRIES_MC,
    'COUNTRIES_CC': COUNTRIES_CC,
    'COUNTRIES': COUNTRIES,
    'COUNTRY_MAP': dict(COUNTRIES),
    'COUNTRY_PRODUCTS': COUNTRY_PRODUCTS,
    'COUNTRY_PRODUCTS_MAP': dict(COUNTRY_PRODUCTS),
    'PRODUCTS': PRODUCTS,
    'PRODUCTS_FILTER': PRODUCTS_FILTER,
    'PRODUCT_MAP': dict(PRODUCTS),
    'RESOLUTIONS': RESOLUTIONS,
    'RESOLUTION_MAP': dict(RESOLUTIONS),
    'EXTENTS': EXTENTS,
    'EXTENT_MAP': dict(EXTENTS),
    'REFERENCES': REFERENCES,
    'REFERENCE_MAP': dict(REFERENCES),
    'UNS_FIELD_DEFS': UNS_FIELD_DEFS,
    'STAGES_FOR_MERGING': STAGES_FOR_MERGING,
    'COUNTRY': COUNTRY,
    'LOT': LOT,
    'STREAM': STREAM,
    'LOTS': LOTS,
    'STREAM_LOTS': STREAM_LOTS,
    'STREAM_LOTS_MAP': dict(STREAM_LOTS),
    'LOTS_MAP': dict(LOTS),
}

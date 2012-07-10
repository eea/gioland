import flask
import blinker
from datetime import datetime
import transaction
from path import path


parcel_views = flask.Blueprint('parcel', __name__)

parcel_signals = blinker.Namespace()
parcel_created = parcel_signals.signal('parcel-created')
file_uploaded = parcel_signals.signal('file-uploaded')
parcel_finalized = parcel_signals.signal('parcel-finalized')


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
        if not authorize():
            return flask.abort(403)

        with warehouse() as wh:
            form = flask.request.form.to_dict()
            metadata = {k: form.get(k, '') for k in METADATA_FIELDS}
            metadata['stage'] = INITIAL_STAGE
            metadata['user'] = flask.g.username or ''
            parcel = wh.new_parcel()
            parcel.save_metadata(metadata)
            parcel.add_history_item("New upload", datetime.utcnow(),
                                    flask.g.username, "")
            parcel_created.send(parcel)
            transaction.commit()
            url = flask.url_for('parcel.view', name=parcel.name)
            return flask.redirect(url)

    else:
        return flask.render_template('parcel_new.html')


@parcel_views.route('/parcel/<string:name>/file', methods=['POST'])
def upload(name):
    if not authorize():
        return flask.abort(403)
    posted_file = flask.request.files['file']
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        if not parcel.uploading:
            flask.abort(403)
        # TODO make sure filename is safe and within the folder
        filename = posted_file.filename.rsplit('/', 1)[-1]
        posted_file.save(parcel.get_path() / filename)
        file_uploaded.send(parcel, filename=filename)
        return flask.redirect(flask.url_for('parcel.view', name=name))


@parcel_views.route('/parcel/<string:name>/finalize', methods=['POST'])
def finalize(name):
    if not authorize():
        return flask.abort(403)
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
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
        parcel.add_history_item("Finalized", datetime.utcnow(),
                                flask.g.username, description_html)

        prev_url = flask.url_for('parcel.view', name=parcel.name)
        next_description_html = '<p>Previous step: <a href="%s">%s</a></p>' % (
            prev_url, dict(STAGES)[parcel.metadata['stage']])
        next_parcel.add_history_item("Next stage", datetime.utcnow(),
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
        get_or_404(wh.get_parcel, name, _exc=KeyError)
        if flask.request.method == 'POST':
            wh.delete_parcel(name)
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


def authorize(role_name='ROLE_SERVICE_PROVIDER'):
    role_user_ids = flask.current_app.config.get(role_name, [])
    return bool(flask.g.username in role_user_ids)


def register_on(app):
    app.register_blueprint(parcel_views)
    app.context_processor(lambda: metadata_template_context)
    app.context_processor(lambda: {'authorize': authorize})


METADATA_FIELDS = [
    'country',
    'theme',
    'projection',
    'resolution',
    'extent',
]


STAGES = [
    ('int', "Intermediate"),
    ('sch', "Semantic check"),
    ('ver', "Verification"),
    ('vch', "Verification check"),
    ('enh', "Enhancement"),
    ('ech', "Enhancement check"),
    ('fin', "Final integrated"),
    ('fva', "Final validated"),
]
STAGE_ORDER = [s[0] for s in STAGES]
INITIAL_STAGE = STAGE_ORDER[0]


COUNTRIES = [
    ('at', "Austria"),
    ('be', "Belgium"),
    ('bg', "Bulgaria"),
    ('cy', "Cyprus"),
    ('cz', "Czech Republic"),
    ('dk', "Denmark"),
    ('ee', "Estonia"),
    ('fi', "Finland"),
    ('fr', "France"),
    ('de', "Germany"),
    ('gr', "Greece"),
    ('hu', "Hungary"),
    ('is', "Iceland"),
    ('ie', "Ireland"),
    ('it', "Italy"),
    ('lv', "Latvia"),
    ('li', "Liechtenstein"),
    ('lt', "Lithuania"),
    ('lu', "Luxembourg"),
    ('mt', "Malta"),
    ('nl', "Netherlands"),
    ('no', "Norway"),
    ('pl', "Poland"),
    ('pt', "Portugal"),
    ('ro', "Romania"),
    ('sk', "Slovakia"),
    ('si', "Slovenia"),
    ('es', "Spain"),
    ('se', "Sweden"),
    ('ch', "Switzerland"),
    ('tr', "Turkey"),
    ('gb', "United Kingdom"),
]


THEMES = [
    ('imp-deg', "Imperviousness Degree"),
    ('imp-chg', "Imperviousness Change"),
    ('tcd',     "Tree Cover Density"),
    ('fty',     "Forest Type"),
    ('tnt',     "Tree / Non-tree"),
    ('tty',     "Tree Type"),
    ('grc',     "Grassland Cover"),
    ('grd',     "Grassland Density"),
    ('wet',     "Wetlands"),
    ('pwb',     "Permanent Water Bodies"),
]

PROJECTIONS = [
    ('ntl', "National"),
    ('eur', "European"),
]

RESOLUTIONS = [
    ('20m', "20m"),
    ('25m', "25m"),
    ('100m', "100m"),
]


EXTENTS = [
    ('full', "Full"),
    ('partial', "Partial"),
]


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

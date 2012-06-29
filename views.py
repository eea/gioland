import flask
import transaction
from path import path


METADATA_FIELDS = [
    'country',
    'theme',
    'projection',
    'resolution',
    'extent',
    'stage',
]

STAGES = [
    ('int', "Intermediate"),
    ('sch', "Semantic Check"),
    ('ver', "Verification"),
    ('vch', "Verification Check"),
    ('enh', "Enhancement"),
    ('ech', "Enhancement check"),
    ('fin', "Final Integrated"),
    ('fva', "Final Validated"),
]

STAGE_MAP = dict(STAGES)
STAGE_ORDER = [s[0] for s in STAGES]

INITIAL_STAGE = STAGE_ORDER[0]


views = flask.Blueprint('views', __name__)


def warehouse():
    return flask.current_app.extensions['warehouse_connector'].warehouse()


def get_or_404(func, *args, **kwargs):
    exc = kwargs.pop('_exc')
    try:
        return func(*args, **kwargs)
    except KeyError:
        flask.abort(404)


@views.before_request
def set_user():
    flask.g.username = flask.session.get('username', None)


@views.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.method == 'POST':
        flask.session['username'] = flask.request.form['username']
        return flask.redirect(flask.url_for('views.login'))
    return flask.render_template('login.html')


@views.route('/')
def index():
    with warehouse() as wh:
        return flask.render_template('index.html',
                                     all_parcels=wh.get_all_parcels())


@views.route('/parcel/new', methods=['GET', 'POST'])
def new_parcel():
    if flask.request.method == 'POST':
        with warehouse() as wh:
            form = flask.request.form.to_dict()
            metadata = {k: form.get(k, '') for k in METADATA_FIELDS}
            metadata['stage'] = INITIAL_STAGE
            metadata['user'] = flask.g.username or ''
            parcel = wh.new_parcel()
            parcel.save_metadata(metadata)
            transaction.commit()
            url = flask.url_for('views.parcel', name=parcel.name)
            return flask.redirect(url)

    else:
        return flask.render_template('new_parcel.html')


@views.route('/parcel/<string:name>/file', methods=['POST'])
def parcel_file(name):
    posted_file = flask.request.files['file']
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        if not parcel.uploading:
            flask.abort(403)
        # TODO make sure filename is safe and within the folder
        filename = posted_file.filename.rsplit('/', 1)[-1]
        posted_file.save(parcel.get_path()/filename)
        return flask.redirect(flask.url_for('views.parcel', name=name))


@views.route('/parcel/<string:name>/finalize', methods=['POST'])
def parcel_finalize(name):
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        parcel.finalize()
        next_stage = STAGE_ORDER[STAGE_ORDER.index(parcel.metadata['stage'])+1]
        next_parcel = wh.new_parcel()
        next_parcel.save_metadata({
            'prev_parcel': parcel.name,
            'stage': next_stage,
        })
        parcel.save_metadata({'next_parcel': next_parcel.name})
        transaction.commit()
        return flask.redirect(flask.url_for('views.parcel', name=parcel.name))


@views.route('/parcel/<string:name>')
def parcel(name):
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        return flask.render_template('parcel.html', parcel=parcel)


@views.route('/parcel/<string:name>/download/<string:filename>')
def parcel_download(name, filename):
    from werkzeug.security import safe_join
    with warehouse() as wh:
        parcel = get_or_404(wh.get_parcel, name, _exc=KeyError)
        file_path = safe_join(parcel.get_path(), filename)
        if not path(file_path).isfile():
            flask.abort(404)
    return flask.send_file(file_path,
                           as_attachment=True,
                           attachment_filename=filename)


def register_on(app):
    app.register_blueprint(views)

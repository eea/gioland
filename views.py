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

INITIAL_STAGE = 'intermediate'


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


@views.route('/upload', methods=['GET', 'POST'])
def new_upload():
    if flask.request.method == 'POST':
        with warehouse() as wh:
            form = flask.request.form.to_dict()
            metadata = {k: form.get(k, '') for k in METADATA_FIELDS}
            metadata['stage'] = INITIAL_STAGE
            metadata['user'] = flask.g.username or ''
            upload = wh.new_parcel()
            upload.save_metadata(metadata)
            transaction.commit()
            url = flask.url_for('views.upload', name=upload.name)
            return flask.redirect(url)

    else:
        return flask.render_template('new_upload.html')


@views.route('/upload/<string:name>')
def upload(name):
    with warehouse() as wh:
        upload = get_or_404(wh.get_upload, name, _exc=KeyError)
        return flask.render_template('upload.html', upload=upload)


@views.route('/upload/<string:name>/file', methods=['POST'])
def upload_file(name):
    posted_file = flask.request.files['file']
    with warehouse() as wh:
        upload = get_or_404(wh.get_upload, name, _exc=KeyError)
        # TODO make sure filename is safe and within the folder
        filename = posted_file.filename.rsplit('/', 1)[-1]
        posted_file.save(upload.get_path()/filename)
        return flask.redirect(flask.url_for('views.upload', name=name))


@views.route('/upload/<string:name>/finalize', methods=['POST'])
def upload_finalize(name):
    with warehouse() as wh:
        parcel = get_or_404(wh.get_upload, name, _exc=KeyError)
        parcel.finalize()
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

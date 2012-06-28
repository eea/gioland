import flask
import transaction


METADATA_FIELDS = [
    'country',
    'theme',
    'projection',
    'resolution',
    'extent',
    'stage',
]


views = flask.Blueprint('views', __name__)


def warehouse():
    return flask.current_app.extensions['warehouse_connector'].warehouse()


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
    return flask.render_template('index.html')


@views.route('/upload', methods=['GET', 'POST'])
def new_upload():
    if flask.request.method == 'POST':
        with warehouse() as wh:
            form = flask.request.form.to_dict()
            metadata = {k: form.get(k, '') for k in METADATA_FIELDS}
            upload = wh.new_upload()
            upload.save_metadata(metadata)
            transaction.commit()
            url = flask.url_for('views.upload', name=upload.name)
            return flask.redirect(url)

    else:
        return flask.render_template('new_upload.html')


@views.route('/upload/<string:name>')
def upload(name):
    with warehouse() as wh:
        upload = wh.get_upload(name)
        return flask.render_template('upload.html', upload=upload)


@views.route('/upload/<string:name>/file', methods=['POST'])
def upload_file(name):
    posted_file = flask.request.files['file']
    with warehouse() as wh:
        upload = wh.get_upload(name)
        # TODO make sure filename is safe and within the folder
        filename = posted_file.filename.rsplit('/', 1)[-1]
        posted_file.save(upload.get_path()/filename)
        return flask.redirect(flask.url_for('views.upload', name=name))


def register_on(app):
    app.register_blueprint(views)

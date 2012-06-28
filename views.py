import flask
import transaction


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
            upload = wh.new_upload()
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
    return flask.redirect(flask.url_for('views.upload', name=name))


def register_on(app):
    app.register_blueprint(views)

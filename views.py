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


@views.route('/upload', methods=['POST'])
def new_upload():
    with warehouse() as wh:
        upload = wh.new_upload()
        transaction.commit()
        return flask.redirect(flask.url_for('views.upload', name=upload.name))


@views.route('/upload/<string:name>')
def upload(name):
    with warehouse() as wh:
        upload = wh.get_upload(name)
        return flask.render_template('upload.html', upload=upload)


def register_on(app):
    app.register_blueprint(views)

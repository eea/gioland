import flask


auth_views = flask.Blueprint('auth', __name__)


def set_user():
    flask.g.username = flask.session.get('username', None)


@auth_views.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.method == 'POST':
        flask.session['username'] = flask.request.form['username']
        return flask.redirect(flask.url_for('auth.login'))
    return flask.render_template('login.html')


def register_on(app):
    app.register_blueprint(auth_views)
    app.before_request(set_user)

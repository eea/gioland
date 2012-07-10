import flask
import ldap


auth_views = flask.Blueprint('auth', __name__)


def set_user():
    flask.g.username = flask.session.get('username', None)


@auth_views.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.method == 'POST':
        form = flask.request.form

        if form['action'] == 'logout':
            del flask.session['username']
            flask.flash("Logged out.", 'system')
            return flask.redirect(flask.url_for('parcel.index'))

        elif form['action'] == 'login':
            if ldap_bind(form['username'], form['password']):
                flask.session['username'] = form['username']
                flask.flash("Login successful as %s" % form['username'],
                            'system')
                return flask.redirect(flask.url_for('parcel.index'))

            else:
                flask.flash("Login failed.", 'error')
                return flask.redirect(flask.url_for('auth.login'))

        else:
            return flask.abort(400)

    return flask.render_template('auth_login.html')


def ldap_bind(user_id, password):
    app = flask.current_app
    conn = ldap.initialize(app.config['LDAP_SERVER'])
    conn.protocol_version = ldap.VERSION3
    conn.timeout = app.config['LDAP_TIMEOUT']

    user_dn = app.config['LDAP_USER_DN_PATTERN'].format(user_id=user_id)
    try:
        result = conn.simple_bind_s(user_dn, password)
    except (ldap.INVALID_CREDENTIALS, ldap.UNWILLING_TO_PERFORM):
        return False
    assert result[:2] == (ldap.RES_BIND, [])
    return True


def register_on(app):
    app.register_blueprint(auth_views)
    app.before_request(set_user)

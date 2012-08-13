import urlparse
import flask
import ldap
from eea.usersdb import UsersDB
from utils import cached


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


@auth_views.route('/login/impersonate', methods=['POST'])
def impersonate():
    if not authorize(['ROLE_ADMIN']):
        flask.abort(403)
    user_id = flask.request.form['user_id']
    flask.current_app.logger.warn("User %r impersonating %r",
                                  flask.g.username, user_id)
    flask.session['username'] = user_id
    flask.flash("Login successful as %s" % user_id, 'system')
    return flask.redirect(flask.url_for('auth.login'))


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


def authorize(role_names):
    user_id = flask.g.username
    if user_id is None:
        return False
    config = flask.current_app.config

    def has_role(role_name):
        for principal in config.get(role_name, []):
            if principal == 'user_id:' + user_id:
                return True

            elif principal.startswith('ldap_group:'):
                group_name = principal[len('ldap_group:'):]
                if group_name in get_ldap_groups(user_id):
                    return True

        else:
            return False

    return any(has_role(role_name) for role_name in role_names)


def register_on(app):
    app.register_blueprint(auth_views)
    app.before_request(set_user)


@cached(timeout=5 * 60)
def get_ldap_groups(user_id):
    app = flask.current_app
    ldap_server = urlparse.urlsplit(app.config['LDAP_SERVER']).netloc
    udb = UsersDB(ldap_server=ldap_server)
    return [r for r, _info in udb.member_roles_info('user', user_id)]

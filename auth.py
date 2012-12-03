import urlparse
from functools import wraps
import flask
import ldap
from eea.usersdb import UsersDB
from utils import cached
from definitions import ALL_ROLES


auth_views = flask.Blueprint('auth', __name__)


def set_user():
    flask.g.username = flask.session.get('username', None)


@auth_views.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.method == 'POST':
        form = flask.request.form

        if form['action'] == 'logout':
            flask.session.pop('username', None)
            flask.flash("Logged out.", 'system')
            return flask.redirect(flask.url_for('parcel.index'))

        elif form['action'] == 'login':
            next = form['next'] or flask.url_for('parcel.index')
            ldapconn = LdapConnection(flask.current_app)
            user_id = form['username']
            if ldapconn.bind(user_id, form['password']):
                flask.session['username'] = user_id
                flask.flash("Login successful as %s" % ldap_full_name(user_id),
                            'system')
                return flask.redirect(next)

            else:
                flask.flash("Login failed.", 'error')
                return flask.redirect(flask.url_for('auth.login'))

        else:
            return flask.abort(400)
    else:
        next = flask.request.args.get('next', '')

    user_id = flask.g.username
    return flask.render_template('auth_login.html', **{
        'user_id': user_id,
        'full_name': ldap_full_name(user_id) if user_id else None,
        'next': next,
    })


@auth_views.route('/login/impersonate', methods=['POST'])
def impersonate():
    app = flask.current_app
    if not authorize(['ROLE_ADMIN']):
        flask.abort(403)
    user_id = flask.request.form['user_id']
    app.logger.warn("User %r impersonating %r", flask.g.username, user_id)
    flask.session['username'] = user_id
    flask.flash("Login successful as %s" % ldap_full_name(user_id), 'system')
    return flask.redirect(flask.url_for('auth.login'))


@cached(timeout=5 * 60)
def ldap_full_name(user_id):
    return LdapConnection(flask.current_app).get_user_name(user_id)


class LdapConnection(object):

    def __init__(self, app):
        ldap_server = app.config['LDAP_SERVER']
        if ldap_server is None:
            self.conn = None
        else:
            self.conn = ldap.initialize(ldap_server)
            self.conn.protocol_version = ldap.VERSION3
            self.conn.timeout = app.config['LDAP_TIMEOUT']
            self._user_dn_pattern = app.config['LDAP_USER_DN_PATTERN']

    def get_user_dn(self, user_id):
        return self._user_dn_pattern.format(user_id=user_id)

    def bind(self, user_id, password):
        if self.conn is None:
            return False
        user_dn = self.get_user_dn(user_id)
        try:
            result = self.conn.simple_bind_s(user_dn, password)
        except (ldap.INVALID_CREDENTIALS, ldap.UNWILLING_TO_PERFORM):
            return False
        assert result[:2] == (ldap.RES_BIND, [])
        return True

    def get_user_name(self, user_id):
        if self.conn is None:
            return u""
        user_dn = self.get_user_dn(user_id)
        result2 = self.conn.search_s(user_dn, ldap.SCOPE_BASE)
        [[_dn, attr]] = result2
        return attr['cn'][0].decode('utf-8')


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


def require_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not authorize(['ROLE_ADMIN']):
            url = flask.request.url
            return flask.redirect(flask.url_for('auth.login', next=url))
        return func(*args, **kwargs)
    return wrapper


@auth_views.route('/roles_debug')
@require_admin
def roles_debug():
    return flask.render_template('auth_roles_debug.html', ALL_ROLES=ALL_ROLES)


@auth_views.route('/logs')
@require_admin
def view_logs():
    import warehouse
    app = flask.current_app
    warehouse_log_file = app.config['WAREHOUSE_PATH'] / warehouse.LOG_FILE_NAME
    with warehouse_log_file.open('rb') as log_file:
        return flask.render_template('auth_logs.html', log_file=log_file)


def register_on(app):
    app.register_blueprint(auth_views)
    app.before_request(set_user)

    @app.context_processor
    def inject():
        return {
            'ldap_full_name': ldap_full_name,
        }


@cached(timeout=5 * 60)
def get_ldap_groups(user_id):
    app = flask.current_app
    ldap_server = urlparse.urlsplit(app.config['LDAP_SERVER']).netloc
    udb = UsersDB(ldap_server=ldap_server)
    return [r for r, _info in udb.member_roles_info('user', user_id)]

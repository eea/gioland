#!/usr/bin/env python

import os
import logging
import code
import copy
import flask
from flask.ext import script


default_config = {
    'LDAP_TIMEOUT': 10,
    'TIME_ZONE': 'Europe/Copenhagen',
    'BASE_URL': "",
    'UNS_CHANNEL_ID': 0,
    'UNS_SUPPRESS_NOTIFICATIONS': False,
    'ROLE_ADMIN': [],
    'CACHING': True,
    'ALLOW_PARCEL_DELETION': False,
    'LDAP_SERVER': None,
}


LOG_FORMAT = "[%(asctime)s] %(name)s %(levelname)s %(message)s"


def register_monitoring_views(app):
    import warehouse

    @app.route('/ping')
    def ping():
        warehouse.get_warehouse()
        return 'gioland is ok'

    @app.route('/crash')
    def crash():
        raise ValueError("Crashing as requested")


def create_app(config={}, testing=False):
    import auth
    import parcel
    import warehouse
    import utils
    app = flask.Flask(__name__)
    app.config.update(copy.deepcopy(default_config))
    if testing:
        app.config['TESTING'] = True
    else:
        app.config.update(configuration_from_environ())
    app.config.update(config)
    warehouse.initialize_app(app)
    auth.register_on(app)
    parcel.register_on(app)
    register_monitoring_views(app)
    utils.initialize_app(app)

    sentry_dsn = app.config.get('SENTRY_DSN')
    if sentry_dsn:
        from raven.conf import setup_logging
        from raven.handlers.logging import SentryHandler
        setup_logging(SentryHandler(sentry_dsn, level=logging.WARN))

    return app


class ReverseProxied(object):
    # working behind a reverse proxy (http://flask.pocoo.org/snippets/35/)

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme

        host = environ.get('HTTP_X_FORWARDED_HOST', '')
        if host:
            environ['HTTP_HOST'] = host

        return self.app(environ, start_response)


manager = script.Manager(create_app)


def configuration_from_environ():
    BOOL = lambda value: value == 'on'
    STR = lambda value: value
    STRLIST = lambda value: value.split()
    options = {
        'DEBUG': BOOL,
        'WAREHOUSE_PATH': STR,
        'LOCK_FILE_PATH': STR,
        'SENTRY_DSN': STR,
        'SECRET_KEY': STR,
        'ROLE_SP': STRLIST,
        'ROLE_ETC': STRLIST,
        'ROLE_NRC': STRLIST,
        'ROLE_ADMIN': STRLIST,
        'ROLE_VIEWER': STRLIST,
        'BASE_URL': STR,
        'UNS_CHANNEL_ID': STR,
        'UNS_LOGIN_USERNAME': STR,
        'UNS_LOGIN_PASSWORD': STR,
        'UNS_SUPPRESS_NOTIFICATIONS': BOOL,
        'LDAP_SERVER': STR,
        'LDAP_USER_DN_PATTERN': STR,
        'ALLOW_PARCEL_DELETION': BOOL,
    }
    config = {}
    for name, converter in options.items():
        if name in os.environ:
            config[name] = converter(os.environ[name])
    return config


class RunCherryPyCommand(script.Command):

    option_list = [
        script.Option('--port', '-p', dest='port', type=int),
    ]

    def handle(self, app, port):
        import cherrypy.wsgiserver
        listen = ('127.0.0.1', port)
        wsgi_app = ReverseProxied(app.wsgi_app)
        server = cherrypy.wsgiserver.CherryPyWSGIServer(listen, wsgi_app)
        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()


manager.add_command('runcherrypy', RunCherryPyCommand())


@manager.command
def shell(warehouse=False):
    def run():
        code.interact('', local=context)

    app = flask._request_ctx_stack.top.app
    context = {'app': app}

    if warehouse:
        import warehouse
        import transaction
        context['wh'] = warehouse.get_warehouse()
        context['transaction'] = transaction

    try:
        run()

    finally:
        if warehouse:
            transaction.abort()


@manager.command
def fsck():
    from warehouse import get_warehouse, checksum

    wh = get_warehouse()
    parcels = wh.get_all_parcels()

    for parcel in parcels:
        folder_path = parcel.get_path()
        files_checksum = checksum(folder_path)
        if not files_checksum == getattr(parcel, 'checksum', []):
            print "Checksum for parcel %r is wrong" % parcel.name
    print "Finished checking for parcel checksums"


@manager.command
def update_tree():
    from warehouse import get_warehouse
    wh = get_warehouse()
    parcels = [p for p in wh.get_all_parcels() if not p.uploading]
    parcels.sort(key=lambda p: p.metadata['upload_time'])
    for p in parcels:
        print p.name, (p.link_in_tree() or '[already linked]')


if __name__ == '__main__':
    stderr = logging.StreamHandler()
    stderr.setFormatter(logging.Formatter(LOG_FORMAT))
    stderr.setLevel(getattr(logging, os.environ.get('LOG_LEVEL', 'INFO')))
    logging.getLogger().addHandler(stderr)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('zc.lockfile').setLevel(logging.CRITICAL)
    manager.run()

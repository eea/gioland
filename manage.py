#!/usr/bin/env python

import os
import logging
import code
import copy
from path import path
import flask
import flaskext.script


default_config = {
    'LDAP_TIMEOUT': 10,
    'TIME_ZONE': 'Europe/Copenhagen',
    'BASE_URL': "",
    'UNS_CHANNEL_ID': 0,
    'UNS_SUPPRESS_NOTIFICATIONS': True,
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
        wh = warehouse.get_warehouse()
        return 'gioland is ok'

    @app.route('/crash')
    def crash():
        raise ValueError("Crashing as requested")


def create_app(config={}, testing=False):
    import auth
    import parcel
    import warehouse
    import utils
    app = flask.Flask(__name__, instance_relative_config=True)
    app.config.update(copy.deepcopy(default_config))
    if testing:
        app.config['TESTING'] = True
    else:
        app.config.update(configuration_from_environ())
        app.config.from_pyfile("settings.py", silent=True)
    app.config.update(config)
    warehouse.initialize_app(app)
    auth.register_on(app)
    parcel.register_on(app)
    register_monitoring_views(app)
    utils.initialize_app(app)
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


manager = flaskext.script.Manager(create_app)


def _set_up_logging(app):
    from logging.handlers import WatchedFileHandler

    log_dir = app.config.get('LOG_DIR')
    if log_dir:
        info_log = WatchedFileHandler(log_dir / 'info.log')
        info_log.setFormatter(logging.Formatter(LOG_FORMAT))
        info_log.setLevel(logging.INFO)
        logging.getLogger().addHandler(info_log)

    sentry_dsn = app.config.get('SENTRY_DSN')
    if sentry_dsn:
        from raven.conf import setup_logging
        from raven.handlers.logging import SentryHandler
        setup_logging(SentryHandler(sentry_dsn, level=logging.WARN))


def configuration_from_environ():
    env = os.environ.get
    config = {}
    config['WAREHOUSE_PATH'] = path(env('WAREHOUSE_DIR', ''))
    config['SENTRY_DSN'] = env('SENTRY_DSN')
    config['SECRET_KEY'] = env('SECRET_KEY')
    config['ROLE_SP'] = env('ROLE_SP', '').split()
    config['ROLE_ETC'] = env('ROLE_ETC', '').split()
    config['ROLE_NRC'] = env('ROLE_NRC', '').split()
    config['ROLE_ADMIN'] = env('ROLE_ADMIN', '').split()
    config['ROLE_VIEWER'] = env('ROLE_VIEWER', '').split()
    config['BASE_URL'] = env('BASE_URL', 'http://localhost:8000')
    config['UNS_CHANNEL_ID'] = env('UNS_CHANNEL_ID')
    config['UNS_LOGIN_USERNAME'] = env('UNS_LOGIN_USERNAME')
    config['UNS_LOGIN_PASSWORD'] = env('UNS_LOGIN_PASSWORD')
    config['UNS_SUPPRESS_NOTIFICATIONS'] = bool(env('UNS_SUPPRESS'))
    config['LDAP_SERVER'] = env('LDAP_SERVER')
    config['LDAP_USER_DN_PATTERN'] = env('LDAP_USER_DN_PATTERN')
    config['LOG_DIR'] = path(env('LOG_DIR', ''))
    return config


class RunCherryPyCommand(flaskext.script.Command):

    option_list = [
        flaskext.script.Option('--port', '-p', dest='port', type=int),
    ]

    def handle(self, app, port):
        _set_up_logging(app)

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
    from parcel import chain_tails

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
    logging.getLogger().addHandler(stderr)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    manager.run()

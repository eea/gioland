#!/usr/bin/env python

import os
import logging
from logging.handlers import SMTPHandler, WatchedFileHandler
import code
import copy
from path import path
import flask
import flaskext.script


default_config = {
    'LDAP_TIMEOUT': 10,
    'LDAP_SERVER': 'ldap://ldap3.eionet.europa.eu',
    'LDAP_USER_DN_PATTERN': "uid={user_id},ou=Users,o=EIONET,l=Europe",
    'TIME_ZONE': 'Europe/Copenhagen',
    'BASE_URL': "",
    'UNS_CHANNEL_ID': 0,
    'UNS_SUPPRESS_NOTIFICATIONS': True,
    'ROLE_ADMIN': [],
    'CACHING': False,
    'ALLOW_PARCEL_DELETION': False,
}


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
        app.config.update(get_configuration_from_sarge())
        app.config.from_pyfile("settings.py", silent=True)
    app.config.update(config)
    warehouse.initialize_app(app)
    auth.register_on(app)
    parcel.register_on(app)
    register_monitoring_views(app)
    utils.initialize_app(app)
    if app.config.get('SENTRY_DSN'):
        from raven.contrib.flask import Sentry
        app.extensions['_sentry_instance'] = Sentry(app)
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
    import notification

    stderr_handler = logging.StreamHandler()
    stderr_handler.level = logging.INFO
    log_fmt = logging.Formatter("[%(asctime)s] %(module)s "
                                "%(levelname)s %(message)s")
    stderr_handler.setFormatter(log_fmt)
    app.logger.addHandler(stderr_handler)

    notification.log.setLevel(logging.DEBUG)
    notification.log.addHandler(stderr_handler)

    if app.config.get('LOGGING_FOLDER'):
        varlog = path(app.config['LOGGING_FOLDER'])

        info_handler = WatchedFileHandler(varlog / 'info.log')
        info_handler.setFormatter(log_fmt)
        info_handler.setLevel(logging.INFO)
        app.logger.addHandler(info_handler)
        notification.log.addHandler(info_handler)

        if app.config.get('LOGGING_DEBUG_LOG'):
            debug_handler = WatchedFileHandler(varlog / 'debug.log')
            debug_handler.setFormatter(log_fmt)
            debug_handler.setLevel(logging.DEBUG)
            app.logger.addHandler(debug_handler)
            notification.log.addHandler(debug_handler)

    recipients = app.config.get('ERROR_MAIL_RECIPIENTS', [])
    if recipients:
        smtp_host = app.config.get('MAIL_SERVER', 'localhost')
        smtp_port = int(app.config.get('MAIL_PORT', 25))

        mail_handler_cfg = {
            'fromaddr': app.config['DEFAULT_MAIL_SENDER'],
            'toaddrs': recipients,
            'subject': "Error in %s" % app.config['DEPLOYMENT_NAME'],
            'mailhost': (smtp_host, smtp_port),
        }

        error_mail_handler = SMTPHandler(**mail_handler_cfg)
        error_mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(error_mail_handler)


def get_configuration_from_sarge():
    if 'SARGEAPP_CFG' not in os.environ:
        return {}

    config = {}
    with open(os.environ['SARGEAPP_CFG'], 'rb') as f:
        sargeapp_cfg = flask.json.load(f)

    services = sargeapp_cfg['services']

    config['WAREHOUSE_PATH'] = path(services[0]['path'])
    config['DEPLOYMENT_NAME'] = services[1]['DEPLOYMENT_NAME']
    config['LOGGING_FOLDER'] = services[1]['LOGGING_FOLDER']
    config['LOGGING_DEBUG_LOG'] = services[1].get('LOGGING_DEBUG_LOG', False)
    config['DEFAULT_MAIL_SENDER'] = services[1]['DEFAULT_MAIL_SENDER']
    config['ERROR_MAIL_RECIPIENTS'] = services[1]['ERROR_MAIL_RECIPIENTS']
    config['SENTRY_DSN'] = services[1]['SENTRY_DSN']
    config['SECRET_KEY'] = str(services[2]['SECRET_KEY'])
    config['ROLE_SERVICE_PROVIDER'] = services[3]['sp']
    config['ROLE_ETC'] = services[3]['etc']
    config['ROLE_NRC'] = services[3]['nrc']
    config['ROLE_ADMIN'] = services[3]['admin']
    config['ROLE_VIEWER'] = services[3]['viewer']
    config['BASE_URL'] = services[4]['base_url']
    config['UNS_CHANNEL_ID'] = services[5]['channel_id']
    config['UNS_LOGIN_USERNAME'] = services[5]['login_username']
    config['UNS_LOGIN_PASSWORD'] = services[5]['login_password']
    config['UNS_SUPPRESS_NOTIFICATIONS'] = bool(services[5].get('suppress'))

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
    manager.run()

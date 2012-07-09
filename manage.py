#!/usr/bin/env python

import code
import flask
import flaskext.script


default_config = {
}


def create_app(config={}):
    import views
    import warehouse
    app = flask.Flask(__name__, instance_relative_config=True)
    app.config.update(default_config)
    app.config.update(get_configuration_from_sarge())
    app.config.from_pyfile('settings.py', silent=True)
    app.config.update(config)
    if 'WAREHOUSE_PATH' in app.config:
        app.extensions['warehouse_connector'] = \
            warehouse.WarehouseConnector(app.config['WAREHOUSE_PATH'])
    views.register_on(app)
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
    import logging
    root_logger = logging.getLogger()

    stderr_handler = logging.StreamHandler()
    stderr_handler.level = logging.INFO
    log_fmt = logging.Formatter("[%(asctime)s] %(module)s "
                                "%(levelname)s %(message)s")
    stderr_handler.setFormatter(log_fmt)
    app.logger.addHandler(stderr_handler)
    root_logger.addHandler(stderr_handler)

    recipients = app.config.get('ERROR_MAIL_RECIPIENTS', [])
    if recipients:
        from logging.handlers import SMTPHandler
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
    import os
    from path import path

    if 'SARGEAPP_CFG' not in os.environ:
        return {}

    config = {}
    with open(os.environ['SARGEAPP_CFG'], 'rb') as f:
        sargeapp_cfg = flask.json.load(f)

    config['WAREHOUSE_PATH'] = path(sargeapp_cfg['services'][0]['path'])

    monitoring = sargeapp_cfg['services'][1]
    if 'DEPLOYMENT_NAME' in monitoring:
        config['DEPLOYMENT_NAME'] = monitoring['DEPLOYMENT_NAME']
    if 'DEFAULT_MAIL_SENDER' in monitoring:
        config['DEFAULT_MAIL_SENDER'] = monitoring['DEFAULT_MAIL_SENDER']
    if 'ERROR_MAIL_RECIPIENTS' in monitoring:
        config['ERROR_MAIL_RECIPIENTS'] = monitoring['ERROR_MAIL_RECIPIENTS']

    sessioncfg = sargeapp_cfg['services'][2]
    if 'SECRET_KEY' in sessioncfg:
        config['SECRET_KEY'] = str(sessioncfg['SECRET_KEY'])

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
        import views, transaction
        with views.warehouse() as wh:
            context['wh'] = wh
            context['transaction'] = transaction
            run()
    else:
        run()


if __name__ == '__main__':
    manager.run()

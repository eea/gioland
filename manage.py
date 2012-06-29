#!/usr/bin/env python

import flask
import flaskext.script


default_config = {
    'DEBUG': True,
}


def create_app(config={}):
    import views
    import warehouse
    app = flask.Flask(__name__, instance_relative_config=True)
    app.config.update(default_config)
    app.config.from_pyfile('settings.py', silent=True)
    app.config.update(config)
    if 'WAREHOUSE_PATH' in app.config:
        app.extensions['warehouse_connector'] = \
            warehouse.WarehouseConnector(app.config['WAREHOUSE_PATH'])
    views.register_on(app)
    return app


manager = flaskext.script.Manager(create_app)


class RunCherryPyCommand(flaskext.script.Command):

    option_list = [
        flaskext.script.Option('--port', '-p', dest='port', type=int),
    ]

    def handle(self, app, port):
        import sys
        import os
        import logging
        from path import path

        with open(os.environ['SARGEAPP_CFG'], 'rb') as f:
            sargeapp_cfg = flask.json.load(f)
        warehouse_path = path(sargeapp_cfg['services'][0]['path'])

        import warehouse
        app.config['WAREHOUSE_PATH'] = warehouse_path
        app.extensions['warehouse_connector'] = \
            warehouse.WarehouseConnector(app.config['WAREHOUSE_PATH'])

        handler = logging.StreamHandler()
        handler.level = logging.INFO
        logging.getLogger().addHandler(handler)

        import cherrypy.wsgiserver
        listen = ('127.0.0.1', port)
        server = cherrypy.wsgiserver.CherryPyWSGIServer(listen, app.wsgi_app)
        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()


manager.add_command('runcherrypy', RunCherryPyCommand())


if __name__ == '__main__':
    manager.run()

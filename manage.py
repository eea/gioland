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


if __name__ == '__main__':
    manager.run()

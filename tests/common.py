from contextlib import contextmanager
import flask
from mock import patch


def create_mock_app(warehouse_path=None):
    from manage import create_app
    config = {
        'TESTING': True,
        'SECRET_KEY': 'asdf',
        'UNS_SUPPRESS_NOTIFICATIONS': False,
    }
    if warehouse_path is not None:
        config['WAREHOUSE_PATH'] = str(warehouse_path)
    app = create_app(config, testing=True)

    @app.route('/test_login', methods=['POST'])
    def test_login():
        flask.session['username'] = flask.request.form['username']
        return "ok"

    @app.route('/test_logout')
    def test_logout():
        try:
            del flask.session['username']
        except KeyError:
            pass
        return "ok"

    return app


@contextmanager
def get_warehouse(app):
    import warehouse
    with app.test_request_context():
        yield warehouse.get_warehouse()


def authorization_patch():
    authorize_patch = patch('auth.authorize')
    authorize_patch.start()
    return authorize_patch


@contextmanager
def record_events(signal):
    events = []
    def _record(sender, **extra):
        events.append((sender, extra))
    signal.connect(_record)
    try:
        yield events
    finally:
        signal.disconnect(_record)

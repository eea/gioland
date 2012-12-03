import unittest
from contextlib import contextmanager
import tempfile
import flask
from mock import patch
from path import path
from werkzeug.datastructures import ImmutableDict


def create_mock_app(warehouse_path=None):
    from manage import create_app
    config = {
        'TESTING': True,
        'SECRET_KEY': 'asdf',
        'UNS_SUPPRESS_NOTIFICATIONS': False,
        'ALLOW_PARCEL_DELETION': True,
        'ROLE_VIEWER': ['user_id:somebody'],
        'CACHING': False,
    }
    if warehouse_path is not None:
        config['WAREHOUSE_PATH'] = str(warehouse_path)
        config['LOCK_FILE_PATH'] = str(warehouse_path / 'lockfile')
    app = create_app(config, testing=True)

    @app.route('/test_login', methods=['POST'])
    def test_login():
        flask.session['username'] = flask.request.form['username']
        return "ok"

    @app.route('/test_logout')
    def test_logout():
        flask.session.pop('username', None)
        return "ok"

    return app


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


def select(container, selector):
    """ Select elements using CSS """
    import lxml.html
    import lxml.cssselect
    if isinstance(container, basestring):
        doc = lxml.html.fromstring(container.decode('utf-8'))
    else:
        doc = container
    xpath = lxml.cssselect.CSSSelector(selector)
    return xpath(doc)


class AppTestCase(unittest.TestCase):

    CREATE_WAREHOUSE = False

    PARCEL_METADATA = ImmutableDict({
        'country': 'be',
        'theme': 'grc',
        'projection': 'eur',
        'resolution': '20m',
        'extent': 'full',
        'coverage': '',
    })

    def new_parcel(self, **extra_metadata):
        metadata = dict(self.PARCEL_METADATA)
        metadata.update(extra_metadata)
        with patch('auth.authorize'):
            resp = self.client.post('/parcel/new', data=metadata)
        self.assertEqual(resp.status_code, 302)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        return parcel_name

    def _pre_setup(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = None

        if self.CREATE_WAREHOUSE:
            self.wh_path = self.tmp / 'warehouse'

            @self.addCleanup
            def close_warehouse():
                connector = self.app.extensions['warehouse_connector']
                connector.close()

        self.app = create_mock_app(self.wh_path)
        self.client = self.app.test_client()
        self.client.post('/test_login', data={'username': 'somebody'})

    @property
    def wh(self):
        import warehouse
        return warehouse.get_warehouse()

    def __call__(self, result=None):
        self._pre_setup()
        super(AppTestCase, self).__call__(result)

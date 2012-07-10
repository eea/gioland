import unittest
import tempfile
from StringIO import StringIO
import flask
from path import path
from common import create_mock_app, get_warehouse, authorization_patch


class UploadTest(unittest.TestCase):

    metadata = {
        'country': 'be',
        'theme': 'grc',
        'projection': 'european',
        'resolution': '25m',
        'extent': 'full',
    }

    def setUp(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp/'warehouse'
        self.parcels_path = self.wh_path/'parcels'
        self.app = create_mock_app(self.wh_path)
        self.addCleanup(authorization_patch().stop)

    def test_login(self):
        client = self.app.test_client()
        client.post('/test_login', data={'username': 'tester'})

        client.preserve_context = True
        client.get('/')
        self.assertEqual(flask.g.username, 'tester')

    def test_begin_parcel_creates_folder(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new')
        self.assertIsNotNone(resp.location)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        self.assertTrue((self.parcels_path/parcel_name).isdir())

    def test_begin_parcel_saves_user_selected_metadata(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=dict(self.metadata, bogus='not here'))
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            self.assertDictContainsSubset(self.metadata, parcel.metadata)
            self.assertNotIn('bogus', parcel.metadata)

    def test_begin_parcel_saves_default_metadata(self):
        client = self.app.test_client()
        client.post('/test_login', data={'username': 'somebody'})
        resp = client.post('/parcel/new', data=self.metadata)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            self.assertEqual(parcel.metadata['stage'], 'int')
            self.assertEqual(parcel.metadata['user'], 'somebody')

    def test_show_existing_files_in_parcel(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]
        parcel_path = self.parcels_path/parcel_name
        (parcel_path/'some.txt').write_text('hello world')

        resp2 = client.get('/parcel/' + parcel_name)
        self.assertIn('some.txt', resp2.data)

    def test_http_post_saves_file_in_parcel(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]
        parcel_path = self.parcels_path/parcel_name

        client.post('/parcel/' + parcel_name + '/file', data={
            'file': (StringIO("teh file contents"), 'data.gml'),
        })
        self.assertEqual(parcel_path.listdir(), [parcel_path/'data.gml'])

    def test_finalize_changes_parceling_flag(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]

        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            self.assertTrue(parcel.uploading)

        resp2 = client.post('/parcel/%s/finalize' % parcel_name)
        parcel_name = resp2.location.rsplit('/', 1)[-1]

        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            self.assertFalse(parcel.uploading)

    def test_uploading_in_finalized_parcel_is_not_allowed(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]
        parcel_path = self.parcels_path/parcel_name
        client.post('/parcel/%s/finalize' % parcel_name)

        resp2 = client.post('/parcel/' + parcel_name + '/file', data={
            'file': (StringIO("teh file contents"), 'data.gml')})
        self.assertEqual(resp2.status_code, 403)
        self.assertEqual(parcel_path.listdir(), [])

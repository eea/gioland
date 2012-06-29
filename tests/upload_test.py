import unittest
import tempfile
from StringIO import StringIO
import flask
from path import path
from common import create_mock_app, get_warehouse


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

    def test_login(self):
        client = self.app.test_client()
        client.post('/login', data={'username': 'tester'})

        client.preserve_context = True
        client.get('/')
        self.assertEqual(flask.g.username, 'tester')

    def test_begin_upload_creates_folder(self):
        client = self.app.test_client()
        resp = client.post('/upload')
        self.assertIsNotNone(resp.location)
        upload_name = resp.location.rsplit('/', 1)[-1]
        self.assertTrue((self.parcels_path/upload_name).isdir())

    def test_begin_upload_saves_user_selected_metadata(self):
        client = self.app.test_client()
        resp = client.post('/upload', data=dict(self.metadata, bogus='not here'))
        upload_name = resp.location.rsplit('/', 1)[-1]
        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(upload_name)
            self.assertDictContainsSubset(self.metadata, parcel.metadata)
            self.assertNotIn('bogus', parcel.metadata)

    def test_begin_upload_saves_default_metadata(self):
        client = self.app.test_client()
        client.post('/login', data={'username': 'somebody'})
        resp = client.post('/upload', data=self.metadata)
        upload_name = resp.location.rsplit('/', 1)[-1]
        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(upload_name)
            self.assertEqual(parcel.metadata['stage'], 'intermediate')
            self.assertEqual(parcel.metadata['user'], 'somebody')

    def test_show_existing_files_in_upload(self):
        client = self.app.test_client()
        resp = client.post('/upload')
        upload_name = resp.location.rsplit('/', 1)[-1]
        upload_path = self.parcels_path/upload_name
        (upload_path/'some.txt').write_text('hello world')

        resp2 = client.get('/upload/' + upload_name)
        self.assertIn('some.txt', resp2.data)

    def test_http_post_saves_file_in_upload(self):
        client = self.app.test_client()
        resp = client.post('/upload')
        upload_name = resp.location.rsplit('/', 1)[-1]
        upload_path = self.parcels_path/upload_name

        resp2 = client.post('/upload/' + upload_name + '/file', data={
            'file': (StringIO("teh file contents"), 'data.gml'),
        })
        self.assertEqual(upload_path.listdir(), [upload_path/'data.gml'])

    def test_finalize_changes_uploading_flag(self):
        client = self.app.test_client()
        resp = client.post('/upload')
        upload_name = resp.location.rsplit('/', 1)[-1]

        with get_warehouse(self.app) as wh:
            upload = wh.get_parcel(upload_name)
            self.assertTrue(upload.uploading)

        resp2 = client.post('/upload/%s/finalize' % upload_name)
        parcel_name = resp2.location.rsplit('/', 1)[-1]

        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            self.assertFalse(parcel.uploading)

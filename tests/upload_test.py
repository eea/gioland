import unittest
import tempfile
from StringIO import StringIO
import flask
from path import path


def create_mock_app(warehouse_path):
    from manage import create_app
    return create_app({
        'TESTING': True,
        'SECRET_KEY': 'asdf',
        'WAREHOUSE_PATH': str(warehouse_path),
    })


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
        self.uploads_path = self.wh_path/'uploads'
        self.uploads_path.makedirs()
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
        self.assertTrue((self.uploads_path/upload_name).isdir())

    def test_begin_upload_saves_user_selected_metadata(self):
        import views
        client = self.app.test_client()
        resp = client.post('/upload', data=dict(self.metadata, bogus='not here'))
        upload_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            with views.warehouse() as wh:
                upload = wh.get_upload(upload_name)
                self.assertDictContainsSubset(self.metadata, upload.metadata)
                self.assertNotIn('bogus', upload.metadata)

    def test_begin_upload_saves_default_metadata(self):
        import views
        client = self.app.test_client()
        client.post('/login', data={'username': 'somebody'})
        resp = client.post('/upload', data=self.metadata)
        upload_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            with views.warehouse() as wh:
                upload = wh.get_upload(upload_name)
                self.assertEqual(upload.metadata['stage'], 'intermediate')
                self.assertEqual(upload.metadata['user'], 'somebody')

    def test_show_existing_files_in_upload(self):
        client = self.app.test_client()
        resp = client.post('/upload')
        upload_name = resp.location.rsplit('/', 1)[-1]
        upload_path = self.uploads_path/upload_name
        (upload_path/'some.txt').write_text('hello world')

        resp2 = client.get('/upload/' + upload_name)
        self.assertIn('some.txt', resp2.data)

    def test_http_post_saves_file_in_upload(self):
        client = self.app.test_client()
        resp = client.post('/upload')
        upload_name = resp.location.rsplit('/', 1)[-1]
        upload_path = self.uploads_path/upload_name

        resp2 = client.post('/upload/' + upload_name + '/file', data={
            'file': (StringIO("teh file contents"), 'data.gml'),
        })
        self.assertEqual(upload_path.listdir(), [upload_path/'data.gml'])

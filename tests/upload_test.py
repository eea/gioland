from StringIO import StringIO
import flask
from common import AppTestCase, authorization_patch


class UploadTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.parcels_path = self.wh_path/'parcels'
        self.addCleanup(authorization_patch().stop)

    def test_login(self):
        client = self.app.test_client()
        client.post('/test_login', data={'username': 'tester'})

        client.preserve_context = True
        client.get('/')
        self.assertEqual(flask.g.username, 'tester')

    def test_begin_parcel_creates_folder(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=self.PARCEL_METADATA)
        self.assertIsNotNone(resp.location)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        self.assertTrue((self.parcels_path/parcel_name).isdir())

    def test_begin_parcel_saves_user_selected_metadata(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=dict(self.PARCEL_METADATA, bogus='not here'))
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertDictContainsSubset(self.PARCEL_METADATA, parcel.metadata)
            self.assertNotIn('bogus', parcel.metadata)

    def test_begin_parcel_saves_default_metadata(self):
        client = self.app.test_client()
        client.post('/test_login', data={'username': 'somebody'})
        resp = client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertEqual(parcel.metadata['stage'], 'int')

    def test_show_existing_files_in_parcel(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        parcel_path = self.parcels_path/parcel_name
        (parcel_path/'some.txt').write_text('hello world')

        resp2 = client.get('/parcel/' + parcel_name)
        self.assertIn('some.txt', resp2.data)

    def test_http_post_saves_file_in_parcel(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        parcel_path = self.parcels_path/parcel_name

        client.post('/parcel/' + parcel_name + '/file', data={
            'file': (StringIO("teh file contents"), 'data.gml'),
        })
        self.assertEqual(parcel_path.listdir(), [parcel_path/'data.gml'])

    def test_finalize_changes_parceling_flag(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertTrue(parcel.uploading)

        resp2 = client.post('/parcel/%s/finalize' % parcel_name)
        parcel_name = resp2.location.rsplit('/', 1)[-1]

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertFalse(parcel.uploading)

    def test_uploading_in_finalized_parcel_is_not_allowed(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        parcel_path = self.parcels_path/parcel_name
        client.post('/parcel/%s/finalize' % parcel_name)

        resp2 = client.post('/parcel/' + parcel_name + '/file', data={
            'file': (StringIO("teh file contents"), 'data.gml')})
        self.assertEqual(resp2.status_code, 403)
        self.assertEqual(parcel_path.listdir(), [])

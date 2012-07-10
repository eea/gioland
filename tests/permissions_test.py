import unittest
import tempfile
from StringIO import StringIO
from path import path
from mock import patch
from common import create_mock_app


def setUpModule(self):
    import parcel; self.parcel = parcel


class SenderCollector(list):

    def __init__(self, signal):
        signal.connect(self.event)

    def event(self, sender, **extra):
        self.append(sender)


class UploadTest(unittest.TestCase):

    def setUp(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp / 'warehouse'
        self.parcels_path = self.wh_path / 'parcels'
        self.app = create_mock_app(self.wh_path)
        self.client = self.app.test_client()
        self.client.post('/test_login', data={'username': 'somebody'})

    def add_to_role(self, username, role_name):
        self.app.config.setdefault(role_name, []).append(username)

    def create_parcel(self):
        with patch('parcel.authorize'):
            post_resp = self.client.post('/parcel/new')
            self.assertEqual(post_resp.status_code, 302)
            return post_resp.location.rsplit('/', 1)[-1]

    def try_new_parcel(self):
        new_parcels = SenderCollector(parcel.parcel_created)
        post_resp = self.client.post('/parcel/new')
        if post_resp.status_code == 403:
            self.assertEqual(len(new_parcels), 0)
            return False
        elif post_resp.status_code == 302:
            self.assertEqual(len(new_parcels), 1)
            return True
        else:
            self.fail('unexpected http status code')

    def try_upload(self, parcel_name):
        uploaded_files = SenderCollector(parcel.file_uploaded)
        url = '/parcel/' + parcel_name + '/file'
        post_data = {'file': (StringIO("xx"), 'y.txt')}
        post_resp = self.client.post(url, data=post_data)
        if post_resp.status_code == 403:
            self.assertEqual(len(uploaded_files), 0)
            return False
        elif post_resp.status_code == 302:
            self.assertEqual(len(uploaded_files), 1)
            return True
        else:
            self.fail('unexpected http status code')

    def try_finalize(self, parcel_name):
        finalized_parcels = SenderCollector(parcel.parcel_finalized)
        post_resp = self.client.post('/parcel/%s/finalize' % parcel_name)
        if post_resp.status_code == 403:
            self.assertEqual(len(finalized_parcels), 0)
            return False
        elif post_resp.status_code == 302:
            self.assertEqual(len(finalized_parcels), 1)
            return True
        else:
            self.fail('unexpected http status code')


    def test_random_user_not_allowed_to_begin_upload(self):
        self.assertFalse(self.try_new_parcel())

    def test_service_provider_allowed_to_begin_upload(self):
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
        self.assertTrue(self.try_new_parcel())


    def test_random_user_not_allowed_to_upload_at_intermediate_state(self):
        name = self.create_parcel()
        self.assertFalse(self.try_upload(name))

    def test_service_provider_allowed_to_upload_at_intermediate_state(self):
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
        name = self.create_parcel()
        self.assertTrue(self.try_upload(name))


    def test_random_user_not_allowed_to_finalize_at_intermediate_state(self):
        name = self.create_parcel()
        self.assertFalse(self.try_finalize(name))

    def test_service_provider_allowed_to_finalize_at_intermediate_state(self):
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
        name = self.create_parcel()
        self.assertTrue(self.try_finalize(name))

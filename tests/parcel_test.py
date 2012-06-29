import unittest
import tempfile
from StringIO import StringIO
from contextlib import contextmanager
import flask
from path import path
import transaction
from common import create_mock_app, get_warehouse


class ParcelTest(unittest.TestCase):

    def setUp(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp/'warehouse'
        self.uploads_path = self.wh_path/'uploads'
        self.parcels_path = self.wh_path/'parcels'
        self.app = create_mock_app(self.wh_path)

    def test_download_file(self):
        map_data = 'teh map data'
        client = self.app.test_client()
        client.post('/login', data={'username': 'somebody'})

        with get_warehouse(self.app) as wh:
            parcel = wh.new_parcel()
            (parcel.get_path()/'data.gml').write_text(map_data)
            parcel.finalize()
            transaction.commit()
            parcel_name = parcel.name

        resp = client.get('/parcel/%s/download/data.gml' % parcel_name)
        self.assertEqual(resp.data, map_data)

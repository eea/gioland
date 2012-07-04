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

    def test_finalize_triggers_next_step_with_forward_backward_references(self):
        with get_warehouse(self.app) as wh:
            parcel = wh.new_parcel()
            parcel.save_metadata({'stage': 'vch'}) # verification check
            transaction.commit()
            parcel_name = parcel.name

        client = self.app.test_client()
        client.post('/parcel/%s/finalize' % parcel_name)

        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel_name = parcel.metadata['next_parcel']
            next_parcel = wh.get_parcel(next_parcel_name)
            self.assertEqual(next_parcel.metadata['prev_parcel'], parcel.name)
            self.assertEqual(next_parcel.metadata['stage'], 'enh') # enhancement

    def test_finalize_preserves_metadata(self):
        metadata = {
            'country': 'be',
            'theme': 'grc',
            'projection': 'european',
            'resolution': '25m',
            'extent': 'full',
        }

        client = self.app.test_client()
        resp = client.post('/parcel/new', data=metadata)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        client.post('/parcel/%s/finalize' % parcel_name)

        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            next_parcel = wh.get_parcel(parcel.metadata['next_parcel'])
            self.assertDictContainsSubset(metadata, next_parcel.metadata)

    def test_delete_parcel(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]
        client.post('/parcel/%s/delete' % parcel_name)

        resp2 = client.get('/parcel/%s' % parcel_name)
        self.assertEqual(resp2.status_code, 404)

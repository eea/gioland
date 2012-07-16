import unittest
import tempfile
from datetime import datetime
from path import path
import transaction
from mock import patch
from common import create_mock_app, get_warehouse, authorization_patch


class ParcelTest(unittest.TestCase):

    METADATA = {
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
        self.app = create_mock_app(self.wh_path)
        self.addCleanup(authorization_patch().stop)

    def test_download_file(self):
        map_data = 'teh map data'
        client = self.app.test_client()
        client.post('/test_login', data={'username': 'somebody'})

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
            parcel.save_metadata(self.METADATA)
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
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=self.METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        client.post('/parcel/%s/finalize' % parcel_name)

        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            next_parcel = wh.get_parcel(parcel.metadata['next_parcel'])
            self.assertDictContainsSubset(self.METADATA, next_parcel.metadata)

    def create_parcel_at_stage(self, stage):
        client = self.app.test_client()
        resp = client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            parcel.metadata['stage'] = stage
            transaction.commit()
        return parcel_name

    def test_finalize_with_reject_disallowed_for_most_stages(self):
        client = self.app.test_client()
        for stage in ['int', 'ver', 'enh', 'fin']:
            parcel_name = self.create_parcel_at_stage(stage)
            resp = client.post('/parcel/%s/finalize' % parcel_name,
                               data={'reject': 'on'})
            self.assertEqual(resp.status_code, 403)

    def test_finalize_with_reject_triggers_previous_step(self):
        client = self.app.test_client()
        for stage, prev_stage in [('sch', 'int'),
                                  ('vch', 'ver'),
                                  ('ech', 'enh')]:
            parcel_name = self.create_parcel_at_stage(stage)
            resp = client.post('/parcel/%s/finalize' % parcel_name,
                               data={'reject': 'on'})
            with get_warehouse(self.app) as wh:
                parcel = wh.get_parcel(parcel_name)
                next_parcel = wh.get_parcel(parcel.metadata['next_parcel'])
                self.assertEqual(next_parcel.metadata['stage'], prev_stage)

    def test_delete_parcel(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]
        client.post('/parcel/%s/delete' % parcel_name)

        resp2 = client.get('/parcel/%s' % parcel_name)
        self.assertEqual(resp2.status_code, 404)


class ParcelHistoryTest(unittest.TestCase):

    def setUp(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp/'warehouse'
        self.app = create_mock_app(self.wh_path)
        datetime_patch = patch('parcel.datetime')
        self.mock_datetime = datetime_patch.start()
        self.addCleanup(datetime_patch.stop)
        self.addCleanup(authorization_patch().stop)
        self.client = self.app.test_client()
        self.client.post('/test_login', data={'username': 'somebody'})

    def check_history_item(self, item, ok_item):
        for name in ok_item:
            self.assertEqual(getattr(item, name, None), ok_item[name])

    def test_parcel_creation_is_logged_in_history(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]

        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            self.check_history_item(parcel.history[0], {
                'time': utcnow,
                'title': "New upload",
                'actor': 'somebody',
            })

    def test_parcel_finalization_is_logged_in_history(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new')
        parcel_name = resp.location.rsplit('/', 1)[-1]
        self.client.post('/parcel/%s/finalize' % parcel_name)

        with get_warehouse(self.app) as wh:
            parcel = wh.get_parcel(parcel_name)
            item = parcel.history[-1]
            self.check_history_item(item, {
                'time': utcnow,
                'title': "Finalized",
                'actor': 'somebody',
            })
            self.assertIn(parcel.metadata['next_parcel'],
                          item.description_html)
            self.assertIn("Semantic check", item.description_html)

    def test_parcel_finalization_generates_message_on_next_parcel(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new')
        parcel1_name = resp.location.rsplit('/', 1)[-1]
        self.client.post('/parcel/%s/finalize' % parcel1_name)

        with get_warehouse(self.app) as wh:
            parcel1 = wh.get_parcel(parcel1_name)
            parcel2 = wh.get_parcel(parcel1.metadata['next_parcel'])
            item = parcel2.history[0]
            self.check_history_item(item, {
                'time': utcnow,
                'title': "Next stage",
                'actor': 'somebody',
            })
            self.assertIn(parcel1_name, item.description_html)
            self.assertIn("Intermediate", item.description_html)

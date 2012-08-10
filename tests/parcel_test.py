import tempfile
import flask
from datetime import datetime
from StringIO import StringIO
from path import path
from mock import patch
from common import (AppTestCase, create_mock_app, authorization_patch, select)


class ParcelTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.parcels_path = self.wh_path / 'parcels'
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
        self.assertTrue((self.parcels_path / parcel_name).isdir())

    def test_begin_parcel_saves_user_selected_metadata(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new',
                           data=dict(self.PARCEL_METADATA, bogus='not here'))
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertDictContainsSubset(self.PARCEL_METADATA,
                                          parcel.metadata)
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
        parcel_path = self.parcels_path / parcel_name
        (parcel_path / 'some.txt').write_text('hello world')

        resp2 = client.get('/parcel/' + parcel_name)
        self.assertIn('some.txt', resp2.data)

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
        parcel_path = self.parcels_path / parcel_name
        client.post('/parcel/%s/finalize' % parcel_name)

        resp2 = client.post('/parcel/' + parcel_name + '/file', data={
            'file': (StringIO("teh file contents"), 'data.gml')})
        self.assertEqual(resp2.status_code, 403)
        self.assertEqual(parcel_path.listdir(), [])

    def test_finalize_triggers_next_step_with_forward_backward_references(self):
        with self.app.test_request_context():
            parcel = self.wh.new_parcel()
            parcel.save_metadata(self.PARCEL_METADATA)
            parcel.save_metadata({'stage': 'vch'})  # verification check
            parcel_name = parcel.name

        client = self.app.test_client()
        client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel_name = parcel.metadata['next_parcel']
            next_parcel = self.wh.get_parcel(next_parcel_name)
            self.assertEqual(next_parcel.metadata['prev_parcel'], parcel.name)
            # enhancement
            self.assertEqual(next_parcel.metadata['stage'], 'enh')

    def test_finalize_preserves_metadata(self):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            next_parcel = self.wh.get_parcel(parcel.metadata['next_parcel'])
            self.assertDictContainsSubset(self.PARCEL_METADATA,
                                          next_parcel.metadata)

    def test_parcel_with_corrupted_metadata_fails(self):
        client = self.app.test_client()
        metadata = dict(self.PARCEL_METADATA)
        metadata['country'] = 'country'
        resp = client.post('/parcel/new', data=metadata)
        self.assertEqual(400, resp.status_code)

    def test_parcel_with_corrupted_metadata_fails(self):
        client = self.app.test_client()
        metadata = dict(self.PARCEL_METADATA)
        metadata['country'] = 'country'
        resp = client.post('/parcel/new', data=metadata)
        self.assertEqual(400, resp.status_code)

    def create_parcel_at_stage(self, stage):
        client = self.app.test_client()
        resp = client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            parcel.metadata['stage'] = stage
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
            with self.app.test_request_context():
                parcel = self.wh.get_parcel(parcel_name)
                next_parcel = self.wh.get_parcel(parcel.metadata['next_parcel'])
                self.assertEqual(next_parcel.metadata['stage'], prev_stage)

    def test_finalize_last_parcel_forbidden(self):
        client = self.app.test_client()
        parcel_name = self.create_parcel_at_stage('fva')
        resp = client.post('/parcel/%s/finalize' % parcel_name)
        self.assertEqual(403, resp.status_code)

    def test_delete_parcel(self):
        parcel_name_1 = self.create_parcel_at_stage('ver')
        parcel_name_2 = self.create_parcel_at_stage('vch')

        with self.app.test_request_context():
            parcel_1 = self.wh.get_parcel(parcel_name_1)
            parcel_2 = self.wh.get_parcel(parcel_name_2)

            parcel_1.save_metadata({'next_parcel': parcel_name_2})
            parcel_1.finalize()
            parcel_2.save_metadata({'prev_parcel': parcel_name_1})

        client = self.app.test_client()
        client.post('/parcel/%s/delete' % parcel_name_2)

        resp = client.get('/parcel/%s' % parcel_name_2)
        self.assertEqual(resp.status_code, 404)

        resp = client.get('/parcel/%s' % parcel_name_1)
        self.assertEqual(resp.status_code, 404)

    def test_delete_parcel_link_if_allow_parcel_deletion(self):
        parcel_name = self.create_parcel_at_stage('ver')

        client = self.app.test_client()
        resp = client.get('/parcel/%s' % parcel_name)
        self.assertEqual(1, len(select(resp.data, '.delete-parcel')))

    def test_delete_parcel_link_if_not_allow_parcel_deletion(self):
        self.app.config['ALLOW_PARCEL_DELETION'] = False
        parcel_name = self.create_parcel_at_stage('ver')

        client = self.app.test_client()
        resp = client.get('/parcel/%s' % parcel_name)
        self.assertEqual(0, len(select(resp.data, '.delete-parcel')))

    def test_filter_parcel(self):
        with self.app.test_request_context():
            parcel1 = self.wh.new_parcel()
            parcel2 = self.wh.new_parcel()

            parcel1.metadata['country'] = 'ro'
            parcel1.metadata['extent'] = 'partial'

            parcel2.metadata['country'] = 'at'

        client = self.app.test_client()
        resp = client.get('/overview?country=ro&extent=partial')
        rows = select(resp.data, ".datatable tbody tr")
        self.assertEqual(1, len(rows))

    def test_filter_parcel_empty(self):
        with self.app.test_request_context():
            parcel1 = self.wh.new_parcel()
            parcel1.metadata['country'] = 'ro'

        client = self.app.test_client()
        resp = client.get('/overview?country=ro&extent=partial')
        data = select(resp.data, ".datatable tbody tr")
        self.assertEqual(0, len(data))


class ParcelHistoryTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
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

        resp = self.client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.check_history_item(parcel.history[0], {
                'time': utcnow,
                'title': "New upload",
                'actor': 'somebody',
            })

    def test_parcel_finalization_is_logged_in_history(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        self.client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
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

        resp = self.client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel1_name = resp.location.rsplit('/', 1)[-1]
        self.client.post('/parcel/%s/finalize' % parcel1_name)

        with self.app.test_request_context():
            parcel1 = self.wh.get_parcel(parcel1_name)
            parcel2 = self.wh.get_parcel(parcel1.metadata['next_parcel'])
            item = parcel2.history[0]
            self.check_history_item(item, {
                'time': utcnow,
                'title': "Next stage",
                'actor': 'somebody',
            })
            self.assertIn(parcel1_name, item.description_html)
            self.assertIn("Intermediate", item.description_html)

    def test_parcel_comment(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        comment = "test comment"
        self.client.post('/parcel/%s/comment' % parcel_name,
                         data={"comment": comment})

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.check_history_item(parcel.history[1], {
                'time': utcnow,
                'title': "Comment",
                'actor': "somebody",
                'description_html': comment,
            })

    def test_parcel_comment_by_anonymous_forbidden(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        self.client.get('/test_logout')
        comment = "test comment"
        resp = self.client.post('/parcel/%s/comment' % parcel_name,
                                data={"comment": comment})
        self.assertEqual(403, resp.status_code)

    def test_parcel_comment_html_entities_escaped(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        comment = "<html>"
        self.client.post('/parcel/%s/comment' % parcel_name,
                         data={"comment": comment})

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.check_history_item(parcel.history[1], {
                'time': utcnow,
                'description_html': "&lt;html&gt;",
            })

import string
from datetime import datetime

import flask
from StringIO import StringIO
from common import AppTestCase, authorization_patch, select
from mock import patch
from gioland.parcel import _get_stages_for_parcel

from gioland.definitions import COUNTRY, LOT


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
        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        self.assertIsNotNone(resp.location)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        self.assertTrue((self.parcels_path / parcel_name).isdir())

    def test_begin_parcel_saves_user_selected_metadata(self):
        resp = self.client.post('/parcel/new/country', data=dict(self.PARCEL_METADATA,
                                                         bogus='not here'))
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertDictContainsSubset(self.PARCEL_METADATA,
                                          parcel.metadata)
            self.assertNotIn('bogus', parcel.metadata)

    def test_begin_stream_parcel(self):
        resp = self.client.post('parcel/new/stream', data=self.STREAM_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertDictContainsSubset(self.STREAM_METADATA,
                                          parcel.metadata)
            self.assertEqual(parcel.metadata['stage'], 's-int')

    def test_finalize_triggers_next_step_with_references_stream(self):
        with self.app.test_request_context():
            parcel = self.wh.new_parcel()
            parcel.save_metadata(self.STREAM_METADATA)
            parcel.save_metadata({'stage': 's-slc'})
            parcel_name = parcel.name

        self.client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel_name = parcel.metadata['next_parcel']
            next_parcel = self.wh.get_parcel(next_parcel_name)
            self.assertIn(parcel.name,
                          next_parcel.metadata['prev_parcel_list'])
            self.assertEqual(next_parcel.metadata['stage'], 's-fih')

    def test_begin_parcel_saves_default_metadata(self):
        resp = self.client.post('/parcel/new/country',
                                data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertEqual(parcel.metadata['stage'], 'c-int')

    def test_begin_parcel_displays_all_deliveries(self):
        resp = self.client.get('/parcel/new/country')
        delivery_types = select(resp.data, '[name=delivery_type]')
        self.assertEqual(len(delivery_types), 3)

    def test_show_existing_files_in_parcel(self):
        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        parcel_path = self.parcels_path / parcel_name
        (parcel_path / 'some.txt').write_text('hello world')

        resp2 = self.client.get('/parcel/' + parcel_name)
        self.assertIn('some.txt', resp2.data)

    def test_finalize_changes_parceling_flag(self):
        resp = self.client.post('/parcel/new/stream', data=self.STREAM_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertTrue(parcel.uploading)

        resp2 = self.client.post('/parcel/%s/finalize' % parcel_name)
        parcel_name = resp2.location.rsplit('/', 1)[-1]

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertFalse(parcel.uploading)

    def test_uploading_in_finalized_parcel_is_not_allowed(self):
        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        parcel_path = self.parcels_path / parcel_name
        self.client.post('/parcel/%s/finalize' % parcel_name)

        resp2 = self.client.post('/parcel/' + parcel_name + '/file', data={
            'file': (StringIO("teh file contents"), 'data.gml')})
        self.assertEqual(resp2.status_code, 403)
        self.assertEqual(parcel_path.listdir(), [])

    def test_finalize_triggers_next_step_with_references(self):
        with self.app.test_request_context():
            parcel = self.wh.new_parcel()
            parcel.save_metadata(self.PARCEL_METADATA)
            parcel.save_metadata({'stage': 'c-fsc'})  # verification check
            parcel_name = parcel.name

        self.client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel_name = parcel.metadata['next_parcel']
            next_parcel = self.wh.get_parcel(next_parcel_name)
            self.assertIn(parcel.name,
                          next_parcel.metadata['prev_parcel_list'])
            # enhancement
            self.assertEqual(next_parcel.metadata['stage'], 'c-fih')

    def test_finalize_preserves_metadata(self):
        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        self.client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            next_parcel = self.wh.get_parcel(parcel.metadata['next_parcel'])
            self.assertDictContainsSubset(self.PARCEL_METADATA,
                                          next_parcel.metadata)

    def test_parcel_with_corrupted_metadata_fails(self):
        metadata = dict(self.PARCEL_METADATA)
        metadata['country'] = 'country'
        resp = self.client.post('/parcel/new/country', data=metadata)
        self.assertEqual(400, resp.status_code)

    def test_finalize_with_reject_disallowed_for_most_stages(self):
        for stage in ['l-int', 'l-fih', 'l-fhm']:
            parcel_name = self.new_parcel(stage=stage,
                                          delivery_type=LOT)
            resp = self.client.post('/parcel/%s/finalize' % parcel_name,
                                    data={'reject': 'on'})
            self.assertEqual(resp.status_code, 403)

    def test_finalize_with_reject_triggers_previous_step(self):
        for stage, prev_stage in [('l-vsc', 'l-int'),
                                  ('l-sch', 'l-int'),
                                  ('l-fmc', 'l-fih')]:
            parcel_name = self.new_parcel(stage=stage,
                                          delivery_type=LOT,
                                          extent='partial')
            self.client.post('/parcel/%s/finalize' % parcel_name,
                             data={'reject': 'on'})
            with self.app.test_request_context():
                parcel = self.wh.get_parcel(parcel_name)
                next_parcel = self.wh.get_parcel(
                    parcel.metadata['next_parcel'])
                self.assertEqual(next_parcel.metadata['stage'], prev_stage)

    def test_finalize_with_reject_saves_rejected_metadata(self):
        for stage in ['c-fsc']:
            parcel_name = self.new_parcel(stage=stage)
            self.client.post('/parcel/%s/finalize' % parcel_name,
                             data={'reject': 'on'})
            with self.app.test_request_context():
                parcel = self.wh.get_parcel(parcel_name)
                self.assertTrue(parcel.metadata['rejection'])

    def test_get_parcels_by_stage(self):
        from gioland import parcel
        self.new_parcel(stage='c-int')
        parcel_name_1 = self.new_parcel(stage='c-fsc')
        self.client.post('/parcel/%s/finalize' % parcel_name_1,
                         data={'reject': 'on'})

        with self.app.test_request_context():
            parcel_name = self.wh.get_parcel(parcel_name_1)\
                              .metadata['next_parcel']
            parcels_by_stage = parcel.get_parcels_by_stage(parcel_name)
            parcels = [p for p in parcels_by_stage.values() if p]
            self.assertEqual(2, len(parcels))

    def test_finalize_last_parcel_forbidden(self):
        parcel_name = self.new_parcel(stage='c-fih')
        resp = self.client.post('/parcel/%s/finalize' % parcel_name)
        self.assertEqual(403, resp.status_code)

    def test_finalize_finalized_parcel_forbidden(self):
        parcel_name = self.new_parcel(stage='c-fsc')
        resp1 = self.client.post('/parcel/%s/finalize' % parcel_name)
        self.assertEqual(resp1.status_code, 302)
        resp2 = self.client.post('/parcel/%s/finalize' % parcel_name)
        self.assertEqual(resp2.status_code, 403)

    def test_delete_parcel(self):
        parcel_name_1 = self.new_parcel(stage='c-int')
        parcel_name_2 = self.new_parcel(stage='c-fsc')

        with self.app.test_request_context():
            parcel_1 = self.wh.get_parcel(parcel_name_1)
            parcel_2 = self.wh.get_parcel(parcel_name_2)

            parcel_1.save_metadata({'next_parcel': parcel_name_2})
            parcel_1.finalize()
            parcel_2.save_metadata({'prev_parcel': parcel_name_1})

        self.client.post('/parcel/%s/delete' % parcel_name_2)
        resp = self.client.get('/parcel/%s' % parcel_name_2)
        self.assertEqual(resp.status_code, 404)

        resp = self.client.get('/parcel/%s' % parcel_name_1)
        self.assertEqual(resp.status_code, 200)

    def test_delete_parcel_link_if_allow_parcel_deletion(self):
        parcel_name = self.new_parcel(stage='c-fsc')
        resp = self.client.get('/parcel/%s' % parcel_name)
        self.assertEqual(1, len(select(resp.data, '.delete-parcel')))

    def test_delete_parcel_link_if_not_allow_parcel_deletion(self):
        self.app.config['ALLOW_PARCEL_DELETION'] = False
        parcel_name = self.new_parcel(stage='c-fsc')
        resp = self.client.get('/parcel/%s' % parcel_name)
        self.assertEqual(0, len(select(resp.data, '.delete-parcel')))

    def test_filter_parcel(self):
        now = datetime.utcnow()
        with self.app.test_request_context():
            parcel1 = self.wh.new_parcel()
            parcel1.add_history_item('create', now, 'tester', '')
            parcel2 = self.wh.new_parcel()
            parcel2.add_history_item('create', now, 'tester', '')

            parcel1.metadata['country'] = 'ro'
            parcel1.metadata['extent'] = 'partial'

            parcel2.metadata['country'] = 'at'

        resp = self.client.get('/search/country?country=ro&extent=partial')
        rows = select(resp.data, ".datatable tbody tr")
        self.assertEqual(1, len(rows))

    def test_filter_parcel_empty(self):
        with self.app.test_request_context():
            parcel1 = self.wh.new_parcel()
            parcel1.metadata['country'] = 'ro'

        resp = self.client.get('/search/country?country=ro&extent=partial')
        data = select(resp.data, ".datatable tbody tr")
        self.assertEqual(0, len(data))

    def test_country_workflow_overview_group(self):
        data = dict(self.PARCEL_METADATA)
        self.client.post('/parcel/new/country', data=data)

        data['product'] = 'grl'
        self.client.post('/parcel/new/country', data=data)

        resp = self.client.get('/country/be')
        table_headers = select(resp.data, '.title')
        self.assertEqual(1, len(table_headers))

        table_headers_text = [t.text for t in table_headers]
        self.assertIn('Grassland',
                      map(string.strip, table_headers_text))

    def test_country_workflow_overview_group_contain_correct_parcels(self):
        data = dict(self.PARCEL_METADATA)
        self.client.post('/parcel/new/country', data=data)
        self.client.post('/parcel/new/country', data=data)

        resp = self.client.get('/country/be')
        table = select(resp.data, '.datatable')
        self.assertEqual(1, len(table))
        rows = select(resp.data, '.datatable tbody tr')
        self.assertEqual(2, len(rows))

    def test_parcel_other_stage_does_not_have_files_from_prev_stage(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        parcel_name = self.new_parcel(stage='c-fsc')
        parcel_path = self.parcels_path / parcel_name
        (parcel_path / 'some.txt').write_text('hello world')

        with self.app.test_request_context():
            self.client.post('/parcel/%s/finalize' % parcel_name)

            parcel = self.wh.get_parcel(parcel_name)
            parcel2 = self.wh.get_parcel(parcel.metadata['next_parcel'])

            files = [f for f in parcel2.get_files()]
            self.assertEqual(0, len(files))


class ParcelHistoryTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        datetime_patch = patch('gioland.forms.datetime')
        datetime_parcel_patch = patch('gioland.parcel.datetime')
        self.mock_datetime = datetime_patch.start()
        self.mock_parcel_datetime = datetime_parcel_patch.start()
        self.addCleanup(datetime_patch.stop)
        self.addCleanup(datetime_parcel_patch.stop)
        self.addCleanup(authorization_patch().stop)

    def check_history_item(self, item, ok_item):
        for name in ok_item:
            self.assertEqual(getattr(item, name, None), ok_item[name])

    def test_parcel_creation_is_logged_in_history(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow
        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
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
        self.mock_parcel_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        self.client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            item = parcel.history[-1]
            self.check_history_item(item, {
                'time': utcnow,
                'title': "Service provider upload finished",
                'actor': 'somebody',
            })
            self.assertIn(parcel.metadata['next_parcel'],
                          item.description_html)
            self.assertIn("Semantic check", item.description_html)

    def test_parcel_finalization_generates_message_on_next_parcel(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow
        self.mock_parcel_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        parcel1_name = resp.location.rsplit('/', 1)[-1]
        self.client.post('/parcel/%s/finalize' % parcel1_name)

        with self.app.test_request_context():
            parcel1 = self.wh.get_parcel(parcel1_name)
            parcel2 = self.wh.get_parcel(parcel1.metadata['next_parcel'])
            item = parcel2.history[0]
            self.check_history_item(item, {
                'time': utcnow,
                'title': "Ready for Final Semantic check",
                'actor': 'somebody',
            })
            self.assertIn(parcel1_name, item.description_html)
            self.assertIn("Service provider upload", item.description_html)

    def test_parcel_comment(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow
        self.mock_parcel_datetime.utcnow.return_value = utcnow
        resp = self.client.post('/parcel/new/stream',
                                data=self.STREAM_METADATA)
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
        self.mock_parcel_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        self.client.get('/test_logout')
        comment = "test comment"
        resp = self.client.post('/parcel/%s/comment' % parcel_name,
                                data={"comment": comment})
        self.assertEqual(302, resp.status_code)

    def test_parcel_comment_html_entities_escaped(self):
        utcnow = datetime.utcnow()
        self.mock_datetime.utcnow.return_value = utcnow
        self.mock_parcel_datetime.utcnow.return_value = utcnow

        resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
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


class LotTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.parcels_path = self.wh_path / 'parcels'
        self.addCleanup(authorization_patch().stop)

    def test_parcel_delivery_type_for_country(self):
        resp = self.client.post('/parcel/new/country',
                                data=self.PARCEL_METADATA)
        self.assertIsNotNone(resp.location)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertDictContainsSubset({'delivery_type': 'country'},
                                          parcel.metadata)

    def test_parcel_delivery_type_for_lot(self):
        resp = self.client.post('/parcel/new/lot',
                                data=self.LOT_METADATA)
        self.assertIsNotNone(resp.location)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertDictContainsSubset({'delivery_type': 'lot'},
                                          parcel.metadata)

    def test_partial_lot_parcel_contains_optional_stage(self):
        parcel_name = self.new_parcel(stage='int',
                                      delivery_type=LOT,
                                      extent='partial')
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            _, DELIVERY_STAGES_ORDER = _get_stages_for_parcel(parcel)
            self.assertIn('l-vsc', DELIVERY_STAGES_ORDER)

    def test_full_lot_parcel_does_not_contain_optional_stage(self):
        parcel_name = self.new_parcel(stage='l-int',
                                      delivery_type=LOT,
                                      extent='full')
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            _, DELIVERY_STAGES_ORDER = _get_stages_for_parcel(parcel)
            self.assertNotIn('l-vsc', DELIVERY_STAGES_ORDER)

    def test_finalize_lot_triggers_correct_stage(self):
        parcel_name = self.new_parcel(stage='l-int', delivery_type=LOT,
                                      extent='partial')
        self.client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel_name = parcel.metadata['next_parcel']
            next_parcel = self.wh.get_parcel(next_parcel_name)
            self.assertIn(parcel.name,
                          next_parcel.metadata['prev_parcel_list'])
            # Final Semantic Check
            self.assertEqual(next_parcel.metadata['stage'], 'l-vsc')

    def test_finalize_with_reject_triggers_previous_step(self):
        parcel_name = self.new_parcel(stage='l-fmc', delivery_type=LOT)
        resp = self.client.post('/parcel/%s/finalize' % parcel_name,
                                data={'reject': 'on'})
        self.assertEqual(302, resp.status_code)
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            next_parcel = self.wh.get_parcel(
                    parcel.metadata['next_parcel'])
            self.assertEqual(next_parcel.metadata['stage'], 'l-fih')

    def test_finalze_lot_final_stage_forbidden(self):
        parcel_name = self.new_parcel(stage='l-fhm', delivery_type=LOT)
        resp = self.client.post('/parcel/%s/finalize' % parcel_name)
        self.assertEqual(403, resp.status_code)

    def test_search_country_deliveries(self):
        self.new_parcel(stage='l-fih', delivery_type=COUNTRY)
        resp = self.client.get('/search/country')
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, len(select(resp.data, '.datatable tbody tr')))

    def test_search_lot_deliveries(self):
        self.new_parcel(stage='l-fih', delivery_type=LOT)
        self.new_parcel(stage='l-fih', delivery_type=LOT)
        resp = self.client.get('/search/lot', follow_redirects=True)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(2, len(select(resp.data, '.datatable tbody tr')))

    def test_search_lot_deliveries_filter_by_lot(self):
        self.new_parcel(stage='l-fih', delivery_type=LOT)
        resp = self.client.get('/search/lot?lot=lot3', follow_redirects=True)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, len(select(resp.data, '.datatable tbody tr')))
        resp = self.client.get('/search/lot?lot=lot2', follow_redirects=True)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(0, len(select(resp.data, '.datatable tbody tr')))

    def test_pick_products(self):
        import json
        resp = self.client.get('/pick_products')
        self.assertEqual(6, len(json.loads(resp.data)))


class ApiTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def get_json(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return flask.json.loads(resp.data)

    def test_search_in_empty_warehouse_returns_nothing(self):
        self.assertEqual(self.get_json('/api/find_parcels'), {'parcels': []})

    def test_search_with_no_arguments_returns_all_parcels(self):
        name1 = self.new_parcel()
        name2 = self.new_parcel(country='dk')
        resp = self.get_json('/api/find_parcels')
        self.assertItemsEqual(resp['parcels'], [name1, name2])

    def test_search_with_country_argument_filters_by_country(self):
        self.new_parcel()
        name = self.new_parcel(country='dk')
        resp = self.get_json('/api/find_parcels?country=dk')
        self.assertItemsEqual(resp['parcels'], [name])

    def test_get_parcel_metadata(self):
        from gioland import warehouse
        name = self.new_parcel()
        resp = self.get_json('/api/parcel/' + name)
        with self.app.test_request_context():
            wh = warehouse.get_warehouse()
            parcel = wh.get_parcel(name)
            self.assertEqual(resp['metadata'], parcel.metadata)

from common import AppTestCase, authorization_patch, select


class ParcelMergeTests(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.parcels_path = self.wh_path / 'parcels'
        self.addCleanup(authorization_patch().stop)

    def _new_parcel(self, data):
        resp = self.client.post('/parcel/new', data=data)
        return resp.location.rsplit('/', 1)[-1]

    def _set_metadata_to_parcel(self, parcel_name, metadata={}):
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            parcel.save_metadata(metadata)

    def _set_parcel_to_merge_stage(self, parcel_name):
        self._set_metadata_to_parcel(parcel_name, {'stage': 'enh'})

    def test_view_finalize_and_merge_btn_if_parcel_is_partial(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        parcel_name = self._new_parcel(data)
        self._set_parcel_to_merge_stage(parcel_name)
        resp = self.client.get('/parcel/' + parcel_name)
        self.assertEqual(1, len(select(resp.data, 'button[name=merge]')))

    def test_view_finalize_and_merge_btn_if_parcel_is_full(self):
        parcel_name = self._new_parcel(self.PARCEL_METADATA)
        resp = self.client.get('/parcel/' + parcel_name)
        self.assertEqual(0, len(select(resp.data, 'button[name=merge]')))

    def test_view_finalize_and_merge_btn_if_parcel_stage_in_stages_for_merging(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        parcel_name = self._new_parcel(data)
        self._set_parcel_to_merge_stage(parcel_name)
        resp = self.client.get('/parcel/' + parcel_name)
        self.assertEqual(1, len(select(resp.data, 'button[name=merge]')))

    def test_view_finalize_and_merge_btn_if_parcel_stage_not_in_stages_for_merging(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        parcel_name = self._new_parcel(data)
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            parcel.save_metadata({'stage': 'ech'})
        resp = self.client.get('/parcel/' + parcel_name)
        self.assertEqual(0, len(select(resp.data, 'button[name=merge]')))

    def test_finalize_and_merge_fail_if_parcel_is_full(self):
        parcel_name = self._new_parcel(self.PARCEL_METADATA)
        self._set_parcel_to_merge_stage(parcel_name)
        resp = self.client.post('/parcel/%s/finalize' % parcel_name,
                                data={'merge': 'on'})
        self.assertEqual(400, resp.status_code)

    def test_finalize_and_merge_fail_if_parcel_stage_not_in_stages_for_merging(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        parcel_name = self._new_parcel(data)
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            parcel.save_metadata({'stage': 'ech'})
        resp = self.client.post('/parcel/%s/finalize' % parcel_name,
                                data={'merge': 'on'})
        self.assertEqual(400, resp.status_code)

    def test_merge_partials_parcels_creates_new_full_partial(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        # create a full parcel
        self._new_parcel(self.PARCEL_METADATA)
        #create 2 partial parcels
        for i in range(2):
            parcel_name = self._new_parcel(data)
            self._set_parcel_to_merge_stage(parcel_name)
        self.client.post('/parcel/%s/finalize' % parcel_name,
                         data={'merge': 'on'})
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel = self.wh.get_parcel(parcel.metadata['next_parcel'])
            new_data = dict(data)
            new_data['extent'] = 'full'
            new_data['coverage'] = ''
            self.assertDictContainsSubset(new_data, next_parcel.metadata)
            self.assertEqual('full', next_parcel.metadata['extent'])

    def test_merge_partials_parcels_fail_if_only_one_parcel(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        parcel_name = self._new_parcel(data)
        self._set_parcel_to_merge_stage(parcel_name)
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            parcel.save_metadata({'stage': 'enh'})
        resp = self.client.post('/parcel/%s/finalize' % parcel_name,
                         data={'merge': 'on'})
        self.assertEqual(400, resp.status_code)

    def test_merge_partials_parcels_closes_all_merged_parcels(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        partial_parcels_names = []
        for i in range(2):
            parcel_name = self._new_parcel(data)
            partial_parcels_names.append(parcel_name)
            self._set_parcel_to_merge_stage(parcel_name)

        self.client.post('/parcel/%s/finalize' % parcel_name,
                         data={'merge': 'on'})
        with self.app.test_request_context():
            for parcel_name in partial_parcels_names:
                parcel = self.wh.get_parcel(parcel_name)
                self.assertIn('upload_time', parcel.metadata)
                self.assertTrue(parcel.metadata['merged'])

    def test_merge_partials_parcels_link_to_next_parcel(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        partial_parcels_names = []
        for i in range(3):
            parcel_name = self._new_parcel(data)
            partial_parcels_names.append(parcel_name)
            self._set_parcel_to_merge_stage(parcel_name)
        self.client.post('/parcel/%s/finalize' % parcel_name,
                         data={'merge': 'on'})
        with self.app.test_request_context():
            next_parcel_name = self.wh.get_parcel(
                partial_parcels_names.pop(0)).metadata['next_parcel']
            for parcel_name in partial_parcels_names:
                parcel = self.wh.get_parcel(parcel_name)
                self.assertEqual(next_parcel_name,
                                 parcel.metadata['next_parcel'])

    def test_merge_partials_previous_steps(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        #create 2 partial parcels
        for i in range(2):
            data['coverage'] = 'partial_%s' % i
            parcel_name = self._new_parcel(data)
            self._set_parcel_to_merge_stage(parcel_name)
        self.client.post('/parcel/%s/finalize' % parcel_name,
                         data={'merge': 'on'})
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel = self.wh.get_parcel(parcel.metadata['next_parcel'])
            description_html = next_parcel.history[0].description_html
            self.assertEqual(2, description_html.count('Enhancement'))
            self.assertIn('(partial_0)', description_html)
            self.assertIn('(partial_1)', description_html)

    def test_merge_partials_add_prev_parcel_list(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = 'partial'
        #create 2 partial parcels
        for i in range(2):
            data['coverage'] = 'partial_%s' % i
            parcel_name = self._new_parcel(data)
            self._set_parcel_to_merge_stage(parcel_name)

        with self.app.test_request_context():
            parcel_name_diff_stage = self.wh.get_parcel(self._new_parcel(data))
            parcel_name_diff_stage.save_metadata({'stage': 'fin'})
        self.client.post('/parcel/%s/finalize' % parcel_name,
                         data={'merge': 'on'})
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel = self.wh.get_parcel(parcel.metadata['next_parcel'])
            self.assertEqual(2, len(next_parcel.metadata['prev_parcel_list']))

    def test_merge_partial_confirmation_view(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = 'partial'
        #create 2 partial parcels
        for i in range(2):
            data['coverage'] = 'partial_%s' % i
            parcel_name = self._new_parcel(data)
            self._set_parcel_to_merge_stage(parcel_name)
        resp = self.client.get('/parcel/%s/finalize?merge=on' % parcel_name)
        self.assertEqual(200, resp.status_code)
        count = len(select(resp.data, '#parcel-finalize-and-merge-form'))
        self.assertEqual(1, count)

    def test_merge_partial_confirmation_view_with_empty_results(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        parcel_name = self._new_parcel(data)
        self._set_parcel_to_merge_stage(parcel_name)
        resp = self.client.get('/parcel/%s/finalize?merge=on' % parcel_name)
        self.assertEqual(200, resp.status_code)
        count = len(select(resp.data, '#parcel-finalize-and-merge-form'))
        self.assertEqual(0, count)

    def test_merge_partials_workflow_overview_history(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = 'partial'
        #create 2 partial parcels
        for i in range(2):
            data['coverage'] = 'partial_%s' % i
            parcel_name = self._new_parcel(data)
            self._set_parcel_to_merge_stage(parcel_name)

        self.client.post('/parcel/%s/finalize' % parcel_name,
                         data={'merge': 'on'})

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            self.assertIn('next_parcel', parcel.metadata)
            next_parcel = parcel.metadata['next_parcel']
            resp = self.client.get('/parcel/%s/chain' % next_parcel)
            self.assertEqual(200, resp.status_code)
            merged_table = select(resp.data, '#parcels-merged-history')
            self.assertEqual(1, len(merged_table))
            merged_table_rows = select(resp.data, '#parcels-merged-history tbody tr')
            self.assertEqual(2, len(merged_table_rows))

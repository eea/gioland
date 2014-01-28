from common import AppTestCase, authorization_patch, select


class ParcelMergeTests(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.parcels_path = self.wh_path / 'parcels'
        self.addCleanup(authorization_patch().stop)

    def _new_parcel(self, data):
        resp = self.client.post('/parcel/new', data=data)
        return resp.location.rsplit('/', 1)[-1]

    def test_view_finalize_and_merge_btn_if_parcel_is_partial(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        parcel_name = self._new_parcel(data)
        resp = self.client.get('/parcel/' + parcel_name)
        self.assertEqual(1, len(select(resp.data, 'button[name=merge]')))

    def test_view_finalize_and_merge_btn_if_parcel_is_full(self):
        parcel_name = self._new_parcel(self.PARCEL_METADATA)
        resp = self.client.get('/parcel/' + parcel_name)
        self.assertEqual(0, len(select(resp.data, 'button[name=merge]')))

    def test_finalize_and_merge_fail_if_parcel_is_full(self):
        parcel_name = self._new_parcel(self.PARCEL_METADATA)
        resp = self.client.post('/parcel/%s/finalize' % parcel_name,
                                data={'merge': 'on'})
        self.assertEqual(400, resp.status_code)

    def test_merge_partials_parcels_creates_new_full_partial(self):
        data = dict(self.PARCEL_METADATA)
        data['extent'] = data['coverage'] = 'partial'
        self._new_parcel(self.PARCEL_METADATA)
        for i in range(5):
            parcel_name = self._new_parcel(data)

        resp = self.client.post('/parcel/%s/finalize' % parcel_name,
                                data={'merge': 'on'})


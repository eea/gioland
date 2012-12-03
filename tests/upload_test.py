import json
from StringIO import StringIO
from common import AppTestCase, authorization_patch, select


class UploadTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.parcels_path = self.wh_path / 'parcels'
        self.addCleanup(authorization_patch().stop)

    def try_upload(self, name, filename='data.gml'):
        data = {
            'resumableFilename': filename,
            'resumableIdentifier': 'data_gml',
            'resumableTotalSize': '11',
        }

        chunk_1_data = dict(data)
        chunk_1_data['resumableChunkSize'] = '3'
        chunk_1_data['resumableChunkNumber'] = '1'
        chunk_1_data['file'] = (StringIO('teh'), filename)

        chunk_2_data = dict(data)
        chunk_2_data['resumableChunkSize'] = '8'
        chunk_2_data['resumableChunkNumber'] = '2'
        chunk_2_data['file'] = (StringIO('map data'), filename)

        # upload chunks
        resp_1 = self.client.post('/parcel/%s/chunk' % name, data=chunk_1_data)
        resp_2 = self.client.post('/parcel/%s/chunk' % name, data=chunk_2_data)

        if (resp_1.status_code, resp_2.status_code) == (200, 200):
            # finalize upload
            resp_3 = self.client.post('/parcel/%s/finalize_upload' % name,
                                      data=data)
            if resp_3.status_code != 200:
                self.fail('finalize upload failed')
            return True
        elif (resp_1.status_code, resp_2.status_code) == (403, 403):
            return False
        elif (resp_1.status_code, resp_2.status_code) == (415, 415):
            return False
        else:
            self.fail('unexpected http status code')

    def try_upload_chunk(self, name, filename='data.gml'):
        data = {
            'resumableFilename': filename,
            'resumableIdentifier': 'data_gml',
            'resumableTotalSize': '11',
        }

        chunk_1_data = dict(data)
        chunk_1_data['resumableChunkSize'] = '3'
        chunk_1_data['resumableChunkNumber'] = '1'
        chunk_1_data['file'] = (StringIO('teh'), filename)

        resp = self.client.post('/parcel/%s/chunk' % name,  data=chunk_1_data)
        if resp.status_code == 200:
            return True
        else:
            return False

    def try_upload_file(self, name, filename='data.gml'):
        data = {'file': (StringIO('teh map data'), filename)}
        resp = self.client.post('/parcel/%s/file' % name, data=data,
                                follow_redirects=True)
        return resp

    def create_parcel_at_stage(self, stage='sch'):
        with self.app.test_request_context():
            parcel = self.wh.new_parcel()
            parcel.save_metadata({'stage': stage})
        return parcel

    def test_upload_file(self):
        parcel = self.create_parcel_at_stage()
        resp = self.try_upload_file(parcel.name)
        self.assertTrue(302, resp.status_code)

    def test_reupload_file_not_allowed(self):
        parcel = self.create_parcel_at_stage()
        self.try_upload_file(parcel.name)
        resp = self.try_upload_file(parcel.name)
        self.assertEqual(1, len(select(resp.data, '.system-msg')))

    def test_upload_file_on_final_stage_forbidden(self):
        parcel = self.create_parcel_at_stage(stage='fva')
        resp = self.try_upload_file(parcel.name)
        self.assertEqual(403, resp.status_code)

    def test_upload_chunks(self):
        parcel = self.create_parcel_at_stage()
        self.assertTrue(self.try_upload(parcel.name))

    def test_reupload_chunk_not_allowed(self):
        parcel = self.create_parcel_at_stage()
        self.try_upload(parcel.name)
        self.assertFalse(self.try_upload(parcel.name))

    def test_upload_chunk_on_final_stage_forbidden(self):
        parcel = self.create_parcel_at_stage(stage='fva')
        self.assertFalse(self.try_upload(parcel.name))

    def test_delete_file(self):
        parcel = self.create_parcel_at_stage()
        resp = self.client.post('/parcel/%s/file/%s/delete' %
                                (parcel.name, 'data.gml'))
        self.assertEqual(302, resp.status_code)

    def test_finalized_parcel_forbids_deletion(self):
        with self.app.test_request_context():
            parcel = self.wh.new_parcel()
            parcel.save_metadata({'stage': 'fva'})
            parcel.finalize()
        resp = self.client.post('/parcel/%s/file/%s/delete' % (parcel.name,
                                                               'data.gml'))
        self.assertEqual(403, resp.status_code)

    def test_files_view(self):
        parcel = self.create_parcel_at_stage()
        self.try_upload(parcel.name)
        resp = self.client.get('/parcel/%s/files' % parcel.name)
        self.assertEqual(1, len(select(resp.data, 'ul li')))

    def test_check_chunk_view(self):
        parcel = self.create_parcel_at_stage()
        self.try_upload_chunk(parcel.name)
        url = '/parcel/%s/chunk?resumableFilename=data.gml'\
              '&resumableIdentifier=data_gml&resumableTotalSize=11'\
              '&resumableChunkNumber=1&resumableChunkSize=3' % parcel.name
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)

    def test_upload_chunk_create_temp_folder(self):
        parcel = self.create_parcel_at_stage()
        self.try_upload_chunk(parcel.name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel.name)
            dirs = parcel.get_path().dirs()
            self.assertEqual(1, len(dirs))

    def test_finalize_parcel_remove_temp_folders(self):
        resp = self.client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]

        self.try_upload_chunk(parcel_name)
        resp = self.client.post('/parcel/%s/finalize' % parcel_name)

        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            dirs = parcel.get_path().dirs()
            self.assertEqual(0, len(dirs))

    def finalize_upload_fails_if_chunks_are_not_uploaded(self):
        data = {
            'resumableFilename': 'data.gml',
            'resumableIdentifier': 'data_gml',
            'resumableTotalSize': '11',
        }

        parcel = self.create_parcel_at_stage()
        self.try_upload_chunk(parcel.name)
        resp = self.client.post('/parcel/%s/finalize_upload' % parcel.name,
                                data=data)
        self.assertEqual(200, resp.status_code)
        response = json.loads(resp.data)
        self.assertEqual('error', response['status'])

    def create_chunks_for_parcel(self, parcel):
        parcel_path = parcel.get_path()
        temp = parcel_path.joinpath('temp')
        temp.makedirs()

        i = 0
        while i < 25:
            with open(temp.joinpath(str(i)), 'wb') as chunk:
                chunk.write(str(i))
            i += 1
        return temp

    def test_create_file_from_chunks(self):
        from parcel import create_file_from_chunks
        resp = self.client.post('/parcel/new', data=self.PARCEL_METADATA)
        parcel_name = resp.location.rsplit('/', 1)[-1]
        with self.app.test_request_context():
            parcel = self.wh.get_parcel(parcel_name)
            parcel_path = parcel.get_path()
            temp = self.create_chunks_for_parcel(parcel)
            create_file_from_chunks(parcel, temp, 'data.txt')

            self.assertEqual(1, len(parcel_path.listdir()))

            with open(parcel_path.joinpath('data.txt'), 'rb') as data:
                self.assertEqual(''.join(map(str, range(0, 25))), data.read())

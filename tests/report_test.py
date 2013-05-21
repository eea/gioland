from common import AppTestCase, authorization_patch, select
from StringIO import StringIO


class ReportTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.addCleanup(authorization_patch().stop)

    def test_report_new(self):
        data = dict(self.REPORT_METADATA,
                    file=(StringIO('ze file'), 'doc.pdf'))
        resp = self.client.post('/country/report/new', data=data)
        self.assertEqual(302, resp.status_code)
        self.assertIsNotNone(resp.location)
        with self.app.test_request_context():
            try:
                self.assertTrue(self.wh.get_report(1))
            except KeyError:
                self.fail('Report with id %s not saved' % 1)

    def test_report_saves_user_selected_metadata(self):
        data = dict(self.REPORT_METADATA,
                    file=(StringIO('ze file'), 'doc.pdf'),
                    bogus='not here')
        resp = self.client.post('/country/report/new', data=data)
        self.assertEqual(302, resp.status_code)

        with self.app.test_request_context():
            report = self.wh.get_report(1)
            self.assertFalse(getattr(report, 'bogus', False))

    def test_report_fail_if_corrupted_metadata(self):
        data = dict(self.REPORT_METADATA)
        data['country'] = 'eau'
        resp = self.client.post('/country/report/new', data=data)
        self.assertEqual(400, resp.status_code)

    def test_report_saves_file(self):
        data = dict(self.REPORT_METADATA,
                    file=(StringIO('ze file'), 'doc.pdf'))
        resp = self.client.post('/country/report/new', data=data)
        self.assertEqual(302, resp.status_code)

        with self.app.test_request_context():
            [filename] = [str(i.name)
                          for i in self.wh.reports_path.walk()]
            self.assertEqual('CDR_BE_FOR_V01.pdf', filename)

    def test_report_filename(self):
        data = dict(self.REPORT_METADATA,
                    file=(StringIO('ze file'), 'doc.pdf'))
        resp = self.client.post('/country/report/new', data=data)
        self.assertEqual(302, resp.status_code)

        with self.app.test_request_context():
            report = self.wh.get_report(1)
            self.assertEqual('CDR_BE_FOR_V01.pdf', report.filename)

    def test_report_filename_increment_version(self):
        data = dict(self.REPORT_METADATA)
        data['file'] = (StringIO('ze file'), 'doc.pdf')
        self.client.post('/country/report/new', data=data)
        data['file'] = (StringIO('ze file'), 'doc.pdf')
        self.client.post('/country/report/new', data=data)
        with self.app.test_request_context():
            report_1 = self.wh.get_report(1)
            report_2 = self.wh.get_report(2)
            self.assertEqual('CDR_BE_FOR_V01.pdf', report_1.filename)
            self.assertEqual('CDR_BE_FOR_V02.pdf', report_2.filename)

    def test_report_upload_files_fails(self):
        data = dict(self.REPORT_METADATA,
                    file=(StringIO('ze file'), 'image.jpg'))
        resp = self.client.post('/country/report/new', data=data)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, len(select(resp.data, '.system-msg')))

from common import AppTestCase, authorization_patch, select

from gioland.definitions import LOT


class UploadTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):

        self.addCleanup(authorization_patch().stop)

    def test_index_delivers_lots(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        rows = select(response.data, "h2  + div > div")
        self.assertEqual(5, len(rows))

    def test_lot_page_displays_related_deliveries(self):
        self.new_parcel(delivery_type=LOT)
        response = self.client.get('/lot/' + self.LOT_METADATA['lot'])
        self.assertEqual(response.status_code, 200)
        rows = select(response.data, "tbody > tr")
        self.assertEqual(1, len(rows))
        response = self.client.get('/lot/lot1')
        rows = select(response.data, "tbody > tr")
        self.assertEqual(0, len(rows))

    def test_lot_page_displays_correct_number_of_stages(self):
        self.new_parcel(delivery_type=LOT)
        response = self.client.get('/lot/' + self.LOT_METADATA['lot'])
        column_titles = select(response.data, "thead > tr:last-child > th")
        self.assertEqual(6, len(column_titles))

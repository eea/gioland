import unittest
import tempfile
from path import path


BAD_METADATA_VALUES = [
    {2: 'a'},
    {'\xcc': 'a'},
    {'a': 2},
    {'a': '\xcc'},
]


class ParcelTest(unittest.TestCase):

    def setUp(self):
        import warehouse
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp/'warehouse'
        self.parcels_path = self.wh_path/'parcels'
        wh_connector = warehouse.WarehouseConnector(self.wh_path)
        self.wh, warehouse_cleanup = wh_connector.get_warehouse()
        self.addCleanup(warehouse_cleanup)

    def new_parcel(self):
        return path(tempfile.mkdtemp(dir=self.tmp))

    def test_warehouse_initially_empty(self):
        self.assertEqual(len(list(self.wh.get_all_parcels())), 0)

    def test_saving_parcel_increases_warehouse_count(self):
        self.wh.add_parcel(self.new_parcel())
        self.assertEqual(len(list(self.wh.get_all_parcels())), 1)

    def test_saving_parcel_creates_warehouse_folder(self):
        self.assertEqual(len(self.parcels_path.listdir()), 0)
        self.wh.add_parcel(self.new_parcel())
        self.assertEqual(len(self.parcels_path.listdir()), 1)

    def test_get_parcel_filesystem_path(self):
        self.wh.add_parcel(self.new_parcel())
        [wh_parcel_path] = self.parcels_path.listdir()
        [parcel] = self.wh.get_all_parcels()
        self.assertEqual(parcel.get_fs_path(), wh_parcel_path)

    def test_saving_parcel_moves_folder_contents(self):
        new_parcel_path = self.new_parcel()
        (new_parcel_path/'one').write_text("hello world")

        self.wh.add_parcel(new_parcel_path)

        [wh_parcel_path] = self.parcels_path.listdir()
        self.assertEqual(wh_parcel_path.listdir(), [wh_parcel_path/'one'])
        self.assertEqual((wh_parcel_path/'one').text(), "hello world")

    def test_arbitrary_parcel_metadata_is_saved(self):
        self.wh.add_parcel(self.new_parcel(), {'a': 'b', 'hello': 'world'})
        [parcel] = list(self.wh.get_all_parcels())
        self.assertEqual(parcel.metadata, {'a': 'b', 'hello': 'world'})

    def test_invalid_metadata_raises_exception(self):
        for bad in BAD_METADATA_VALUES:
            self.assertRaises(ValueError, self.wh.add_parcel,
                              self.new_parcel(), bad)


class ZodbPersistenceTest(unittest.TestCase):

    def setUp(self):
        import warehouse
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp/'warehouse'
        self.parcels_path = self.wh_path/'parcels'
        self.wh_connector = warehouse.WarehouseConnector(self.wh_path)

    def test_saved_parcel_files_are_persisted(self):
        new_parcel_path = path(tempfile.mkdtemp(dir=self.tmp))
        (new_parcel_path/'one').write_text("hello world")
        with self.wh_connector.warehouse() as wh1:
            wh1.add_parcel(new_parcel_path)
            self.assertEqual(len(list(wh1.get_all_parcels())), 1)
            [parcel_1] = wh1.get_all_parcels()
            parcel_path_1 = parcel_1.get_fs_path()
            import transaction; transaction.commit()

        with self.wh_connector.warehouse() as wh2:
            self.assertEqual(len(list(wh2.get_all_parcels())), 1)
            [parcel] = wh2.get_all_parcels()
            parcel_path = parcel.get_fs_path()
            self.assertEqual(parcel_path, parcel_path_1)
            self.assertEqual(parcel_path.listdir(), [parcel_path/'one'])
            self.assertEqual((parcel_path/'one').text(), "hello world")

    def test_saved_parcel_metadata_is_persisted(self):
        new_parcel_path = path(tempfile.mkdtemp(dir=self.tmp))
        with self.wh_connector.warehouse() as wh1:
            wh1.add_parcel(new_parcel_path, {'hello': 'world'})
            self.assertEqual(len(list(wh1.get_all_parcels())), 1)
            import transaction
            transaction.commit()

        with self.wh_connector.warehouse() as wh2:
            [parcel] = wh2.get_all_parcels()
            self.assertEqual(parcel.metadata, {'hello': 'world'})


class UploadTest(unittest.TestCase):

    def setUp(self):
        import warehouse
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp/'warehouse'
        self.uploads_path = self.wh_path/'uploads'
        self.wh_connector = warehouse.WarehouseConnector(self.wh_path)

    def get_warehouse(self):
        wh, warehouse_cleanup = self.wh_connector.get_warehouse()
        self.addCleanup(warehouse_cleanup)
        return wh

    def test_new_upload_creates_folder(self):
        wh = self.get_warehouse()
        upload = wh.new_upload()
        self.assertTrue(upload.get_path().isdir())
        self.assertIs(wh.get_upload(upload.name), upload)

    def test_upload_can_list_its_files(self):
        wh = self.get_warehouse()
        upload = wh.new_upload()
        upload_path = upload.get_path()
        file1_path = upload_path/'somefile.txt'
        file2_path = upload_path/'otherfile.txt'
        file1_path.write_text('one')
        file2_path.write_text('two')
        self.assertItemsEqual(upload.get_files(), [file1_path, file2_path])

    def test_upload_stores_metadata(self):
        wh = self.get_warehouse()
        upload = wh.new_upload()
        upload.save_metadata({'a': 'b', 'x': 'y'})
        self.assertDictContainsSubset({'a': 'b', 'x': 'y'}, upload.metadata)

    def test_upload_verifies_metadata_keys_and_values(self):
        wh = self.get_warehouse()
        upload = wh.new_upload()
        for bad in BAD_METADATA_VALUES:
            self.assertRaises(ValueError, upload.save_metadata, bad)

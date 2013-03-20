import unittest
import tempfile
from datetime import datetime
from contextlib import contextmanager
from path import path
import transaction
from common import AppTestCase


BAD_METADATA_VALUES = [
    {2: 'a'},
    {'\xcc': 'a'},
    {'a': 2},
    {'a': '\xcc'},
]


def setUpModule(self):
    import warehouse
    self.warehouse = warehouse


class ParcelTest(unittest.TestCase):

    def setUp(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp / 'warehouse'
        self.parcels_path = self.wh_path / 'parcels'
        wh_connector = warehouse.WarehouseConnector(self.wh_path)
        self.wh, warehouse_cleanup = wh_connector.open_warehouse()
        self.addCleanup(warehouse_cleanup)

    def test_warehouse_initially_empty(self):
        self.assertEqual(len(list(self.wh.get_all_parcels())), 0)

    def test_saving_parcel_increases_warehouse_count(self):
        self.wh.new_parcel()
        self.assertEqual(len(list(self.wh.get_all_parcels())), 1)

    def test_new_parcel_returns_the_parcel(self):
        parcel = self.wh.new_parcel()
        self.assertEqual([parcel], list(self.wh.get_all_parcels()))

    def test_get_parcel_returns_the_right_parcel(self):
        parcel1 = self.wh.new_parcel()
        parcel2 = self.wh.new_parcel()
        self.assertIs(self.wh.get_parcel(parcel1.name), parcel1)

    def test_saving_parcel_creates_warehouse_folder(self):
        self.assertEqual(len(self.parcels_path.listdir()), 0)
        self.wh.new_parcel()
        self.assertEqual(len(self.parcels_path.listdir()), 1)

    def test_parcel_folder_has_correct_permissions(self):
        parcel = self.wh.new_parcel()
        self.assertEqual(parcel.get_path().stat().st_mode, 040755)

    def test_get_parcel_filesystem_path(self):
        self.wh.new_parcel()
        [wh_parcel_path] = self.parcels_path.listdir()
        [parcel] = self.wh.get_all_parcels()
        self.assertEqual(parcel.get_path(), wh_parcel_path)

    def test_arbitrary_parcel_metadata_is_saved(self):
        parcel = self.wh.new_parcel()
        parcel.save_metadata({'a': 'b', 'hello': 'world'})
        [parcel] = list(self.wh.get_all_parcels())
        self.assertEqual(parcel.metadata, {'a': 'b', 'hello': 'world'})

    def test_invalid_metadata_raises_exception(self):
        parcel = self.wh.new_parcel()
        for bad in BAD_METADATA_VALUES:
            self.assertRaises(ValueError, parcel.save_metadata, bad)


class ZodbPersistenceTest(unittest.TestCase):

    def setUp(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp / 'warehouse'
        self.parcels_path = self.wh_path / 'parcels'
        self.wh_connector = warehouse.WarehouseConnector(self.wh_path)

    @contextmanager
    def warehouse(self):
        warehouse, cleanup = self.wh_connector.open_warehouse()
        try:
            yield warehouse
        finally:
            cleanup()

    def test_saved_parcel_files_are_persisted(self):
        with self.warehouse() as wh1:
            wh1.new_parcel()
            self.assertEqual(len(list(wh1.get_all_parcels())), 1)
            [parcel_1] = wh1.get_all_parcels()
            parcel_path_1 = parcel_1.get_path()
            (parcel_path_1 / 'one').write_text("hello world")
            transaction.commit()

        with self.warehouse() as wh2:
            self.assertEqual(len(list(wh2.get_all_parcels())), 1)
            [parcel] = wh2.get_all_parcels()
            parcel_path = parcel.get_path()
            self.assertEqual(parcel_path, parcel_path_1)
            self.assertEqual(parcel_path.listdir(), [parcel_path / 'one'])
            self.assertEqual((parcel_path / 'one').text(), "hello world")

    def test_saved_parcel_metadata_is_persisted(self):
        with self.warehouse() as wh1:
            parcel = wh1.new_parcel()
            parcel.save_metadata({'hello': 'world'})
            self.assertEqual(len(list(wh1.get_all_parcels())), 1)
            transaction.commit()

        with self.warehouse() as wh2:
            [parcel] = wh2.get_all_parcels()
            self.assertEqual(parcel.metadata, {'hello': 'world'})


class UploadTest(unittest.TestCase):

    def setUp(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp / 'warehouse'
        self.uploads_path = self.wh_path / 'uploads'
        self.wh_connector = warehouse.WarehouseConnector(self.wh_path)

    def get_warehouse(self):
        wh, warehouse_cleanup = self.wh_connector.open_warehouse()
        self.addCleanup(warehouse_cleanup)
        return wh

    def test_new_upload_creates_folder(self):
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        self.assertTrue(upload.get_path().isdir())
        self.assertIs(wh.get_parcel(upload.name), upload)

    def test_upload_can_list_its_files(self):
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        upload_path = upload.get_path()
        file1_path = upload_path / 'somefile.txt'
        file2_path = upload_path / 'otherfile.txt'
        file1_path.write_text('one')
        file2_path.write_text('two')
        self.assertItemsEqual(upload.get_files(), [file1_path, file2_path])

    def test_upload_stores_metadata(self):
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        upload.save_metadata({'a': 'b', 'x': 'y'})
        self.assertDictContainsSubset({'a': 'b', 'x': 'y'}, upload.metadata)

    def test_upload_verifies_metadata_keys_and_values(self):
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        for bad in BAD_METADATA_VALUES:
            self.assertRaises(ValueError, upload.save_metadata, bad)


class UploadFinalizationTest(unittest.TestCase):

    def setUp(self):
        self.tmp = path(tempfile.mkdtemp())
        self.addCleanup(self.tmp.rmtree)
        self.wh_path = self.tmp / 'warehouse'
        self.uploads_path = self.wh_path / 'uploads'
        self.wh_connector = warehouse.WarehouseConnector(self.wh_path)

    def get_warehouse(self):
        wh, warehouse_cleanup = self.wh_connector.open_warehouse()
        self.addCleanup(warehouse_cleanup)
        return wh

    def test_finalize_upload_creates_parcel(self):
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        upload.finalize()
        self.assertIs(wh.get_parcel(upload.name), upload)

    def test_finalize_upload_preserves_metadata(self):
        metadata = {'hello': 'world'}
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        upload.save_metadata(metadata)
        upload.finalize()
        self.assertDictContainsSubset(metadata, upload.metadata)

    def test_finalize_upload_preserves_files(self):
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        (upload.get_path() / 'somefile.txt').write_text('the contents')
        upload.finalize()
        file_path = upload.get_path() / 'somefile.txt'
        self.assertTrue(file_path.isfile())
        self.assertEqual(file_path.text(), 'the contents')

    def test_finalize_upload_marks_timestamp(self):
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        t0 = datetime.utcnow().isoformat()
        upload.finalize()
        t1 = datetime.utcnow().isoformat()
        self.assertTrue(t0 <= upload.metadata['upload_time'] <= t1)

    def test_finalize_upload_changes_uploading_flag(self):
        wh = self.get_warehouse()
        upload = wh.new_parcel()
        self.assertTrue(upload.uploading)
        upload.finalize()
        self.assertFalse(upload.uploading)

    def test_checksum(self):
        import hashlib

        map_data = 'teh map data'
        hexdigest = hashlib.md5(map_data).hexdigest()

        path = (self.tmp / 'checksum')
        path.makedirs()
        (path / 'data.gml').write_text(map_data)

        self.assertEqual([(u'data.gml', hexdigest)], warehouse.checksum(path))

    def test_finalize_checksum(self):
        wh = self.get_warehouse()
        parcel = wh.new_parcel()
        parcel.finalize()
        transaction.commit()
        self.assertIsInstance(parcel.checksum, list)


class DeleteParcelTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        import flask
        reqctx = self.app.test_request_context()
        reqctx.push()
        flask.g.username = 'testuser'
        self.addCleanup(reqctx.pop)

    def test_delete_removes_parcel_from_list(self):
        parcel = self.wh.new_parcel()
        parcel_name = parcel.name
        self.wh.delete_parcel(parcel_name)
        self.assertRaises(KeyError, self.wh.get_parcel, parcel_name)
        self.assertEqual(list(self.wh.get_all_parcels()), [])

    def test_delete_does_not_remove_folder(self):
        parcel = self.wh.new_parcel()
        parcel_path = parcel.get_path()
        self.wh.delete_parcel(parcel.name)
        self.assertTrue(parcel_path.isdir())

    def create_initial_parcel(self):
        parcel = self.wh.new_parcel()
        parcel.save_metadata({
            'stage': 'int',
            'country': 'dk',
            'theme': 'imp-deg',
            'extent': 'full',
            'projection': 'eur',
            'resolution': '20m',
            'coverage': '',
        })
        return parcel

    def test_delete_removes_subsequent_parcels(self):
        from parcel import finalize_parcel, delete_parcel_and_followers
        parcel = self.create_initial_parcel()
        finalize_parcel(self.wh, parcel, reject=False)
        parcel2 = self.wh.get_parcel(parcel.metadata['next_parcel'])
        delete_parcel_and_followers(self.wh, parcel2.name)
        self.assertRaises(KeyError, self.wh.get_parcel, parcel2.name)

    def test_delete_keeps_previous_parcels(self):
        from parcel import finalize_parcel, delete_parcel_and_followers
        parcel = self.create_initial_parcel()
        finalize_parcel(self.wh, parcel, reject=False)
        parcel2 = self.wh.get_parcel(parcel.metadata['next_parcel'])
        finalize_parcel(self.wh, parcel2, reject=False)
        parcel3 = self.wh.get_parcel(parcel2.metadata['next_parcel'])
        delete_parcel_and_followers(self.wh, parcel2.name)
        self.assertIs(self.wh.get_parcel(parcel.name), parcel)

    def test_delete_leaves_previous_parcel_unfinalized(self):
        from parcel import finalize_parcel, delete_parcel_and_followers
        parcel = self.create_initial_parcel()
        finalize_parcel(self.wh, parcel, reject=False)
        parcel2 = self.wh.get_parcel(parcel.metadata['next_parcel'])
        delete_parcel_and_followers(self.wh, parcel2.name)
        self.assertTrue(parcel.uploading)
        self.assertNotIn('next_parcel', parcel.metadata)
        self.assertNotIn('upload_time', parcel.metadata)

    def test_delete_adds_comment_on_previous_parcel(self):
        from parcel import finalize_parcel, delete_parcel_and_followers
        parcel = self.create_initial_parcel()
        finalize_parcel(self.wh, parcel, reject=False)
        parcel2 = self.wh.get_parcel(parcel.metadata['next_parcel'])
        delete_parcel_and_followers(self.wh, parcel2.name)
        self.assertIn('deleted', parcel.history[-1].description_html)
        self.assertIn(parcel2.name, parcel.history[-1].description_html)


class ParcelHistoryTest(unittest.TestCase):

    def test_history_initially_empty(self):
        parcel = warehouse.Parcel(None, 'asdf')
        self.assertEqual(parcel.history, [])

    def test_add_item_to_history(self):
        parcel = warehouse.Parcel(None, 'asdf')
        utcnow = datetime.utcnow()
        parcel.add_history_item("Big bang", utcnow, 'somebody', "first thing")
        self.assertEqual(len(parcel.history), 1)
        self.assertEqual(parcel.history[0].title, "Big bang")
        self.assertEqual(parcel.history[0].time, utcnow)
        self.assertEqual(parcel.history[0].actor, 'somebody')
        self.assertEqual(parcel.history[0].description_html, "first thing")

    def test_history_item_links_back_to_parcel(self):
        parcel = warehouse.Parcel(None, 'asdf')
        parcel.add_history_item("Big bang", datetime.utcnow(),
                                'somebody', "first thing")
        [item] = parcel.history
        self.assertIs(item.parcel, parcel)

    def test_history_item_receives_incremental_id(self):
        parcel = warehouse.Parcel(None, 'asdf')
        parcel.add_history_item("one", datetime.utcnow(), 'somebody', "")
        parcel.add_history_item("two", datetime.utcnow(), 'somebody', "")
        [item1, item2] = parcel.history
        self.assertEqual(item1.title, "one")
        self.assertEqual(item2.title, "two")
        self.assertEqual(item1.id_, 1)
        self.assertEqual(item2.id_, 2)

    def test_history_item_returned(self):
        parcel = warehouse.Parcel(None, 'asdf')
        item = parcel.add_history_item("Big bang", datetime.utcnow(),
                                       'somebody', "first thing")
        self.assertEqual(parcel.history, [item])


class RequesetTransactionTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def test_commit_on_success(self):
        @self.app.route('/change_something', methods=['POST'])
        def change_something():
            wh = warehouse.get_warehouse()
            wh.test_value = 'asdf'
            return 'ok'

        self.client.post('/change_something')

        with self.app.test_request_context():
            wh = warehouse.get_warehouse()
            self.assertEqual(wh.test_value, 'asdf')

    def test_rollback_on_error(self):
        @self.app.route('/change_something', methods=['POST'])
        def change_something():
            wh = warehouse.get_warehouse()
            wh.test_value = 'asdf'
            raise ValueError

        self.assertRaises(ValueError, self.client.post, '/change_something')

        with self.app.test_request_context():
            wh = warehouse.get_warehouse()
            self.assertFalse(hasattr(wh, 'test_value'))


class FilesystemSymlinkTest(AppTestCase):

    CREATE_WAREHOUSE = True

    @property
    def symlinks_root(self):
        return self.wh_path / 'tree'

    def create_parcel(self, stage, finalize_and_link=False):
        with self.app.test_request_context():
            wh = warehouse.get_warehouse()
            parcel = wh.new_parcel()
            parcel.save_metadata(self.PARCEL_METADATA)
            parcel.save_metadata({'stage': stage})
            if finalize_and_link:
                parcel.finalize()
                parcel.link_in_tree()
            return parcel.name

    def symlink_path(self, metadata, *extra):
        from definitions import EDITABLE_METADATA
        symlink_path = self.symlinks_root
        for name in EDITABLE_METADATA:
            symlink_path = symlink_path / metadata[name]
        for bit in extra:
            symlink_path = symlink_path / str(bit)
        return symlink_path

    def test_new_parcel_leaves_no_symlink(self):
        stage = 'enh'
        self.create_parcel(stage)
        symlink_path = self.symlink_path(self.PARCEL_METADATA, stage, 1)
        self.assertFalse(symlink_path.islink())
        self.assertEqual(self.symlinks_root.listdir(), [])

    def test_finalized_parcel_has_symlink(self):
        stage = 'enh'
        name = self.create_parcel(stage, True)
        symlink_path = self.symlink_path(self.PARCEL_METADATA, stage, 1)
        self.assertTrue(symlink_path.islink())
        self.assertEqual(symlink_path.readlink(),
                         self.wh_path / 'parcels' / name)

    def test_second_finalized_parcel_with_same_metadata_has_symlink(self):
        stage = 'enh'
        name1 = self.create_parcel(stage, True)
        name2 = self.create_parcel(stage, True)
        symlink_path_2 = self.symlink_path(self.PARCEL_METADATA, stage, 2)
        self.assertTrue(symlink_path_2.islink())
        self.assertEqual(symlink_path_2.readlink(),
                         self.wh_path / 'parcels' / name2)

    def test_symlink_generator_skips_over_broken_symlinks(self):
        stage = 'enh'
        name1 = self.create_parcel(stage, True)
        with self.app.test_request_context():
            wh = warehouse.get_warehouse()
            wh.delete_parcel(name1)
        name2 = self.create_parcel(stage, True)
        symlink_path_2 = self.symlink_path(self.PARCEL_METADATA, stage, 2)
        self.assertTrue(symlink_path_2.islink())
        self.assertEqual(symlink_path_2.readlink(),
                         self.wh_path / 'parcels' / name2)

    def test_repeated_calls_to_link_in_tree_dont_create_more_links(self):
        stage = 'enh'
        name = self.create_parcel(stage, True)
        parent_path = self.symlink_path(self.PARCEL_METADATA, stage)
        with self.app.test_request_context():
            wh = warehouse.get_warehouse()
            parcel = wh.get_parcel(name)
            parcel.link_in_tree()

        self.assertEqual(parent_path.listdir(), [parent_path / '1'])

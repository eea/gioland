import tempfile
from contextlib import contextmanager
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from BTrees.OOBTree import OOBTree
from persistent import Persistent
import transaction
from path import path


def _ensure_unicode(thing):
    if isinstance(thing, str):
        try:
            return thing.decode('ascii')
        except UnicodeDecodeError:
            raise ValueError("Metadata may not contain non-ascii bytestrings")
    elif isinstance(thing, unicode):
        return thing
    else:
        raise ValueError("Metadata keys must be strings")


def _ensure_dir(dir_path):
    if not dir_path.isdir():
        dir_path.makedirs()
    return dir_path


class Parcel(Persistent):

    def __init__(self, warehouse, name, metadata):
        self._warehouse = warehouse
        self.name = name
        self.metadata = PersistentMapping()
        for key, value in metadata.iteritems():
            self.metadata[_ensure_unicode(key)] = _ensure_unicode(value)

    def get_fs_path(self):
        return self._warehouse.parcels_path/self.name


class Upload(Persistent):

    def __init__(self, warehouse, name):
        self._warehouse = warehouse
        self.name = name

    def get_path(self):
        return self._warehouse.uploads_path/self.name

    def get_files(self):
        return self.get_path().listdir()


class Warehouse(Persistent):

    # `fs_path` is injected at runtime, not stored in the database
    __slots__ = ('fs_path', '__dict__')

    def __init__(self):
        self._parcels = PersistentList()
        self._uploads = OOBTree()

    @property
    def parcels_path(self):
        return self.fs_path/'parcels'

    @property
    def uploads_path(self):
        return self.fs_path/'uploads'

    def add_parcel(self, parcel_src, metadata={}):
        parcel_path = path(tempfile.mkdtemp(prefix='', dir=self.parcels_path))
        for item_path in parcel_src.listdir():
            wh_item_path = parcel_path/item_path.name
            item_path.rename(wh_item_path)

        parcel = Parcel(self, parcel_path.name, metadata)
        self._parcels.append(parcel)

    def get_all_parcels(self):
        return iter(self._parcels)

    def new_upload(self):
        upload_path = path(tempfile.mkdtemp(prefix='', dir=self.uploads_path))
        upload = Upload(self, upload_path.name)
        self._uploads[upload.name] = upload
        return upload

    def get_upload(self, name):
        return self._uploads[name]


class WarehouseConnector(object):

    def __init__(self, fs_path):
        self._fs_path = path(fs_path)
        self._db = None

    def _get_db(self):
        if self._db is None:
            from ZODB.DB import DB
            from ZODB.FileStorage import FileStorage
            filestorage_path = _ensure_dir(self._fs_path/'filestorage')
            storage = FileStorage(str(filestorage_path/'Data.fs'))
            self._db = DB(storage)
        return self._db

    def get_warehouse(self):
        conn = self._get_db().open()
        transaction.begin()

        def cleanup():
            transaction.abort()
            conn.close()

        zodb_root = conn.root()
        if 'warehouse' not in zodb_root:
            zodb_root['warehouse'] = Warehouse()

        warehouse = zodb_root['warehouse']
        warehouse.fs_path = _ensure_dir(self._fs_path)
        _ensure_dir(warehouse.parcels_path)
        _ensure_dir(warehouse.uploads_path)

        return warehouse, cleanup

    @contextmanager
    def warehouse(self):
        warehouse, cleanup = self.get_warehouse()
        try:
            yield warehouse
        finally:
            cleanup()

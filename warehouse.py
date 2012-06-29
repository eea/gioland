import tempfile
from contextlib import contextmanager
from datetime import datetime
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

    @property
    def uploading(self):
        return 'upload_time' not in self.metadata

    def __init__(self, warehouse, name):
        self._warehouse = warehouse
        self.name = name
        self.metadata = PersistentMapping()

    def save_metadata(self, new_metadata):
        for key, value in new_metadata.iteritems():
            self.metadata[_ensure_unicode(key)] = _ensure_unicode(value)

    def get_path(self):
        return self._warehouse.parcels_path/self.name

    def get_files(self):
        return self.get_path().listdir()

    def finalize(self):
        self.save_metadata({'upload_time': datetime.utcnow().isoformat()})


class Warehouse(Persistent):

    # `fs_path` is injected at runtime, not stored in the database
    __slots__ = ('fs_path', '__dict__')

    def __init__(self):
        self._parcels = OOBTree()

    @property
    def parcels_path(self):
        return self.fs_path/'parcels'

    def new_parcel(self):
        parcel_path = path(tempfile.mkdtemp(prefix='', dir=self.parcels_path))
        parcel = Parcel(self, parcel_path.name)
        self._parcels[parcel.name] = parcel
        return parcel

    def get_parcel(self, name):
        return self._parcels[name]

    def get_all_parcels(self):
        return iter(self._parcels.values())

    def get_upload(self, name):
        return self.get_parcel(name)


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

        return warehouse, cleanup

    @contextmanager
    def warehouse(self):
        warehouse, cleanup = self.get_warehouse()
        try:
            yield warehouse
        finally:
            cleanup()

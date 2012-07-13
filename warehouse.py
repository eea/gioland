import tempfile
from contextlib import contextmanager
from datetime import datetime
import logging, logging.handlers
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from BTrees.OOBTree import OOBTree
from persistent import Persistent
import transaction
from path import path


log = logging.getLogger(__name__)

LOGGING_FORMAT = '[%(asctime)s] %(levelname)s %(message)s'
log_number = 1


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
        self.history = PersistentList()

    def save_metadata(self, new_metadata):
        self._warehouse.logger.info("Metadata update for %r: %r",
                                    self.name, new_metadata)
        for key, value in new_metadata.iteritems():
            self.metadata[_ensure_unicode(key)] = _ensure_unicode(value)

    def get_path(self):
        return self._warehouse.parcels_path/self.name

    def get_files(self):
        return self.get_path().listdir()

    def finalize(self):
        self._warehouse.logger.info("Finalizing %r", self.name)
        self.save_metadata({'upload_time': datetime.utcnow().isoformat()})

    def add_history_item(self, *args, **kwargs):
        item = ParcelHistoryItem(self, *args, **kwargs)
        item.id_ = len(self.history) + 1
        self.history.append(item)
        return item


class ParcelHistoryItem(Persistent):

    def __init__(self, parcel, title, time, actor, description_html):
        self.parcel = parcel
        self.title = title
        self.time = time
        self.actor = actor
        self.description_html = description_html


class Warehouse(Persistent):

    _volatile_attributes = {}

    @property
    def fs_path(self):
        return self._volatile_attributes[id(self)]['fs_path']

    @property
    def logger(self):
        return self._volatile_attributes[id(self)]['logger']

    def __init__(self):
        self._parcels = OOBTree()

    @property
    def parcels_path(self):
        return self.fs_path/'parcels'

    def new_parcel(self):
        parcel_path = path(tempfile.mkdtemp(prefix='', dir=self.parcels_path))
        parcel = Parcel(self, parcel_path.name)
        self._parcels[parcel.name] = parcel
        self.logger.info("New parcel %r", parcel.name)
        return parcel

    def delete_parcel(self, name):
        self.logger.info("Deleting parcel %r", name)
        parcel = self._parcels.pop(name)
        parcel.get_path().rmtree()

    def get_parcel(self, name):
        return self._parcels[name]

    def get_all_parcels(self):
        return iter(self._parcels.values())


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
        global log_number

        conn = self._get_db().open()
        transaction.begin()
        handler = logging.handlers.WatchedFileHandler(self._fs_path/'activity.log')
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(LOGGING_FORMAT))

        def cleanup():
            transaction.abort()
            warehouse.logger.removeHandler(handler)
            del warehouse._volatile_attributes[id(warehouse)]
            conn.close()

        zodb_root = conn.root()
        if 'warehouse' not in zodb_root:
            zodb_root['warehouse'] = Warehouse()

        warehouse = zodb_root['warehouse']
        warehouse._volatile_attributes[id(warehouse)] = {
            'fs_path': _ensure_dir(self._fs_path),
            'logger': log.getChild('con%d' % log_number),
        }
        warehouse.logger.setLevel(logging.INFO)
        log_number += 1
        warehouse.logger.addHandler(handler)
        _ensure_dir(warehouse.parcels_path)

        return warehouse, cleanup

    @contextmanager
    def warehouse(self):
        warehouse, cleanup = self.get_warehouse()
        try:
            yield warehouse
        finally:
            cleanup()

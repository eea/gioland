import hashlib
import logging
import logging.handlers
import tempfile
from datetime import datetime

import transaction
from BTrees.OOBTree import OOBTree
from path import path
from persistent import Persistent
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping

from gioland.definitions import COUNTRY
from gioland.definitions import METADATA, COUNTRY_EXCLUDE_METADATA, STREAM, STREAM_EXCLUDE_METADATA

log = logging.getLogger(__name__)

LOGGING_FORMAT = '[%(asctime)s] %(levelname)s %(message)s'
LOG_FILE_NAME = 'activity.log'
BLOCK_SIZE = 8192
log_number = 1


def _current_user():
    default = '[nobody]'
    try:
        import flask
        return flask.g.username or default
    except:
        return default


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


def checksum(path):
    files = []
    for p in path.listdir():
        if not p.isfile():
            continue
        md5 = hashlib.md5()
        with open(p, 'rb') as f:
            while True:
                data = f.read(BLOCK_SIZE)
                if not data:
                    break
                md5.update(data)
            files.append((p.name, md5.hexdigest()))
    return files


class Parcel(Persistent):

    def __init__(self, warehouse, name):
        self._warehouse = warehouse
        self.name = name
        self.metadata = PersistentMapping()
        self.history = PersistentList()

    @property
    def uploading(self):
        return 'upload_time' not in self.metadata

    @property
    def file_uploading(self):
        from gioland.parcel import _get_stages_for_parcel
        DELIVERY_STAGES, _ = _get_stages_for_parcel(self)
        stage = DELIVERY_STAGES.get(self.metadata.get('stage'), {})
        return stage.get('file_uploading', False)

    def save_metadata(self, new_metadata):
        self._warehouse.logger.info("Metadata update for %r: %r (user %s)",
                                    self.name, new_metadata, _current_user())
        for key, value in new_metadata.iteritems():
            if key == 'prev_parcel_list':
                self.metadata[_ensure_unicode(key)] = \
                    [_ensure_unicode(v) for v in value]
            else:
                self.metadata[_ensure_unicode(key)] = _ensure_unicode(value)

    def get_path(self):
        return self._warehouse.parcels_path / self.name

    def get_files(self):
        for f in self.get_path().listdir():
            if not f.name.startswith('.') and not f.isdir():
                yield f

    def finalize(self):
        self._warehouse.logger.info("Finalizing %r (user %s)",
                                    self.name, _current_user())
        self.checksum = checksum(self.get_path())
        self.save_metadata({'upload_time': datetime.utcnow().isoformat()})

    def link_in_tree(self):
        symlink_path = self._warehouse.tree_path
        if self.metadata['delivery_type'] == COUNTRY:
            filtered_metadata = tuple(set(METADATA) ^ set(COUNTRY_EXCLUDE_METADATA))
        elif self.metadata['delivery_type'] == STREAM:
            filtered_metadata = tuple(set(METADATA) ^ set(STREAM_EXCLUDE_METADATA))
        else:
            filtered_metadata = METADATA

        for name in filtered_metadata:
            if name in self.metadata:
                symlink_path = symlink_path / self.metadata[name]
        symlink_path.makedirs_p()
        target_path = self.get_path()
        for c in xrange(1, 101):
            symlink_path_c = symlink_path / str(c)
            if not symlink_path_c.islink():
                target_path.symlink(symlink_path_c)
                return symlink_path_c
            else:
                if symlink_path_c.readlink() == target_path:
                    return
        else:
            raise RuntimeError("Unable to create symlink, tried 100 numbers")

    def add_history_item(self, title, time, actor, description_html):
        item = ParcelHistoryItem(self, title, time, actor, description_html)
        item.id_ = len(self.history) + 1
        self.history.append(item)
        return item

    @property
    def last_modified(self):
        return self.history[-1].time


class ParcelHistoryItem(Persistent):

    def __init__(self, parcel, title, time, actor, description_html):
        self.parcel = parcel
        self.title = title
        self.time = time
        self.actor = actor
        self.description_html = description_html


class Report(Persistent):

    def __init__(self, lot, filename=None):
        self.lot = lot

    @property
    def name(self):
        return '%s' % self.lot


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
        self._reports = OOBTree()

    @property
    def parcels_path(self):
        return self.fs_path / 'parcels'

    @property
    def reports_path(self):
        return self.fs_path / 'reports'

    @property
    def tree_path(self):
        return self.fs_path / 'tree'

    def new_parcel(self):
        parcel_path = path(tempfile.mkdtemp(prefix='', dir=self.parcels_path))
        parcel_path.chmod(0755)
        parcel = Parcel(self, parcel_path.name)
        self._parcels[parcel.name] = parcel
        self.logger.info("New parcel %r (user %s)",
                         parcel.name, _current_user())
        return parcel

    def delete_parcel(self, name):
        self.logger.info("Deleting parcel %r (user %s)", name, _current_user())
        self._parcels.pop(name)

    def get_parcel(self, name):
        return self._parcels[name]

    def get_all_parcels(self):
        return iter(self._parcels.values())

    def new_report(self, lot):
        report = Report(lot)
        pk = max(self._reports.keys() or [0]) + 1
        report.pk = pk
        report.user = _current_user()
        self._reports[pk] = report
        self.logger.info("New report for %r (user %s)",
                         report.name, _current_user())
        return report

    def get_report(self, report_id):
        return self._reports[report_id]

    def get_all_reports(self):
        return iter(self._reports.values())

    def delete_report(self, report_id):
        self._reports.pop(report_id)


class WarehouseConnector(object):

    def __init__(self, fs_path):
        self._fs_path = path(fs_path)
        self._db = None

    def _get_db(self):
        if self._db is None:
            from ZODB.DB import DB
            from ZODB.FileStorage import FileStorage
            filestorage_path = _ensure_dir(self._fs_path / 'filestorage')
            storage = FileStorage(str(filestorage_path / 'Data.fs'))
            self._db = DB(storage)
        return self._db

    def open_warehouse(self):
        global log_number

        conn = self._get_db().open()
        transaction.begin()
        handler = logging.handlers.WatchedFileHandler(
            self._fs_path / LOG_FILE_NAME)
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
        _ensure_dir(warehouse.reports_path)
        _ensure_dir(warehouse.tree_path)

        return warehouse, cleanup

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None


def get_warehouse():
    import flask
    if not hasattr(flask.g, 'warehouse'):
        wc = flask.current_app.extensions['warehouse_connector']
        warehouse, cleanup = wc.open_warehouse()
        flask.g.warehouse = warehouse
        flask.g.warehouse_cleanup = cleanup
    return flask.g.warehouse


def _cleanup_warehouse(err=None):
    import flask
    if hasattr(flask.g, 'warehouse'):
        if err is None:
            transaction.get().note(flask.request.url)
            transaction.commit()
        else:
            transaction.abort()
        flask.g.warehouse_cleanup()
        del flask.g.warehouse
        del flask.g.warehouse_cleanup


def initialize_app(app):
    import flask
    from gioland import auth

    if 'WAREHOUSE_PATH' not in app.config:
        return

    connector = WarehouseConnector(app.config['WAREHOUSE_PATH'])
    app.extensions['warehouse_connector'] = connector
    app.teardown_request(_cleanup_warehouse)

    @app.route('/zodb_pack', methods=['GET', 'POST'])
    def zodb_pack():
        if not auth.authorize(['ROLE_ADMIN']):
            return flask.abort(403)

        db = connector._get_db()

        if flask.request.method == 'POST':
            db.pack(days=float(flask.request.form['days']))
            return flask.redirect(flask.url_for('zodb_pack'))

        return flask.render_template('zodb_pack.html', db=db)

    @app.route('/zodb_undo', methods=['GET', 'POST'])
    def zodb_undo():
        if not auth.authorize(['ROLE_ADMIN']):
            return flask.abort(403)

        db = connector._get_db()

        if flask.request.method == 'POST':
            undo = flask.request.form.getlist('undo')
            db.undoMultiple(undo)
            transaction.get().note("undo %d" % len(undo))
            transaction.commit()
            flask.flash("Rolled back %d transactions" % len(undo), 'system')
            return flask.redirect(flask.request.url)

        count = flask.request.args.get('count', 20, type=int)
        return flask.render_template('zodb_undo.html', db=db, count=count)

    @app.template_filter('to_datetime')
    def to_datetime(t):
        return datetime.fromtimestamp(t)

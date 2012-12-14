import time
from functools import wraps
import logging
from contextlib import contextmanager
from werkzeug.contrib.cache import NullCache, SimpleCache
import flask
from dateutil import tz
from zc.lockfile import LockFile, LockError
from definitions import DATE_FORMAT


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def cached(timeout):
    def decorator(func):
        @wraps(func)
        def wrapper(*args):
            cache = get_cache()
            key = '%s.%s %r' % (func.__module__, func.__name__, args)
            rv = cache.get(key)
            if rv is None:
                rv = func(*args)
                cache.set(key, rv, timeout=timeout)
            return rv
        return wrapper
    return decorator


def get_cache():
    return flask.current_app.extensions['gioland-cache']


def initialize_app(app):
    if app.config['CACHING']:
        cache = SimpleCache()
    else:
        cache = NullCache()
    app.extensions['gioland-cache'] = cache


def format_datetime(value, format_name='long'):
    """ Formats a datetime according to the given format. """
    timezone = flask.current_app.config.get("TIME_ZONE")
    if timezone:
        from_zone = tz.gettz("UTC")
        to_zone = tz.gettz(timezone)
        # Tell the datetime object that it's in UTC time zone since
        # datetime objects are 'naive' by default
        value = value.replace(tzinfo=from_zone)
        # Convert time zone
        value = value.astimezone(to_zone)
    return value.strftime(DATE_FORMAT[format_name])


LOCK_TIMEOUT = 5.0


def get_lock():
    lock_path = flask.current_app.config['LOCK_FILE_PATH']
    t0 = time.time()
    while True:
        if time.time() - t0 > LOCK_TIMEOUT:
            raise RuntimeError("Timeout while getting exclusive lock")

        try:
            return LockFile(lock_path)

        except LockError:
            log.debug("Lock busy, sleeping ...")
            time.sleep(0.2)


def exclusive_lock(func=None):
    if func is None:
        # we're being used as context manager
        @contextmanager
        def locker():
            lock = get_lock()
            t0 = time.time()
            try:
                yield
            finally:
                lock.close()
                duration = time.time() - t0
                log.debug("Held lock for %.3f" % duration)
        return locker()

    @wraps(func)
    def wrapper(*args, **kwargs):
        with exclusive_lock():
            return func(*args, **kwargs)

    return wrapper

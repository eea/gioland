from functools import wraps
from werkzeug.contrib.cache import NullCache, SimpleCache
import flask
from dateutil import tz
from definitions import DATE_FORMAT


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

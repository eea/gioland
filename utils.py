from functools import wraps
from werkzeug.contrib.cache import NullCache, SimpleCache
import flask


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

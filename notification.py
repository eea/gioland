import logging
from xmlrpclib import ServerProxy
import flask
import blinker
from definitions import (COUNTRIES, STAGES, THEMES, PROJECTIONS, RESOLUTIONS,
                         EXTENTS, RDF_URI)


COUNTRY_MAP    = dict(COUNTRIES)
STAGE_MAP      = dict(STAGES)
THEME_MAP      = dict(THEMES)
PROJECTION_MAP = dict(PROJECTIONS)
RESOLUTION_MAP = dict(RESOLUTIONS)
EXTENT_MAP     = dict(EXTENTS)


log = logging.getLogger(__name__)

signals = blinker.Namespace()
uns_notification_sent = signals.signal("uns-notification-sent")


def get_uns_proxy():
    app = flask.current_app
    url = "http://{0}:{1}@uns.eionet.europa.eu/rpcrouter".format(
            app.config['UNS_LOGIN_USERNAME'], app.config['UNS_LOGIN_PASSWORD'])
    return ServerProxy(url).UNSService


def create_channel(title="GioLand",
                   description="High Resolution Layers workflow updates"):
    uns = get_uns_proxy()
    print uns.createChannel(title, description)


def can_subscribe(user_id):
    app = flask.current_app
    channel_id = app.config['UNS_CHANNEL_ID']
    uns = get_uns_proxy()
    return bool(uns.canSubscribe(channel_id, user_id or ''))


def subscribe(user_id):
    app = flask.current_app
    channel_id = app.config['UNS_CHANNEL_ID']
    uns = get_uns_proxy()
    uns.makeSubscription(channel_id, user_id, [])


def prepare_notification_rdf(item):
    app = flask.current_app

    parcel = item.parcel
    metadata = parcel.metadata
    parcel_url = (app.config['BASE_URL'] +
                  flask.url_for('parcel.view', name=parcel.name))
    event_id = "%s#history-%d" % (parcel_url, item.id_)

    event_data = [
        (RDF_URI['rdf_type'], RDF_URI['parcel_event']),
        (RDF_URI['title'], "%s (%s)" % (item.title, parcel.name)),
        (RDF_URI['identifier'], parcel_url),
        (RDF_URI['date'], item.time.strftime('%Y-%b-%d %H:%M:%S')),
        (RDF_URI['locality'], COUNTRY_MAP.get(metadata['country'], "")),
        (RDF_URI['actor'], item.actor),
        (RDF_URI['stage'], STAGE_MAP.get(metadata['stage'], "")),
        (RDF_URI['theme'], THEME_MAP.get(metadata['theme'], "")),
        (RDF_URI['projection'], PROJECTION_MAP.get(metadata['projection'], "")),
        (RDF_URI['resolution'], RESOLUTION_MAP.get(metadata['resolution'], "")),
        (RDF_URI['extent'], EXTENT_MAP.get(metadata['extent'], "")),
    ]

    return [[event_id, pred, obj] for pred, obj in event_data]


def notify(item):
    rdf_triples = prepare_notification_rdf(item)
    app = flask.current_app
    channel_id = app.config['UNS_CHANNEL_ID']
    send_notifications = not (app.testing or
                              app.config.get('UNS_SUPPRESS_NOTIFICATIONS'))
    if send_notifications:
        log.info("Notification via UNS for %s", rdf_triples[0][0])
        uns = get_uns_proxy()
        uns.sendNotification(channel_id, rdf_triples)
    else:
        log.info("Notification via UNS for %s (not sent)", rdf_triples[0][0])
    uns_notification_sent.send(app, item=item, rdf_triples=rdf_triples)

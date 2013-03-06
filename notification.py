import logging
from xmlrpclib import ServerProxy
import flask
import blinker
from definitions import RDF_URI, UNS_FIELD_DEFS, METADATA
import auth
from utils import format_datetime


metadata_rdf_fields = [(field['rdf_uri'], field['name'], dict(field['range']))
                       for field in UNS_FIELD_DEFS
                       if field['name'] in METADATA]

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

signals = blinker.Namespace()
uns_notification_sent = signals.signal("uns-notification-sent")


def get_uns_proxy():
    app = flask.current_app
    url = "http://{0}:{1}@uns.eionet.europa.eu/rpcrouter".format(
            app.config['UNS_LOGIN_USERNAME'], app.config['UNS_LOGIN_PASSWORD'])
    return ServerProxy(url).UNSService


def create_channel(title="GIO Land",
                   description="High Resolution Layers workflow updates"):
    uns = get_uns_proxy()
    print uns.createChannel(title, description)


def can_subscribe(user_id):
    app = flask.current_app
    channel_id = app.config['UNS_CHANNEL_ID']
    uns = get_uns_proxy()
    return bool(uns.canSubscribe(channel_id, user_id or ''))


def subscribe(user_id, filters):
    app = flask.current_app

    rdf_filters_map = {}
    for rdf_uri, metadata_name, value_map in metadata_rdf_fields:
        if metadata_name in filters:
            rdf_filters_map[rdf_uri] = value_map[filters[metadata_name]]

    decision = filters.get('decision')
    if decision is not None:
        rdf_filters_map[RDF_URI['decision']] = decision

    rdf_filters = []
    if rdf_filters_map:
        rdf_filters.append(rdf_filters_map)

    log.info("Subscribing user %r with filters %r", user_id, rdf_filters)

    channel_id = app.config['UNS_CHANNEL_ID']
    uns = get_uns_proxy()
    uns.makeSubscription(channel_id, user_id, rdf_filters)


def prepare_notification_rdf(item, event_type, rejected=None):
    app = flask.current_app

    parcel = item.parcel
    metadata = parcel.metadata
    parcel_url = (app.config['BASE_URL'] +
                  flask.url_for('parcel.view', name=parcel.name))
    event_id = "%s#history-%d" % (parcel_url, item.id_)
    full_name = auth.ldap_full_name(item.actor)

    title = item.title
    if full_name:
        title += " by %s" % full_name
    title += " (stage reference: %s)" % parcel.name

    [event_type_def] = [f for f in UNS_FIELD_DEFS if f['name'] == 'event_type']
    event_type_values = [k for k, v in event_type_def['range']]
    if event_type not in event_type_values:
        raise RuntimeError("Unknown event type %r (not in %r)" %
                           (event_type, event_type_values))

    event_data = [
        (RDF_URI['rdf_type'], RDF_URI['parcel_event']),
        (RDF_URI['title'], title),
        (RDF_URI['identifier'], parcel_url),
        (RDF_URI['date'], format_datetime(item.time, 'uns')),
        (RDF_URI['actor'], item.actor),
        (RDF_URI['actor_name'], full_name),
        (RDF_URI['event_type'], event_type),
    ]

    if rejected is not None:
        decision = 'rejected' if rejected else 'accepted'
        event_data.append((RDF_URI['decision'], decision))

    for rdf_uri, metadata_name, value_map in metadata_rdf_fields:
        value = value_map.get(metadata[metadata_name], "")
        event_data.append((rdf_uri, value))

    return [[event_id, pred, obj] for pred, obj in event_data]


def notify(item, event_type, rejected=None):
    send_notification(prepare_notification_rdf(item, event_type, rejected))


def send_notification(rdf_triples):
    app = flask.current_app
    channel_id = app.config['UNS_CHANNEL_ID']
    send_notifications = not (app.testing or
                              app.config.get('UNS_SUPPRESS_NOTIFICATIONS'))
    if send_notifications:
        log.info("Notification via UNS for %s", rdf_triples[0][0])
        log.debug("Notification data: %r", rdf_triples)
        uns = get_uns_proxy()
        uns.sendNotification(channel_id, rdf_triples)
    else:
        log.info("Notification via UNS for %s (not sent)", rdf_triples[0][0])
    uns_notification_sent.send(app, rdf_triples=rdf_triples)

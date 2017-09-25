from contextlib import contextmanager
from datetime import datetime

from common import AppTestCase, record_events, authorization_patch
from dateutil import tz
from mock import Mock, patch, call

from gioland.definitions import COUNTRY


def setUpModule(self):
    from gioland import notification
    self.notification = notification


class NotificationDeliveryTest(AppTestCase):

    def setUp(self):
        from gioland import warehouse

        self.app.config['BASE_URL'] = 'http://example.com'

        self.utcnow = datetime.utcnow()
        parcel = warehouse.Parcel(Mock(), 'asdf')
        parcel.save_metadata({
            'country': 'it',
            'lot': 'lot3',
            'stage': 'c-fsc',
            'product': 'grl',
            'resolution': '20m',
            'delivery_type': COUNTRY,
        })
        parcel.add_history_item("Now hear this", self.utcnow,
                                'somewho', "descr")
        [self.item] = parcel.history

    def test_notification_calls_uns(self):

        with record_events(notification.uns_notification_sent) as events:
            with self.app.test_request_context():
                notification.notify(self.item, 'comment')

        self.assertEqual(len(events), 1)

    def test_notification_rdf(self):
        from gioland.definitions import RDF_URI

        zone = 'Asia/Tokyo'
        self.app.config['TIME_ZONE'] = zone
        now = (self.utcnow.replace(tzinfo=tz.gettz('UTC'))
                          .astimezone(tz.gettz(zone)))

        with self.app.test_request_context():
            rdf_triples = notification.prepare_notification_rdf(self.item,
                                                                'comment')

        [event_id] = list(set(s for s, p, o in rdf_triples))
        self.assertEqual(event_id, "http://example.com/parcel/asdf#history-1")

        rdf_data = {p: o for s, p, o in rdf_triples}
        self.assertDictContainsSubset({
            RDF_URI['date']: now.strftime('%Y-%b-%d %H:%M:%S'),
            RDF_URI['actor']: "somewho",
            RDF_URI['locality']: "Italy",
            RDF_URI['stage']: "Final Semantic check",
            RDF_URI['title']: "Now hear this (stage reference: asdf)",
            RDF_URI['identifier']: "http://example.com/parcel/asdf",
            RDF_URI['product']: "Grassland",
            RDF_URI['resolution']: "20 m",
            RDF_URI['event_type']: "comment",
        }, rdf_data)

    @contextmanager
    def record_uns_calls(self):
        with patch('gioland.notification.get_uns_proxy') as mock_get_uns_proxy:
            sendNotification = mock_get_uns_proxy.return_value.sendNotification
            with self.app.test_request_context():
                yield sendNotification.mock_calls

    def test_uns_not_called_in_tests(self):
        with self.record_uns_calls() as uns_calls:
            notification.notify(self.item, 'comment')
        self.assertEqual(len(uns_calls), 0)

    def test_uns_not_called_if_suppressed(self):
        with self.record_uns_calls() as uns_calls:
            self.app.config['UNS_SUPPRESS_NOTIFICATIONS'] = True
            try:
                notification.notify(self.item, 'comment')
            finally:
                self.app.config['UNS_SUPPRESS_NOTIFICATIONS'] = False
        self.assertEqual(len(uns_calls), 0)

    def test_uns_called_if_not_in_tests(self):
        with self.record_uns_calls() as uns_calls:
            self.app.config['TESTING'] = False
            try:
                notification.notify(self.item, 'comment')
            finally:
                self.app.config['TESTING'] = True
        self.assertEqual(len(uns_calls), 1)


def rdfdata(event):
    (sender, extra) = event
    return dict((p, o) for (s, p, o) in extra['rdf_triples'])


class NotificationTriggerTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.addCleanup(authorization_patch().stop)

    def test_notification_not_triggered_on_new_parcel(self):
        with record_events(notification.uns_notification_sent) as events:
            resp = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(events, [])

    def test_notification_triggered_once_on_finalize_parcel(self):
        from gioland.definitions import RDF_URI
        resp_1 = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        self.assertEqual(resp_1.status_code, 302)
        parcel_name = resp_1.location.rsplit('/', 1)[-1]

        with record_events(notification.uns_notification_sent) as events:
            resp_2 = self.client.post('/parcel/%s/finalize' % parcel_name)
            self.assertEqual(resp_2.status_code, 302)

        self.assertEqual(len(events), 1)
        event_rdf = rdfdata(events[0])
        self.assertEqual(event_rdf[RDF_URI['title']],
                         ("Service provider upload finished"
                          " (stage reference: %s)" % parcel_name))
        self.assertNotIn(RDF_URI['decision'], event_rdf)

    @patch('gioland.parcel.authorize_for_parcel', Mock(return_value=True))
    def test_parcel_rejection_triggers_accept_notification(self):
        from gioland.definitions import RDF_URI
        resp_1 = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        self.assertEqual(resp_1.status_code, 302)
        parcel1_name = resp_1.location.rsplit('/', 1)[-1]

        resp_2 = self.client.post('/parcel/%s/finalize' % parcel1_name)
        self.assertEqual(resp_2.status_code, 302)
        with self.app.test_request_context():
            parcel1 = self.wh.get_parcel(parcel1_name)
            parcel2_name = parcel1.metadata['next_parcel']

        with record_events(notification.uns_notification_sent) as events:
            resp_3 = self.client.post('/parcel/%s/finalize' % parcel2_name)

        self.assertEqual(resp_3.status_code, 302)
        self.assertEqual(len(events), 1)
        event_rdf = rdfdata(events[0])
        self.assertEqual(event_rdf[RDF_URI['decision']], "accepted")

    @patch('gioland.parcel.authorize_for_parcel', Mock(return_value=True))
    def test_parcel_rejection_triggers_rejection_notification(self):
        from gioland.definitions import RDF_URI
        resp_1 = self.client.post('/parcel/new/country', data=self.PARCEL_METADATA)
        self.assertEqual(resp_1.status_code, 302)
        parcel1_name = resp_1.location.rsplit('/', 1)[-1]

        resp_2 = self.client.post('/parcel/%s/finalize' % parcel1_name)
        self.assertEqual(resp_2.status_code, 302)
        with self.app.test_request_context():
            parcel1 = self.wh.get_parcel(parcel1_name)
            parcel2_name = parcel1.metadata['next_parcel']

        with record_events(notification.uns_notification_sent) as events:
            resp_3 = self.client.post('/parcel/%s/finalize' % parcel2_name,
                                      data={'reject': 'on'})

        self.assertEqual(resp_3.status_code, 302)
        self.assertEqual(len(events), 1)
        event_rdf = rdfdata(events[0])
        self.assertEqual(event_rdf[RDF_URI['decision']], "rejected")


class NotificationSubscriptionTest(AppTestCase):

    def setUp(self):
        self.channel_id = '1234'
        self.app.config['UNS_CHANNEL_ID'] = self.channel_id

    @patch('gioland.notification.get_uns_proxy')
    def test_subscribe_calls_to_uns(self, mock_proxy):
        self.client.post('/subscribe')
        self.assertEqual(mock_proxy.return_value.makeSubscription.mock_calls,
                         [call(self.channel_id, 'somebody', [])])

    @patch('gioland.notification.get_uns_proxy')
    def test_subscribe_with_filters_passes_filters_to_uns(self, mock_proxy):
        from gioland.definitions import RDF_URI

        self.client.post('/subscribe', data={
            'country': 'dk',
            'extent': 'partial',
            'resolution': '20m',
            'product': 'fty',
        })

        ok_filters = [{
            RDF_URI['locality']: "Denmark",
            RDF_URI['extent']: "Partial",
            RDF_URI['resolution']: "20 m",
            RDF_URI['product']: "Forest Type",
        }]
        self.assertEqual(mock_proxy.return_value.makeSubscription.mock_calls,
                         [call(self.channel_id, 'somebody', ok_filters)])

import unittest
from datetime import datetime
from contextlib import contextmanager
from mock import Mock, patch
from common import create_mock_app, record_events


def setUpModule(self):
    import notification; self.notification = notification


class NotificationDeliveryTest(unittest.TestCase):

    def setUp(self):
        import warehouse

        self.app = create_mock_app()
        self.app.config['BASE_URL'] = 'http://example.com'

        self.utcnow = datetime.utcnow()
        parcel = warehouse.Parcel(Mock(), 'asdf')
        parcel.save_metadata({
            'country': 'it',
            'stage': 'enh',
            'theme': 'grc',
            'projection': 'ntl',
            'resolution': '25m',
            'extent': 'partial',
        })
        parcel.add_history_item("Now hear this", self.utcnow,
                                'somewho', "descr")
        [self.item] = parcel.history

    def test_notification_calls_uns(self):

        with record_events(notification.uns_notification_sent) as events:
            with self.app.test_request_context():
                notification.notify(self.item)

        self.assertEqual(len(events), 1)

    def test_notification_rdf(self):
        from definitions import RDF_URI

        with self.app.test_request_context():
            rdf_triples = notification.prepare_notification_rdf(self.item)

        [event_id] = list(set(s for s, p, o in rdf_triples))
        self.assertEqual(event_id, "http://example.com/parcel/asdf#history-1")

        rdf_data = {p: o for s, p, o in rdf_triples}
        self.assertDictContainsSubset({
            RDF_URI['date']: self.utcnow.strftime('%Y-%b-%d %H:%M:%S'),
            RDF_URI['locality']: "Italy",
            RDF_URI['actor']: "somewho",
            RDF_URI['stage']: "Enhancement",
            RDF_URI['title']: "Now hear this (asdf)",
            RDF_URI['identifier']: "http://example.com/parcel/asdf",
            RDF_URI['theme']: "Grassland Cover",
            RDF_URI['projection']: "National",
            RDF_URI['resolution']: "25m",
            RDF_URI['extent']: "Partial",
        }, rdf_data)

    @contextmanager
    def record_uns_calls(self):
        with patch('notification.get_uns_proxy') as mock_get_uns_proxy:
            sendNotification = mock_get_uns_proxy.return_value.sendNotification
            with self.app.test_request_context():
                yield sendNotification.mock_calls

    def test_uns_not_called_in_tests(self):
        with self.record_uns_calls() as uns_calls:
            notification.notify(self.item)
        self.assertEqual(len(uns_calls), 0)

    def test_uns_not_called_if_suppressed(self):
        with self.record_uns_calls() as uns_calls:
            self.app.config['UNS_SUPPRESS_NOTIFICATIONS'] = True
            try:
                notification.notify(self.item)
            finally:
                self.app.config['UNS_SUPPRESS_NOTIFICATIONS'] = False
        self.assertEqual(len(uns_calls), 0)

    def test_uns_called_if_not_in_tests(self):
        with self.record_uns_calls() as uns_calls:
            self.app.config['TESTING'] = False
            try:
                notification.notify(self.item)
            finally:
                self.app.config['TESTING'] = True
        self.assertEqual(len(uns_calls), 1)

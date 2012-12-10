# -*- coding: utf-8 -*-
# Copyright (c) 2010-2012 Infrae. All rights reserved.
# See also LICENSE.txt

import unittest

import infrae.wsgi
from infrae.wsgi.testing import BrowserLayer, Browser
from infrae.testing import get_event_names
from zope.security.management import queryInteraction


class WSGILayer(BrowserLayer):
    default_users = {'admin': ['Manager']}


FunctionalLayer = WSGILayer(infrae.wsgi)


class FunctionalTestCase(unittest.TestCase):
    """Functional testing.
    """
    layer = FunctionalLayer

    def setUp(self):
        self.browser = Browser()
        self.browser.handleErrors = True
        self.browser.raiseHttpErrors = False
        get_event_names()       # Clear setup events

    def test_default_view(self):
        self.browser.open('http://localhost')
        self.assertEqual(self.browser.title, 'Zope QuickStart')
        self.assertEqual(self.browser.status, '200 OK')
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationAfterRender',
             'PublicationBeforeCommit',
             'PublicationSuccess',
             'EndRequestEvent'])
        self.assertIs(queryInteraction(), None)

    def test_notfound_view(self):
        self.browser.open('http://localhost/nowhere')
        self.assertEqual(self.browser.status, '404 Not Found')
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationBeforeError',
             'PublicationAfterRender',
             'PublicationBeforeAbort',
             'PublicationFailure',
             'EndRequestEvent'])
        self.assertIs(queryInteraction(), None)

    def test_debug_view(self):
        # You must be authenticated to access the debug view.
        self.browser.open('http://localhost/debugzope.html')
        self.assertEqual(self.browser.status, '401 Unauthorized')
        self.browser.addHeader('Authorization', 'Basic admin:admin')
        self.browser.reload()
        self.assertEqual(self.browser.status, '200 OK')

    def test_log_view(self):
        # You must be authenticated to access the log view.
        self.browser.open('http://localhost/errorlog.html')
        self.assertEqual(self.browser.status, '401 Unauthorized')
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationBeforeCommit',
             'PublicationSuccess',
             'EndRequestEvent'])
        self.assertIs(queryInteraction(), None)

        self.browser.addHeader('Authorization', 'Basic admin:admin')
        self.browser.reload()
        self.assertEqual(self.browser.status, '200 OK')
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationAfterRender',
             'PublicationBeforeCommit',
             'PublicationSuccess',
             'EndRequestEvent'])
        self.assertIs(queryInteraction(), None)

    def test_abort(self):
        self.browser.open('http://localhost/abort.html')
        self.assertEqual(self.browser.status, '400 Bad Request')
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationBeforeAbort',
             'PublicationFailure',
             'EndRequestEvent'])
        self.assertIs(queryInteraction(), None)

    def test_conflict(self):
        self.browser.open('http://localhost/conflict.html')
        self.assertEqual(self.browser.status, '503 Service Unavailable')
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationBeforeAbort',
             'PublicationFailure'] * 4 +
            ['EndRequestEvent'] * 4)
        self.assertIs(queryInteraction(), None)

    def test_failed_conflict(self):
        self.browser.open('http://localhost/failed_conflict.html')
        self.assertEqual(self.browser.status, '500 Internal Server Error')
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationBeforeAbort',
             'PublicationFailure',
             'PublicationStart',
             'PublicationAfterTraversal',
             'PublicationBeforeError',
             'PublicationAfterRender',
             'PublicationBeforeAbort',
             'PublicationFailure',
             'EndRequestEvent',
             'EndRequestEvent'])
        self.assertIs(queryInteraction(), None)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FunctionalTestCase))
    return suite

# -*- coding: utf-8 -*-
# Copyright (c) 2010-2012 Infrae. All rights reserved.
# See also LICENSE.txt

import unittest

import infrae.wsgi
from infrae.wsgi.testing import BrowserLayer, Browser


class InfraeWSGILayer(BrowserLayer):
    default_users = {'admin': ['Manager']}


FunctionalLayer = InfraeWSGILayer(infrae.wsgi)


class FunctionalTestCase(unittest.TestCase):
    """Functional testing.
    """
    layer = FunctionalLayer

    def setUp(self):
        self.browser = Browser()
        self.browser.handleErrors = True
        self.browser.raiseHttpErrors = False

    def test_default_view(self):
        self.browser.open('http://localhost')
        self.assertEqual(self.browser.title, 'Zope QuickStart')
        self.assertEqual(self.browser.status, '200 OK')

    def test_notfound_view(self):
        self.browser.open('http://localhost/nowhere')
        self.assertEqual(self.browser.status, '404 Not Found')

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
        self.browser.addHeader('Authorization', 'Basic admin:admin')
        self.browser.reload()
        self.assertEqual(self.browser.status, '200 OK')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FunctionalTestCase))
    return suite

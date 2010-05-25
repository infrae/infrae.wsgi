# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import unittest

import infrae.wsgi
from infrae.wsgi.testing import BrowserLayer, Browser


class FunctionalTestCase(unittest.TestCase):
    """Functional testing.
    """
    layer = BrowserLayer(infrae.wsgi)

    def setUp(self):
        self.browser = Browser()
        self.browser.handleErrors = True
        self.browser.raiseHttpErrors = False

    def test_default_view(self):
        self.browser.open('http://localhost')
        self.assertEqual(self.browser.title, 'Zope QuickStart')
        self.assertEqual(self.browser.status, '200 OK')

    def test_notfound(self):
        self.browser.open('http://localhost/nowhere')
        self.assertEqual(self.browser.status, '404 Not Found')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FunctionalTestCase))
    return suite

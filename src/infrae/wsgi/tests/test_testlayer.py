# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import unittest

import infrae.wsgi
from infrae.wsgi.testing import BrowserLayer, Browser


class MockWSGIApplication(object):
    """This mock WSGI application let us test the Browser/http method
    integration.
    """

    def __init__(self):
        self.__environ = None
        self.__result_status = '200 OK'
        self.__result_headers = ()

    def get_environ(self):
        return self.__environ

    def __call__(self, environ, start_response):
        self.__environ = environ
        write = start_response(self.__result_status, self.__result_headers)
        return ["Test succeed"]


class BrowserTestLayer(BrowserLayer):
    """A BrowserTestLayer where the Zope WSGI application is replaced
    with the mock WSGI application.
    """

    def testSetUp(self):
        self.test_wsgi_application = MockWSGIApplication()
        super(BrowserTestLayer, self).testSetUp()

    def testTearDown(self):
        super(BrowserTestLayer, self).testTearDown()
        self.test_wsgi_application = None

    def _create_wsgi_application(self):
        return self.test_wsgi_application


FunctionalLayer = BrowserTestLayer(infrae.wsgi)


class BrowserTestCase(unittest.TestCase):
    """Test the test browser.
    """
    layer = FunctionalLayer

    def setUp(self):
        self.wsgi_application = self.layer.test_wsgi_application

    def test_open(self):
        """Just test to access a URL.
        """
        browser = Browser()
        browser.open('http://localhost/index.html')
        environ = self.wsgi_application.get_environ()

        self.assertEqual(environ['wsgi.handleErrors'], True)
        self.assertEqual(environ['PATH_INFO'], '/index.html')
        self.assertEqual(environ['REQUEST_METHOD'], 'GET')

        self.assertEqual(browser.status, '200 OK')
        self.assertEqual(browser.contents, 'Test succeed')

    def test_handle_errors(self):
        """Test that the flag handleError on the browser switch the
        wsgi debug mode.
        """
        browser = Browser()
        browser.handleErrors = False
        browser.open('http://localhost/index.html')
        environ = self.wsgi_application.get_environ()

        self.assertEqual(environ['wsgi.handleErrors'], False)
        self.assertEqual(environ['PATH_INFO'], '/index.html')
        self.assertEqual(environ['REQUEST_METHOD'], 'GET')

    def test_authenticate(self):
        """Test addHeader/authentication header.
        """
        browser = Browser()
        browser.addHeader('Authorization', 'Basic mgr:mgrpw')
        browser.open('http://localhost/index.html')
        environ = self.wsgi_application.get_environ()

        self.assertEqual(environ['HTTP_AUTHORIZATION'], 'Basic bWdyOm1ncnB3')

    def test_authenticate_base64(self):
        """Test addHeader/authentication header with an already
        encoded header.
        """
        browser = Browser()
        browser.addHeader('Authorization', 'Basic bWdyOm1ncnB3')
        browser.open('http://localhost/index.html')
        environ = self.wsgi_application.get_environ()

        self.assertEqual(environ['HTTP_AUTHORIZATION'], 'Basic bWdyOm1ncnB3')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BrowserTestCase))
    return suite


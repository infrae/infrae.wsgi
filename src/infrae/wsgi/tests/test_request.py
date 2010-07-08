# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from cStringIO import StringIO
import unittest

from infrae.testing import ZCMLLayer
from infrae.wsgi.publisher import WSGIRequest, set_virtual_host
from infrae.wsgi.tests.mockers import MockApplication
import infrae.wsgi

TEST_REQUEST="GET /root HTTP/1.1\r\nHost:infrae.com\r\n\r\n"
TEST_ENVIRON = {'SERVER_NAME': 'infrae.com', 'SERVER_PORT': '80'}


class RequestTestCase(unittest.TestCase):
    """Test the WSGI request Virtual Host support.
    """
    layer = ZCMLLayer(infrae.wsgi)

    def setUp(self):
        self.request = WSGIRequest(StringIO(TEST_REQUEST), TEST_ENVIRON, None)
        self.request['PARENTS'] = [MockApplication(),]

    def test_simple(self):
        self.assertEqual(
            self.request.physicalPathToURL('/root'), 'http://infrae.com/root')
        self.assertEqual(
            self.request.getURL(), 'http://infrae.com')

    def test_virtual_host(self):
        set_virtual_host(self.request, 'https://silva.net')

        self.assertEqual(
            self.request.physicalPathToURL('/root'), 'https://silva.net/root')
        self.assertEqual(
            self.request.getURL(), 'https://silva.net')

    def test_virtual_host_and_path(self):
        set_virtual_host(self.request, 'http://zope.org/products/silva')

        self.assertEqual(
            self.request.physicalPathToURL('/root'),
            'http://zope.org/products/silva/root')
        self.assertEqual(
            self.request.getURL(),
            'http://zope.org/products/silva')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RequestTestCase))
    return suite

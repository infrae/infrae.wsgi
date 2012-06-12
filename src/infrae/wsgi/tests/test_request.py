# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from cStringIO import StringIO
import unittest

from zope.interface.verify import verifyObject

from infrae.testing import ZCMLLayer
from infrae.wsgi.interfaces import IRequest, ITraverser
from infrae.wsgi.interfaces import IVirtualHosting, IAuthenticator
from infrae.wsgi.publisher import WSGIRequest
from infrae.wsgi.tests.mockers import MockApplication
import infrae.wsgi

TEST_REQUEST="GET /root HTTP/1.1\r\nHost:infrae.com\r\n\r\n"
TEST_ENVIRON = {'SERVER_NAME': 'infrae.com', 'SERVER_PORT': '80'}


class RequestTestCase(unittest.TestCase):
    """Test the WSGI request Virtual Host support.
    """
    layer = ZCMLLayer(infrae.wsgi)

    def setUp(self):
        self.application = MockApplication()
        self.request = WSGIRequest(StringIO(TEST_REQUEST), TEST_ENVIRON, None)
        self.request['PARENTS'] = [self.application,]

    def test_simple(self):
        self.assertTrue(IRequest.providedBy(self.request))
        self.assertEqual(
            self.request.physicalPathToURL('/root'), 'http://infrae.com/root')
        self.assertEqual(
            self.request.getURL(), 'http://infrae.com')

    def test_plugin_traverser(self):
        retrieved_plugin = self.request.get_plugin(ITraverser)
        self.assertIs(retrieved_plugin, None)

        plugin = self.request.query_plugin(self.application, ITraverser)
        self.assertNotEqual(plugin, None)
        self.assertTrue(verifyObject(ITraverser, plugin))

        retrieved_plugin = self.request.get_plugin(ITraverser)
        self.assertIs(plugin, retrieved_plugin)

    def test_plugin_virtualhosting(self):
        retrieved_plugin = self.request.get_plugin(IVirtualHosting)
        self.assertIs(retrieved_plugin, None)

        plugin = self.request.query_plugin(self.application, IVirtualHosting)
        self.assertNotEqual(plugin, None)
        self.assertTrue(verifyObject(IVirtualHosting, plugin))

        retrieved_plugin = self.request.get_plugin(IVirtualHosting)
        self.assertIs(plugin, retrieved_plugin)

    def test_plugin_authenticator(self):
        retrieved_plugin = self.request.get_plugin(IAuthenticator)
        self.assertIs(retrieved_plugin, None)

        plugin = self.request.query_plugin(self.application, IAuthenticator)
        self.assertNotEqual(plugin, None)
        self.assertTrue(verifyObject(IAuthenticator, plugin))

        retrieved_plugin = self.request.get_plugin(IAuthenticator)
        self.assertIs(plugin, retrieved_plugin)

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RequestTestCase))
    return suite

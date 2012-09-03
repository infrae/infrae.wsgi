# -*- coding: utf-8 -*-
# Copyright (c) 2010-2012 Infrae. All rights reserved.
# See also LICENSE.txt

import unittest

from zope.interface.verify import verifyObject

from infrae.testing import ZCMLLayer
from infrae.wsgi.testing import TestRequest
from infrae.wsgi.interfaces import IRequest, ITraverser
from infrae.wsgi.interfaces import IVirtualHosting, IAuthenticator
import infrae.wsgi


class RequestTestCase(unittest.TestCase):
    """Test the WSGI request Virtual Host support.
    """
    layer = ZCMLLayer(infrae.wsgi)

    def test_test_request(self):
        request = TestRequest()
        self.assertTrue(IRequest.providedBy(request))
        self.assertEqual(
            request.physicalPathToURL('/root'), 'http://localhost/root')
        self.assertEqual(
            request.getURL(), 'http://localhost')

    def test_plugin_traverser(self):
        request = TestRequest()
        retrieved_plugin = request.get_plugin(ITraverser)
        self.assertIs(retrieved_plugin, None)

        plugin = request.query_plugin(request.application, ITraverser)
        self.assertNotEqual(plugin, None)
        self.assertTrue(verifyObject(ITraverser, plugin))

        retrieved_plugin = request.get_plugin(ITraverser)
        self.assertIs(plugin, retrieved_plugin)

    def test_plugin_virtualhosting(self):
        request = TestRequest()
        retrieved_plugin = request.get_plugin(IVirtualHosting)
        self.assertIs(retrieved_plugin, None)

        plugin = request.query_plugin(request.application, IVirtualHosting)
        self.assertNotEqual(plugin, None)
        self.assertTrue(verifyObject(IVirtualHosting, plugin))
        self.assertEqual(plugin.root, None)

        retrieved_plugin = request.get_plugin(IVirtualHosting)
        self.assertIs(plugin, retrieved_plugin)

    def test_plugin_authenticator(self):
        request = TestRequest()
        retrieved_plugin = request.get_plugin(IAuthenticator)
        self.assertIs(retrieved_plugin, None)

        plugin = request.query_plugin(request.application, IAuthenticator)
        self.assertNotEqual(plugin, None)
        self.assertTrue(verifyObject(IAuthenticator, plugin))

        retrieved_plugin = request.get_plugin(IAuthenticator)
        self.assertIs(plugin, retrieved_plugin)


class VirtualHostingTestCase(unittest.TestCase):
    """Test the virtual hosting plugin functionality.
    """
    layer = ZCMLLayer(infrae.wsgi)

    def test_rewrite_url(self):
        request = TestRequest()
        plugin = request.query_plugin(request.application, IVirtualHosting)
        self.assertNotEqual(plugin, None)

        self.assertEqual(
            plugin.rewrite_url(None, 'http://localhost/root/folder/edit'),
            '/root/folder/edit')
        self.assertEqual(
            plugin.rewrite_url('https://admin', 'http://localhost/root/edit'),
            'https://admin/root/edit')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RequestTestCase))
    suite.addTest(unittest.makeSuite(VirtualHostingTestCase))
    return suite

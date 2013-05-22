# -*- coding: utf-8 -*-
# Copyright (c) 2010-2013 Infrae. All rights reserved.
# See also LICENSE.txt

# This package define a simple infrae.testing layer with a wsgi
# application.

import re
import base64

from AccessControl.SecurityManagement import (
    getSecurityManager, setSecurityManager, noSecurityManager)
from zope.site.hooks import getSite, setSite, setHooks
from transaction import commit

from infrae.testing import Zope2Layer
from infrae.wsgi.publisher import WSGIApplication


basicre = re.compile('Basic (.+)?:(.+)?$')
def auth_header(header):
    """This function takes an authorization HTTP header and encode the
    couple user, password into base 64 like the HTTP protocol wants
    it.
    """
    match = basicre.match(header)
    if match:
        u, p = match.group(1, 2)
        if u is None:
            u = ''
        if p is None:
            p = ''
        auth = base64.encodestring('%s:%s' % (u, p))
        return 'Basic %s' % auth[:-1]
    return header


class TestBrowserWSGIResult(object):
    """Call a WSGI Application and return its result.

    Backup the ZCA local site before calling the wrapped application and
    restore it when done.
    """

    def __init__(self, app, connection, environ, start_response):
        self.app = app
        self.connection = connection
        self.environ = environ
        self.start_response = start_response
        self.__result = None
        self.__next = None
        self.__site = None
        self.__security = None

    def __iter__(self):
        return self

    def next(self):
        if self.__next is None:
            # Backup ZCA site and security manager
            self.__site = getSite()
            self.__security = getSecurityManager()
            noSecurityManager()
            self.__result = self.app(self.environ, self.start_response)
            self.__next = iter(self.__result).next
        return self.__next()

    def close(self):
        if self.__result is not None:
            if hasattr(self.__result, 'close'):
                self.__result.close()
        if self.__site is not None:
            setSite(self.__site)
            setHooks()
        if self.__security is not None:
            setSecurityManager(self.__security)
        self.connection.sync()


class TestWSGIMiddleware(object):
    """Simple middleware that commit changes before calling the
    application and restore the Zope status after. It is not
    compatible with zope.app.testing.
    """

    def __init__(self, app, connection):
        self.app = app
        self.connection = connection

    def __call__(self, environ, start_response):
        # Handle authorization
        auth_key = 'HTTP_AUTHORIZATION'
        if environ.has_key(auth_key):
            environ[auth_key] = auth_header(environ[auth_key])

        commit()
        return TestBrowserWSGIResult(
            self.app, self.connection, environ, start_response)


class BrowserLayer(Zope2Layer):
    """Functional test layer.
    """

    def _create_wsgi_application(self):
        # Create Zope WSGI Application. You can change this method if
        # you whish to change the tested WSGI application.
        return WSGIApplication(
            self._application, self._transaction_manager)

    def testSetUp(self):
        super(BrowserLayer, self).testSetUp()
        wsgi_app = self._create_wsgi_application()

        self._test_wsgi_application = TestWSGIMiddleware(
            wsgi_app, self._test_connection)

    def testTearDown(self):
        self._test_wsgi_application = None
        super(BrowserLayer, self).testTearDown()

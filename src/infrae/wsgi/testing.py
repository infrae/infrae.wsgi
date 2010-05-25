# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import re
import base64

from infrae.testing import Zope2Layer, suite_from_package
from infrae.wsgi.publisher import WSGIApplication
from transaction import commit
from wsgi_intercept.mechanize_intercept import Browser as BaseInterceptBrowser
from zope.testbrowser.browser import Browser as ZopeTestBrowser
import wsgi_intercept

# List of hostname where the test browser/http function replies to
TEST_HOSTS = ['localhost', '127.0.0.1']


class InterceptBrowser(BaseInterceptBrowser):

    default_schemes = ['http']
    default_others = ['_http_error', '_http_request_upgrade',
                      '_http_default_error']
    default_features = ['_redirect', '_cookies', '_referer', '_refresh',
                        '_equiv', '_basicauth', '_digestauth']


class Browser(ZopeTestBrowser):
    """Override the zope.testbrowser.browser.Browser interface so that it
    uses PatchedMechanizeBrowser
    """

    def __init__(self, *args, **kwargs):
        kwargs['mech_browser'] = InterceptBrowser()
        ZopeTestBrowser.__init__(self, *args, **kwargs)

    @property
    def status(self):
        return '%d %s' % (
            self.mech_browser._response.code,
            self.mech_browser._response.msg)


# Compatibility helpers to behave like zope.app.testing

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


def is_wanted_header(header):
    """Return True if the given HTTP header key is unwanted.
    """
    key, value = header
    return key.lower() not in ('x-content-type-warning', 'x-powered-by')


class TestBrowserWSGIResult(object):
    """Call a WSGI Application and return its result.
    """

    def __init__(self, app, finish, environ, start_response):
        self.app = app
        self.environ = environ
        self.start_response = start_response
        self.finish = finish
        self.__result = None
        self.__next = None

    def __iter__(self):
        return self

    def next(self):
        if self.__next is None:
            self.__result = self.app(self.environ, self.start_response)
            self.__next = iter(self.__result).next
        return self.__next()

    def close(self):
        if self.__result is not None:
            if hasattr(self.__result, 'close'):
                self.__result.close()
        self.finish()


class TestBrowserMiddleware(object):
    """This middleware makes the WSGI application compatible with the
    HTTPCaller behavior defined in zope.app.testing.functional:
    - It honors the X-zope-handle-errors header in order to support
      zope.testbrowser Browser handleErrors flag.
    - It modifies the HTTP Authorization header to encode user and
      password into base 64 if it is Basic authentication.
    """

    def __init__(self, app, connection, handle_errors):
        assert isinstance(handle_errors, bool)
        self.app = app
        self.default_handle_errors = str(handle_errors)
        self.connection = connection

    def __call__(self, environ, start_response):
        # Handle debug mode
        handle_errors = environ.get(
            'HTTP_X_ZOPE_HANDLE_ERRORS', self.default_handle_errors)
        environ['wsgi.handleErrors'] = handle_errors == 'True'

        # Handle authorization
        auth_key = 'HTTP_AUTHORIZATION'
        if environ.has_key(auth_key):
            environ[auth_key] = auth_header(environ[auth_key])

        # Remove unwanted headers
        def application_start_response(status, headers):
            headers = filter(is_wanted_header, headers)
            return start_response(status, headers)

        commit()

        return TestBrowserWSGIResult(
            self.app, self.connection.sync, environ, application_start_response)


class BrowserLayer(Zope2Layer):
    """Functional test layer.
    """

    def testSetUp(self):
        super(BrowserLayer, self).testSetUp()
        wsgi_app = WSGIApplication(
            self._application, self._transaction_manager)

        def factory(handle_errors=True):
            return TestBrowserMiddleware(
                wsgi_app, self._test_connection, handle_errors)

        for host in TEST_HOSTS:
            wsgi_intercept.add_wsgi_intercept(host, 80, factory)

    def testTearDown(self):
        for host in TEST_HOSTS:
            wsgi_intercept.remove_wsgi_intercept(host, 80)
        super(BrowserLayer, self).testTearDown()


class ResponseParser(object):
    """This behave like a Response object returned by HTTPCaller of
    zope.app.testing.functional.
    """

    def __init__(self, data):
        self.data = data

    def getStatus(self):
        line = self.getStatusString()
        status, rest = line.split(' ', 1)
        return int(status)

    def getStatusString(self):
        status_line = self.data.split('\n', 1)[0]
        protocol, status_string = status_line.split(' ', 1)
        return status_string

    def getHeader(self, name, default=None):
        return self.getHeaders().get(name, default)

    def getHeaders(self):
        without_body = self.data.split('\n\n', 1)[0]
        headers_text = without_body.split('\n', 1)[1]
        headers = {}
        for header in headers_text.split('\n'):
            header_name, header_value = header.split(':', 1)
            header_value = header_value.strip()
            if header_name in headers:
                if isinstance(headers[header_name], list):
                    headers[header_name].append(header_value)
                else:
                    headers[header_name] = [headers[header_name], header_value]
            else:
                headers[header_name] = header_value
        return headers

    def getBody(self):
        parts = self.data.split('\n\n', 1)
        if len(parts) < 2:
            return ''
        return parts[1]

    def getOutput(self):
        return self.data

    __str__ = getOutput


def http(string, handle_errors=False, parsed=False):
    """This function behave like the HTTPCaller of
    zope.app.testing.functional.
    """
    key = ('localhost', 80)

    if key not in wsgi_intercept._wsgi_intercept:
        raise ValueError("Test not runned in the proper layer.")

    (app_fn, script_name) = wsgi_intercept._wsgi_intercept[key]
    app = app_fn(handle_errors=handle_errors)

    socket = wsgi_intercept.wsgi_fake_socket(app, 'localhost', 80, '')
    socket.sendall(string.lstrip())
    result = socket.makefile()
    response = result.getvalue()
    if parsed:
        return ResponseParser(response)
    return response

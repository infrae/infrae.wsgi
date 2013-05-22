# -*- coding: utf-8 -*-
# Copyright (c) 2010-2013 Infrae. All rights reserved.
# See also LICENSE.txt

from cStringIO import StringIO

from Acquisition import aq_base
from ZPublisher.BaseRequest import RequestContainer
from zope.interface import implements, alsoProvides

from infrae.wsgi.interfaces import ITestRequest
from infrae.wsgi.publisher import WSGIRequest, WSGIResponse
from infrae.wsgi.tests.mockers import MockRoot
from infrae.wsgi.utils import split_path_info

import urlparse
import urllib


class TestRequest(WSGIRequest):
    """Test request that inherit from the real request.
    """
    implements(ITestRequest)

    def __init__(self, application=None, layers=[], headers={},
                 url='http://localhost', method='GET', debug=True, form={}):
        url_parts = urlparse.urlparse(url)
        netloc_parts = url_parts.netloc.split(':')
        if len(netloc_parts) > 1:
            hostname = netloc_parts[0]
            port = netloc_parts[1]
        else:
            hostname = netloc_parts[0]
            if url_parts.scheme == 'https':
                port = '443'
            else:
                port = '80'
        query = url_parts.query
        if form:
            if isinstance(form, dict):
                data = []
                for key, value in form.iteritems():
                    if isinstance(value, (list, tuple)):
                        for item in value:
                            data.append((key, item))
                    else:
                        data.append((key, value))
            elif isinstance(form, (list, tuple)):
                data = form
            else:
                raise ValueError("Cannot encode form", form)
            query = urllib.urlencode(data)
        environ = {'SERVER_PROTOCOL': 'HTTP/1.0',
                   'SERVER_NAME': hostname,
                   'SERVER_PORT': port,
                   'wsgi.version': (1,0),
                   'wsgi.url_scheme': url_parts.scheme,
                   'wsgi.input': StringIO(),
                   'wsgi.errors': StringIO(),
                   'wsgi.multithread': False,
                   'wsgi.multiprocess': False,
                   'wsgi.run_once': False,
                   'wsgi.handleErrors': not debug,
                   'REQUEST_METHOD': method,
                   'SCRIPT_NAME': '',
                   'PATH_INFO': url_parts.path,
                   'QUERY_STRING': query}
        for name, value in headers:
            http_name = ('HTTP_' + name.upper()).replace('-', '_')
            environ[http_name] = value
        WSGIRequest.__init__(
            self,
            environ['wsgi.input'],
            environ,
            WSGIResponse(environ, lambda status, headers: None, debug))
        if application is None:
            application = MockRoot()
        else:
            application = aq_base(application.getPhysicalRoot())
        self.application = application.__of__(RequestContainer(REQUEST=self))
        self['PARENTS'] = [self.application,]
        for layer in layers:
            alsoProvides(self, layer)
        self.processInputs()
        path_info = self['PATH_INFO']

        path = list(reversed(split_path_info(path_info)))
        self['ACTUAL_URL'] = self['URL'] + urllib.quote(path_info)
        self['TraversalRequestNameStack'] = self.path = path
        method = self.get('REQUEST_METHOD', 'GET').upper()
        if method in ['GET', 'POST']:
            method = 'index_html'
        self.method = method

    def _hold(self, callback):
        # Discard cleanup callback
        pass

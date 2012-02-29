# -*- coding: utf-8 -*-
# Copyright (c) 2011 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import urlparse

from five import grok
from zope.interface import Interface

from OFS.interfaces import IObjectManager
import zExceptions

from infrae.wsgi.interfaces import IRequest, IVirtualHosting
from infrae.wsgi.utils import split_path_info


class VirtualHosting(grok.MultiAdapter):
    grok.adapts(Interface, IRequest)
    grok.provides(IVirtualHosting)
    grok.implements(IVirtualHosting)

    # Default virtual hosting headers.
    HEADERS = ['HTTP_X_VHM_HOST',
               'HTTP_X_FORWARDED_HOST',
               'HTTP_X_FORWARDED_SERVER']

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def traverse(self, path):
        """Traverse to the root object at  path.
        """
        content = self.context
        for piece in path:
            child = content._getOb(piece, None)
            if not IObjectManager.providedBy(child):
                raise zExceptions.NotFound(self.path)
            hook = getattr(child, '__before_publishing_traverse__', None)
            if hook is not None:
                hook(child, self.request)
            content = child.__of__(content)
        return content

    def __call__(self, method, path):
        root = self.context
        for header in self.HEADERS:
            virtual_host = self.request.environ.get(header)
            if virtual_host:
                url = urlparse.urlparse(virtual_host)
                if ':' in url.netloc:
                    hostname, port = url.netloc.split(':', 1)
                    self.request.setServerURL(url.scheme, hostname, int(port))
                else:
                    self.request.setServerURL(url.scheme, url.netloc)
                path = split_path_info(url.path)
                if path:
                    root = self.traverse(path)
                    self.request.setVirtualRoot(path)
                break

        return root, method, path

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
                raise zExceptions.BadRequest(
                    u'Invalid virtual host path /%s.' % '/'.join(path))
            hook = getattr(child, '__before_publishing_traverse__', None)
            if hook is not None:
                hook(child, self.request)
            content = child
            self.request['PARENTS'].append(content)
        return content

    def __call__(self, method, path):
        root = self.context
        virtual_host = self.request.environ.get(
            'HTTP_X_VHM_HOST')
        if virtual_host:
            url = urlparse.urlparse(virtual_host)

            # Step 1. Set Server Name
            hostname = url.netloc
            if ':' in hostname:
                hostname, port = url.netloc.split(':', 1)
            else:
                port = '80'
                if url.scheme == 'https':
                    port = '443'
            self.request.setServerURL(url.scheme, hostname, port)

            # Step 2. Consume extra path
            host_path = split_path_info(url.path)
            if host_path:
                for piece in host_path:
                    if path:
                        taken_piece = path.pop()
                        if taken_piece == piece:
                            continue
                    raise zExceptions.BadRequest(
                        u'This URL is not in the virtual host.')

            # Step 3. Traverse to the virtual root
            virtual_path = split_path_info(
                self.request.environ.get(
                    'HTTP_X_VHM_PATH'))
            if virtual_path:
                root = self.traverse(virtual_path)

            # Step 4, in case of path manipulation, set virtual root
            if virtual_path or host_path:
                self.request.setVirtualRoot(host_path)

        return root, method, path

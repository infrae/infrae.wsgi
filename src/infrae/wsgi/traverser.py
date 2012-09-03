# -*- coding: utf-8 -*-
# Copyright (c) 2011-2012 Infrae. All rights reserved.
# See also LICENSE.txt

from five import grok
from zope.component import queryMultiAdapter
from zope.interface import Interface
from zope.publisher.interfaces import NotFound
from zope.publisher.interfaces.browser import IBrowserPublisher

from AccessControl.ZopeSecurityPolicy import getRoles
from ZPublisher.BaseRequest import UNSPECIFIED_ROLES, DefaultPublishTraverse
from ZPublisher.BaseRequest import quote
from OFS.interfaces import IObjectManager
import zExceptions

from infrae.wsgi.interfaces import IRequest, ITraverser


class ObjectManagerPublishTraverse(DefaultPublishTraverse, grok.MultiAdapter):
    """The default Zope 3 folder traverser is register in Zope
    2.13.13. We register the Zope 2 one for Zope 2 folder, to prevent
    a broken ZMI.
    """
    grok.adapts(IObjectManager, IRequest)
    grok.provides(IBrowserPublisher)


def query_adapter(content, request, iface):
    """Query an adapter if needed.
    """
    if iface.providedBy(content):
        return content
    adapter = queryMultiAdapter((content, request), iface)
    if adapter is None:
        return DefaultPublishTraverse(content, request)
    return adapter


class Traverser(grok.MultiAdapter):
    grok.adapts(Interface, IRequest)
    grok.provides(ITraverser)
    grok.implements(ITraverser)

    def __init__(self, context, request):
        self.request = request
        self.context = context
        self.roles = getRoles(None, None, context, UNSPECIFIED_ROLES)

    def __call__(self, method, path):
        request = self.request
        content = self.context
        parents = request['PARENTS']
        request['TraversalRequestNameStack'] = path
        # Steps records the traversed path (used for some URL computation)
        steps = request.steps
        _steps = request._steps = map(quote, steps)
        entry_name = ''

        try:
            # We build parents in the wrong order, so we
            # need to make sure we reverse it when we're done.
            while 1:
                bpth = getattr(content, '__before_publishing_traverse__', None)
                if bpth is not None:
                    bpth(content, request)

                path = request.path = request['TraversalRequestNameStack']
                # Consume one item in the path.
                if path:
                    entry_name = path.pop()
                else:
                    # End of path, look for a view using IBrowserPublisher

                    next_content, default_path = query_adapter(
                        content, request, IBrowserPublisher).browserDefault(
                        request)

                    if next_content is not content:
                        self.roles = getRoles(
                            content, None, next_content, self.roles)
                        content = next_content

                    if default_path:
                        request._hacked_path=1
                        if len(default_path) > 1:
                            path = list(default_path)
                            method = path.pop()
                            request['TraversalRequestNameStack'] = path
                            continue
                        else:
                            entry_name = default_path[0]
                    elif (method and hasattr(content, method)
                          and entry_name != method
                          and getattr(content, method) is not None):
                        request._hacked_path=1
                        entry_name = method
                        method = 'index_html'
                    else:
                        break

                step = quote(entry_name)
                _steps.append(step)
                steps.append(entry_name)
                request['URL'] = '/'.join((request['URL'], step))

                try:
                    next_content = request.traverseName(content, entry_name)
                except (KeyError, AttributeError, NotFound):
                    raise zExceptions.NotFound(request['URL'])

                if (hasattr(content, '__bobo_traverse__') or
                    hasattr(content, entry_name)):
                    check_name = entry_name
                else:
                    check_name = None

                self.roles = getRoles(
                    content, check_name, next_content, self.roles)
                content = next_content

                parents.append(content)
        finally:
            parents.reverse()

        # Hacked path is for ZMI, where the real path is different
        # than the URL, and a base tag must be hacked in the body
        # response.
        if request._hacked_path:
            url = request['URL']
            index = url.rfind('/')
            if index > 0:
                request.response.setBase(url[:index])


        # content is PUBLISHED, or the first in parents (since it have
        # been reversed).
        request['PUBLISHED'] = parents.pop(0)

        # If content as a call method, get the roles defined on it, it
        # will be called.
        if hasattr(content, '__call__'):
            self.roles = getRoles(
                content, '__call__', content.__call__, self.roles)
        request.roles = self.roles

        return content


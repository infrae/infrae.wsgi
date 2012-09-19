# -*- coding: utf-8 -*-
# Copyright (c) 2011-2012 Infrae. All rights reserved.
# See also LICENSE.txt

from zope.interface import Interface, Attribute, implements
from zope.publisher.interfaces.browser import IDefaultBrowserLayer

from ZPublisher.interfaces import IPubAfterTraversal, IPubEvent
from ZPublisher.pubevents import PubStart, PubSuccess, PubFailure, \
    PubBeforeCommit, PubAfterTraversal, PubBeforeAbort, \
    PubBeforeStreaming


class IRequest(IDefaultBrowserLayer):

    def query_plugin(context, iface):
        """Query an adapter that adapts context and request. Store it
        All request variable must set properlyfor future use.
        """

    def get_plugin(iface):
        """Return a previously queried plugin.
        """


class ITestRequest(IRequest):
    application = Attribute(u'Application root')
    method = Attribute(u"Queried method")
    path = Attribute(u"Queried path")


class IVirtualHosting(Interface):
    """Implement the virtual hosting.
    """
    request = Attribute(u"Request being published")
    context = Attribute(u"Application root")
    root = Attribute(u"Virtual Hosting that have been computed, if any.")

    def rewrite_url(base_url, original_url):
        """Rewrite ``original_url`` (a currently valid URL in the
        current computed virtual host) to be accessible via
        ``base_url`` (an another available virtual host). If
        ``base_url`` is empty, only a global path will be returned.
        """

    def __call__(method, path):
        """Return a tuple (root, method, path) to use after virtual
        hosting being done.

        All request variable must be updated properly.
        """


class ITraverser(Interface):
    """Traverse to the published content.
    """
    request = Attribute(u"Request being traversed")
    context = Attribute(u"Application root")

    def __call__(method, path):
        """Traversed to the published content.

        All request variable must be set properly.
        """


class IAuthenticator(Interface):
    """Do the Zope authentication, after the traverser have been called.
    """
    request = Attribute(u"Request")
    context = Attribute(u"Published content")

    def __call__(validation_hook=None):
        """Do the authentication. You can raise Unauthorized in case
        of failure.

        If validation_hook is provided, you must call it if a user is
        authenticated.

        All request variable must be set properly.
        """


# Publications Events, review and extend Zope2 publication events


class IPublicationAfterTraversal(IPubAfterTraversal):
    content = Attribute(u"Content traversed to")


class IPublicationAfterRender(IPubEvent):
    content = Attribute(u"Content rendered")


class IPublicationBeforeError(IPubEvent):
    content = Attribute(u"Content where the error happened.")


class PublicationStart(PubStart):
    pass


class PublicationAfterTraversal(PubAfterTraversal):
    implements(IPublicationAfterTraversal)

    def __init__(self, request, content):
        self.request = request
        self.content = content


class PublicationBeforeError(object):
    implements(IPublicationBeforeError)

    def __init__(self, request, content):
        self.request = request
        self.content = content

class PublicationAfterRender(object):
    implements(IPublicationAfterRender)

    def __init__(self, request, content):
        self.request = request
        self.content = content


class PublicationSuccess(PubSuccess):
    pass


class PublicationBeforeCommit(PubBeforeCommit):
    pass


class PublicationFailure(PubFailure):
    pass


class PublicationBeforeAbort(PubBeforeAbort):
    pass


class PublicationBeforeStreaming(PubBeforeStreaming):
    pass

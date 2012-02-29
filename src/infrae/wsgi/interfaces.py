# -*- coding: utf-8 -*-
# Copyright (c) 2011 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from zope.interface import Interface, Attribute
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IRequest(IDefaultBrowserLayer):

    def query_plugin(context, iface):
        """Query an adapter that adapts context and request. Store it
        All request variable must set properlyfor future use.
        """

    def get_plugin(iface):
        """Return a previously queried plugin.
        """


class IVirtualHosting(Interface):
    """Implement the virtual hosting.
    """
    request = Attribute(u"Request being published")
    context = Attribute(u"Application root")

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

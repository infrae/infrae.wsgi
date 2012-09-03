# -*- coding: utf-8 -*-
# Copyright (c) 2010-2012 Infrae. All rights reserved.
# See also LICENSE.txt

from five import grok
from zope.interface import providedBy
from zope.publisher.interfaces import INotFound
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.security.interfaces import IForbidden

from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
import Acquisition
import zExceptions

grok.layer(IBrowserRequest)

HTML_TEMPLATE = u"""
<html>
  <head>
    <title>%s</title>
  </head>
  <body>
     <h1>An error happened</h1>
     <p><b>%s</b></p>
  </body>
</html>
"""

class DefaultError(Acquisition.Implicit):
    """Wrapper for errors. The are the context, with all acquisition
    and Zope Component Architecture working.
    """
    security = ClassSecurityInfo()
    security.declareObjectPublic()

    def __init__(self, error):
        self.error = error

    @property
    def __provides__(self):
        if hasattr(self.error, '__provides__'):
            return self.error.__provides__
        return providedBy(self.error)


InitializeClass(DefaultError)


class NotFound(grok.View):
    grok.name('error.html')
    grok.context(INotFound)

    def update(self):
        self.response.setStatus(404)

    def render(self):
        return HTML_TEMPLATE % (
            self.__class__.__name__, 'Page not found: %s' %
            str(self.context.error))


class Forbidden(grok.View):
    grok.name('error.html')
    grok.context(IForbidden)

    def update(self):
        self.response.setStatus(403)

    def render(self):
        return HTML_TEMPLATE % (
            self.__class__.__name__, str(self.context.error))


class BadRequest(grok.View):
    grok.name('error.html')
    grok.context(zExceptions.BadRequest)

    def update(self):
        self.response.setStatus(400)

    def render(self):
        return HTML_TEMPLATE % (
            self.__class__.__name__, 'Bad request: %s' %
            str(self.context.error))


class Error(grok.View):
    grok.name('error.html')
    grok.context(Exception)

    def update(self):
        self.response.setStatus(500)

    def render(self):
        return HTML_TEMPLATE % (
            self.context.error.__class__.__name__, str(self.context.error))

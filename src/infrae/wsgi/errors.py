# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$


from five import grok
from zope.publisher.interfaces import INotFound
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.security.interfaces import IForbidden

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


class NotFound(grok.View):
    grok.name('error.html')
    grok.context(INotFound)

    def update(self):
        self.response.setStatus(404)

    def render(self):
        return HTML_TEMPLATE % (
            self.__class__.__name__, 'Page not found: %s' % str(self.error))


class Forbidden(grok.View):
    grok.name('error.html')
    grok.context(IForbidden)

    def update(self):
        self.response.setStatus(403)

    def render(self):
        return HTML_TEMPLATE % (self.__class__.__name__, str(self.error))


class Error(grok.View):
    grok.name('error.html')
    grok.context(Exception)

    def update(self):
        self.response.setStatus(500)

    def render(self):
        return HTML_TEMPLATE % (self.error.__class__.__name__, str(self.error))

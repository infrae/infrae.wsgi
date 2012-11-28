

from five import grok
from zope.interface import Interface
from infrae.wsgi.response import AbortPublication


class TestView(grok.View):
    grok.context(Interface)
    grok.name('test.html')

    def render(self):
        return '<html><h1>Test</h1></html>'


class AbortView(grok.View):
    grok.context(Interface)
    grok.name('abort.html')

    def render(self):
        # This should only done by infrae.wsgi code.
        raise AbortPublication(False)

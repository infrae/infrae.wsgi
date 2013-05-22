# -*- coding: utf-8 -*-
# Copyright (c) 2013  Infrae. All rights reserved.
# See also LICENSE.txt

from ZODB.POSException import ConflictError

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


class ConflictuousView(grok.View):
    grok.context(Interface)
    grok.name('conflict.html')

    def render(self):
        raise ConflictError()


class ConflictAndErrorView(grok.View):
    grok.context(Interface)
    grok.name('failed_conflict.html')

    def render(self):
        if self.request.retry_count:
            raise ValueError('Failed')
        raise ConflictError()

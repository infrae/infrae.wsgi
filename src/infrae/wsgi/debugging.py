# -*- coding: utf-8 -*-
# Copyright (c) 2012  Infrae. All rights reserved.
# See also LICENSE.txt

from five import grok
from zope.interface import Interface

import thread
import sys
import traceback
import time
from cStringIO import StringIO

def dump_threads():
    """Dump running threads

    Returns a string with the tracebacks.
    """

    frames = sys._current_frames()
    this_thread_id = thread.get_ident()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    res = ["Threads traceback dump at %s\n" % now]
    for thread_id, frame in frames.iteritems():
        if thread_id == this_thread_id:
            continue

        # Find request in frame
        reqinfo = ''
        f = frame
        while f is not None:
            co = f.f_code

            if co.co_name == 'publish':
                if co.co_filename.endswith('/infrae/wsgi/publisher.py'):
                    request = f.f_locals.get('request')
                    if request is not None:
                        reqinfo += (request.get('REQUEST_METHOD', '') + ' ' +
                                   request.get('PATH_INFO', ''))
                        qs = request.get('QUERY_STRING')
                        if qs:
                            reqinfo += '?'+qs
                    break
            f = f.f_back
        if reqinfo:
            reqinfo = " (%s)" % reqinfo

        output = StringIO()
        traceback.print_stack(frame, file=output)
        res.append("Thread %s%s:\n%s" %
            (thread_id, reqinfo, output.getvalue()))

    frames = None
    res.append("End of dump")
    return '\n'.join(res)


class DebugThreads(grok.View):
    grok.context(Interface)
    grok.name('debugzope.html')
    grok.require('zope2.ViewManagementScreens')

    def render(self):
        return u'<html><body><pre>%s</pre></body></html>' % dump_threads()


try:
    import webob.dec
except ImportError:
    def make_middleware(app, global_config, **config):
        return app
else:
    class DebugThreadsMiddleware(object):
        """Display the threads status. Warning: if enabled, this
        can be accessed without any authentication.
        """

        def __init__(self, app, name="++threads++"):
            self.app = app
            self.name = name

        @webob.dec.wsgify
        def __call__(self, request):
            if request.path_info.startswith('/' + self.name):
                threads = dump_threads()
                return '<html><body><pre>%s</pre></body></html>' % threads
            return request.get_response(self.app)

    def make_middleware(app, global_config, **config):
        name = config.get('name', '++threads++')
        return DebugThreadsMiddleware(app, name=name)


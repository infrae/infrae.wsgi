# -*- coding: utf-8 -*-
# Copyright (c) 2010-2012 Infrae. All rights reserved.
# See also LICENSE.txt

from cStringIO import StringIO
from tempfile import TemporaryFile
from urllib import quote
import socket
import threading

from zope.cachedescriptors.property import Lazy

from AccessControl.SecurityManagement import noSecurityManager
from Acquisition.interfaces import IAcquirer
from ZPublisher.BaseRequest import exec_callables, RequestContainer
from ZPublisher.Publish import Retry
from ZPublisher.Request import Request
from ZPublisher.mapply import mapply
from ZODB.POSException import ConflictError
from zope.component import queryMultiAdapter, getMultiAdapter
from zope.event import notify
from zope.interface import implements
from zope.site.hooks import getSite
from zope.publisher.interfaces.browser import IBrowserPage, IBrowserPublisher
from zope.security.management import newInteraction, endInteraction
import Zope2
import zExceptions

from infrae.wsgi import interfaces
from infrae.wsgi.errors import DefaultError
from infrae.wsgi.response import WSGIResponse, AbortPublication
from infrae.wsgi.log import logger, log_last_error, ErrorSupplement
from infrae.wsgi.utils import reconstruct_url_from_environ
from infrae.wsgi.utils import split_path_info

CHUNK_SIZE = 1<<16              # 64K


def call_object(obj, args, request):
    return apply(obj, args)


def missing_name(name, request):
    if name == 'self':
        return request['PARENTS'][0]
    raise zExceptions.BadRequest(name)


def dont_publish_class(klass, request):
    raise zExceptions.Forbidden("class %s" % klass.__name__)


class WSGIRequest(Request):
    """A WSGIRequest have a default skin.
    """
    implements(interfaces.IRequest)

    def __init__(self, *args, **kwargs):
        Request.__init__(self, *args, **kwargs)
        self.__plugins = {interfaces.IRequest.__identifier__: self}

    def query_plugin(self, context, iface):
        plugin = getMultiAdapter((context, self), iface)
        self.__plugins[iface.__identifier__] = plugin
        return plugin

    def get_plugin(self, iface):
        return self.__plugins.get(iface.__identifier__)


class WSGIResult(object):
    """Iterator to wrap Zope result, in order to commit/abort the
    transaction at the end of the iterator iteration, and to close the
    request at the end.
    """

    def __init__(self, request, publisher, data, cleanup=None):
        self.request = request
        self.publisher = publisher
        self.cleanup = cleanup
        self.__next = iter(data).next
        self.__failed = False

    @Lazy
    def url(self):
        return reconstruct_url_from_environ(self.request.environ)

    def next(self):
        try:
            return self.__next()
        except StopIteration:
            raise
        except Exception:
            logger.exception(
                u"Unexpected error in the WSGI stack for '%s'", self.url)
            self.__failed = True
            raise

    def __iter__(self):
        return self

    def close(self):
        try:
            if self.__failed:
                logger.error(
                    "An error happened in the WSGI stack "
                    "while iterating the result for the url '%s'", self.url)
                self.publisher.abort()
            else:
                self.publisher.finish()
        except ConflictError:
            self.publisher.abort()
            raise
        finally:
            # Always cleanup
            if self.cleanup is not None:
                self.cleanup()


def safe_callback(publisher, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except Exception:
        log_last_error(publisher.request, publisher.response)


class WSGIPublication(object):
    """Publish a request through WSGI.
    """

    def __init__(self, app, request, response):
        self.app = app
        self.request = request
        self.response = response
        self.data_sent = False
        self.publication_done = False

    def start(self):
        """Start the publication process.
        """
        notify(interfaces.PublicationStart(self.request))
        newInteraction()
        noSecurityManager()
        self.app.transaction.begin()
        self.request.processInputs()

    def commit(self):
        """Commit results of the publication.
        """
        safe_callback(
            self,
            notify,
            interfaces.PublicationBeforeCommit(self.request))
        self.app.transaction.commit()
        endInteraction()
        safe_callback(
            self,
            notify,
            interfaces.PublicationSuccess(self.request))

    def abort(self):
        """Abort the current publication process.
        """
        safe_callback(
            self,
            notify,
            interfaces.PublicationBeforeAbort(self.request, None, False))
        self.app.transaction.abort()
        endInteraction()
        safe_callback(
            self,
            notify,
            interfaces.PublicationFailure(self.request, None, False))

    def finish(self):
        """End the publication process, by either committing the
        transaction or aborting it.
        """
        if self.publication_done:
            return
        if self.response.getStatus() < 404:
            # We want to commit the transaction in case of redirects
            # and unauthorized.
            self.commit()
        else:
            self.abort()
        self.publication_done = True

    def result(self):
        """Return the result of the response, and commit if we don't
        plan to stream data/or had stream data.
        """
        self.data_sent, data = self.response.getWSGIResponse()
        if not self.data_sent:
            # If we didn't send any data yet, commit now: if the commit
            # fail, we can retry the request since we didn't send
            # anything.
            self.finish()
        return data

    def error(self, error, last_known_obj):
        """Render and log an error.
        """
        if IBrowserPage.providedBy(last_known_obj):
            #of the last obj is a view, use it's context (which should be
            # an IAcquirer)
            last_known_obj = last_known_obj.context
        if not IAcquirer.providedBy(last_known_obj):
            last_known_site = getSite()
            if last_known_site is not None:
                last_known_obj = last_known_site
        context = DefaultError(error)
        if IAcquirer.providedBy(last_known_obj):
            context = context.__of__(last_known_obj)
        error_view = queryMultiAdapter(
            (context, self.request), name='error.html')
        if IBrowserPublisher.providedBy(error_view):
            error_view, error_path = error_view.browserDefault(self.request)
            if error_path:
                raise NotImplementedError(
                    u'Error browserDefault retuned an path. '
                    u'This is not implemented.')

        if error_view is not None:
            notify(interfaces.PublicationBeforeError(
                    self.request, last_known_obj))
            try:
                error_result = error_view()
                if error_result is not None:
                    self.response.setBody(error_result)

                notify(interfaces.PublicationAfterRender(
                        self.request, error_view))

            except Exception as error:
                log_last_error(
                    self.request, self.response, obj=last_known_obj,
                    extra=u"Error while rendering error message")
                self.response.setStatus(500)
                self.response.setBody(ERROR_WHILE_RENDERING_ERROR_TEMPLATE)
        else:
            logger.error('No action defined for last exception')
            self.response.setStatus(500)
            self.response.setBody(DEFAULT_ERROR_TEMPLATE)

    def get_application_root(self):
        """Return a new Zope root for this request.
        """
        # This create the connection to the ZODB, wrap it in the
        # request.  After this, request.close must always be called.
        root = self.app.application.__bobo_traverse__(self.request)
        return root.__of__(RequestContainer(REQUEST=self.request))

    def get_path_and_method(self, root):
        """Return the path and the method of this request.
        """
        request = self.request
        path_info = request['PATH_INFO']

        # Inspect path
        path = list(reversed(split_path_info(path_info)))
        request['ACTUAL_URL'] = request['URL'] + quote(path_info)
        request['TraversalRequestNameStack'] = request.path = path
        request['PARENTS'] = [root]

        # Method
        method = request.get('REQUEST_METHOD', 'GET').upper()
        if method in ['GET', 'POST']:
            # index_html is still the default method, only any object can
            # override it by implementing its own __browser_default__ method
            method = 'index_html'

        if not path and not method:
            raise zExceptions.BadRequest(request['URL'])

        return method, path

    def publish(self):
        """Publish the request into the response.
        """
        self.start()

        # First check for "cancel" redirect ZMI-o-hardcoded thing:
        submit = self.request.get('SUBMIT', None)
        if submit is not None:
            if submit.strip().lower() == 'cancel':
                cancel = self.request.get('CANCEL_ACTION','')
                if cancel:
                    raise zExceptions.Redirect(cancel)

        # Get the path, method and root
        root = self.get_application_root()
        method, path = self.get_path_and_method(root)

        # Do some optional virtual hosting
        vhm = self.request.query_plugin(
            root, interfaces.IVirtualHosting)
        root, method, path = vhm(method, path)

        # Zope 2 style post traverser hooks
        self.request._post_traverse = post_traverse = []

        # Get object to publish/render
        traverser = self.request.query_plugin(root, interfaces.ITraverser)
        content = traverser(method, path)
        __traceback_supplement__ = (ErrorSupplement, content)

        # Zope 2 style post traverser hooks
        del self.request._post_traverse

        # Run authentication
        authenticator = self.request.query_plugin(
            content, interfaces.IAuthenticator)
        authenticator(Zope2.zpublisher_validated_hook)

        # Run Zope 2 style post traversal hooks
        if post_traverse:
            result = exec_callables(post_traverse)
            if result is not None:
                content = result

        notify(interfaces.PublicationAfterTraversal(self.request, content))

        # Render the content into the response
        self.app.transaction.recordMetaData(content, self.request)
        result = mapply(
            content, self.request.args, self.request,
            call_object, 1, missing_name, dont_publish_class,
            self.request, bind=1)

        if result is not None:
            self.response.setBody(result)

        notify(interfaces.PublicationAfterRender(self.request, content))

        return self.result()

    def publish_and_manage_errors(self):
        """Publish the request, manage errors.
        """
        def last_content():
            content = self.request.get('PUBLISHED')
            if content is None:
                parents = self.request.get('PARENTS')
                if parents:
                    return parents[0]
            return content

        try:
            return self.publish()
        except (ConflictError, Retry, AbortPublication):
            # Conflict are managed at an higher level
            raise
        except zExceptions.Unauthorized:
            # Manage unauthorized
            log_last_error(self.request, self.response, last_content())
            self.response.setStatus(401)
            try:
                # To be compatible with PAS
                self.response._unauthorized()
            except Exception:
                # The _unauthorised handler using PAS failed
                log_last_error(
                    self.request, self.response, obj=last_content(),
                    extra="Error while processing the unauthorized PAS handler")
                self.response.setStatus(401)
                self.response.setBody("")
                self.response.setHeader(
                    'WWW-Authenticate', 'basic realm="%s"' % self.response.realm)
        except zExceptions.Redirect as error:
            # Redirect
            self.response.redirect(str(error))
        except Exception as error:
            content = last_content()
            log_last_error(self.request, self.response, content)
            if self.response.debug_mode:
                # If debug mode is on, don't render anything for the error.
                raise

            self.error(error, content)

        # Return the result of the response
        return self.result()

    def publish_and_retry(self):
        """Publish the request into the response and retry if it
        fails.
        """
        try:
            data = self.publish_and_manage_errors()
        except (ConflictError, Retry):
            self.abort()
            self.publication_done = True
            if self.request.supports_retry() and not self.data_sent:
                # If can still retry, and didn't send any data yet, do it.
                logger.info('Conflict, retrying request %s' % (
                        reconstruct_url_from_environ(self.request.environ)))
                new_request = self.request.retry()
                try:
                    new_publication = self.__class__(
                        self.app, new_request, self.response)
                    data = new_publication.publish_and_retry()
                    self.publication_done = new_publication.publication_done
                finally:
                    new_request.close()
            else:
                # Otherwise, just render a plain error.
                logger.error('Conflict error for request %s' % (
                        reconstruct_url_from_environ(self.request.environ)))
                self.response.setStatus(503)
                self.response.setBody(RETRY_FAIL_ERROR_TEMPLATE)
                data = self.result()
        return data

    def __call__(self, cleanup=None):
        """Publish the request and send the result via an iterator.
        """
        try:
            data = self.publish_and_retry()
            self.response.startWSGIResponse()
            return WSGIResult(self.request, self, data, cleanup)
        except Exception:
            # In case of exception we didn't catch (like
            # AbortPublication), abort all the current transaction.
            self.abort()
            cleanup()
            raise


class WSGIApplication(object):
    """Zope WSGI application.
    """

    def __init__(self, application, transaction,
                 handle_errors=True, concurrency=4):
        self.application = application
        self.transaction = transaction
        self.memory_maxsize = 2 << 20
        self.handle_errors = handle_errors
        self.concurrency = threading.Semaphore(concurrency)

    def save_input(self, environ):
        """We want to save the request input in order to be able to
        retry a request: Zope need to be able to do .seek(0) on
        wsgi_input.
        """
        original_input = environ.get('wsgi.input')

        if original_input is not None:
            environ_length = environ.get('CONTENT_LENGTH')
            length = int(environ_length) if environ_length else 0
            if length > self.memory_maxsize:
                new_input = environ['wsgi.input'] = TemporaryFile('w+b')
            else:
                new_input = environ['wsgi.input'] = StringIO()
            to_read = length

            try:
                while to_read:
                    if to_read <= CHUNK_SIZE:
                        data = original_input.read(to_read)
                        to_read = 0
                    else:
                        data = original_input.read(CHUNK_SIZE)
                        to_read -= CHUNK_SIZE
                    new_input.write(data)
            except (socket.error, IOError):
                raise AbortPublication(started=False)

            new_input.seek(0)
            environ['wsgi.input'] = new_input

    def __call__(self, environ, start_response):
        """WSGI entry point.
        """
        try:
            debug_mode = not environ.get(
                'wsgi.handleErrors', self.handle_errors)
            self.save_input(environ)
            response = WSGIResponse(environ, start_response, debug_mode)
            request = WSGIRequest(environ['wsgi.input'], environ, response)
            publication = WSGIPublication(self, request, response)

            self.concurrency.acquire()
            def cleanup(context=None):
                request.close()
                self.concurrency.release()

            return publication(cleanup)
        except AbortPublication, error:
            if not error.response_started:
                msg = 'Socket error'
                start_response('400 Bad Request', [
                        ('Content-Type', 'text/plain'),
                        ('Content-Length', str(len(msg))),
                        ])
                return [msg]
            # Return nothing otherwise
            return []



ERROR_WHILE_RENDERING_ERROR_TEMPLATE = u"""
<html>
  <head>
    <title>Error</title>
  </head>
  <body>
     <h1>An error happened while rendering an error message</h1>
     <p>Sorry for the inconvenience.</p>
     <p>Please check the server logs for more information.</p>
  </body>
</html>
"""

DEFAULT_ERROR_TEMPLATE = u"""
<html>
  <head>
    <title>Error</title>
  </head>
  <body>
     <h1>An error happened</h1>
     <p>Sorry for the inconvenience.</p>
     <p>Please check the server logs for more information.</p>
  </body>
</html>
"""

RETRY_FAIL_ERROR_TEMPLATE = u"""
<html>
  <head>
    <title>Service temporarily unavailable</title>
  </head>
  <body>
     <h1>Your request cannot be processed at the moment</h1>
     <p>Please retry later.</p>
  </body>
</html>
"""



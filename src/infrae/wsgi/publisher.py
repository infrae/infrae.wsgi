# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from urlparse import urlparse
from tempfile import TemporaryFile
from cStringIO import StringIO
import socket
import types

from AccessControl.SecurityManagement import noSecurityManager
from Acquisition.interfaces import IAcquirer
from ZPublisher.Publish import Retry
from ZPublisher.Request import Request
from ZPublisher.mapply import mapply
from ZPublisher.pubevents import PubStart, PubSuccess, PubFailure, \
    PubBeforeCommit, PubAfterTraversal, PubBeforeAbort
from ZODB.POSException import ConflictError
from zope.component import queryMultiAdapter
from zope.event import notify
from zope.interface import implements
from zope.site.hooks import getSite
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.security.management import newInteraction, endInteraction
import Zope2
import zExceptions

from infrae.wsgi.errors import DefaultError
from infrae.wsgi.response import WSGIResponse, AbortPublication
from infrae.wsgi.log import logger, log_last_error, ErrorSupplement

CHUNK_SIZE = 1<<16              # 64K

def set_virtual_host(request, virtual_host):
    url = urlparse(virtual_host)
    if ':' in url.netloc:
        hostname, port = url.netloc.split(':', 1)
        request.setServerURL(url.scheme, hostname, int(port))
    else:
        request.setServerURL(url.scheme, url.netloc)
    request.setVirtualRoot(url.path.split('/'))


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
    implements(IDefaultBrowserLayer)


class WSGIResult(object):
    """Iterator to wrap Zope result, in order to commit/abort the
    transaction at the end of the iterator iteration, and to close the
    request at the end.
    """

    def __init__(self, request, publisher, data):
        self.__next = iter(data).next
        self.request = request
        self.publisher = publisher
        self.__iteration_done = False

    def next(self):
        try:
            return self.__next()
        except StopIteration:
            self.__iteration_done = True
            raise

    def __iter__(self):
        return self

    def close(self):
        try:
            if not self.__iteration_done:
                self.publisher.abort()
            else:
                self.publisher.finish()
        except ConflictError:
            self.publisher.abort()
            raise
        finally:
            # Always close the request, even if there errors while committing.
            self.request.close()


class WSGIPublication(object):
    """Publish a request through WSGI.
    """

    def __init__(self, app, request, response):
        self.app = app
        self.request = request
        self.response = response
        self.data_sent = False
        self.publication_done = False

    def __safe_callback(self, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception:
            log_last_error(self.request, self.response)

    def start(self):
        """Start the publication process.
        """
        notify(PubStart(self.request))
        newInteraction()
        noSecurityManager()
        self.app.transaction.begin()
        self.request.processInputs()

    def commit(self):
        """Commit results of the publication.
        """
        self.__safe_callback(notify, PubBeforeCommit(self.request))
        self.app.transaction.commit()
        endInteraction()
        self.__safe_callback(notify, PubSuccess(self.request))

    def abort(self):
        """Abort the current publication process.
        """
        self.__safe_callback(notify, PubBeforeAbort(self.request, None, False))
        self.app.transaction.abort()
        endInteraction()
        self.__safe_callback(notify, PubFailure(self.request, None, False))

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
        if not IAcquirer.providedBy(last_known_obj):
            last_known_site = getSite()
            if last_known_site is not None:
                last_known_obj = last_known_site
        context = DefaultError(error)
        if IAcquirer.providedBy(last_known_obj):
            context = context.__of__(last_known_obj)
        error_page = queryMultiAdapter(
            (context, self.request), name='error.html')

        if error_page is not None:
            try:
                error_result = error_page()
                if error_result is not None:
                    self.response.setBody(error_result)
            except Exception as error:
                log_last_error(
                    self.request, self.response, obj=last_known_obj,
                    extra=u"Error while rendering error message\n")
                self.response.setStatus(500)
                self.response.setBody(ERROR_WHILE_RENDERING_ERROR_TEMPLATE)
        else:
            logger.error('No action defined for last exception')
            self.response.setStatus(500)
            self.response.setBody(DEFAULT_ERROR_TEMPLATE)

    def publish(self):
        """Publish the request into the response.
        """
        parents = None
        published_content = None

        def last_content():
            content = published_content
            if content is None or isinstance(content, types.FunctionType):
                return parents[0] if parents is not None else None
            return content

        try:
            self.start()

            # First check for "cancel" redirect ZMI-o-hardcoded thing:
            submit = self.request.get('SUBMIT', None)
            if submit is not None:
                if submit.strip().lower() == 'cancel':
                    cancel = self.request.get('CANCEL_ACTION','')
                    if cancel:
                        raise zExceptions.Redirect(cancel)

            path = self.request.get('PATH_INFO')
            self.request['PARENTS'] = parents = [self.app.application,]

            # Get the virtual host story running
            # This should be in request __init__ but it needs
            # self.request['PARENTS'] to be set properly.
            if 'HTTP_X_VHM_HOST' in self.request.environ:
                set_virtual_host(
                    self.request,
                    self.request.environ['HTTP_X_VHM_HOST'])

            # Get object to publish/render
            published_content = self.request.traverse(
                path, validated_hook=Zope2.zpublisher_validated_hook)
            __traceback_supplement__ = (ErrorSupplement, published_content)

            notify(PubAfterTraversal(self.request))

            # Render the object into the response
            self.app.transaction.recordMetaData(published_content, self.request)
            result = mapply(published_content, self.request.args, self.request,
                            call_object, 1,
                            missing_name, dont_publish_class,
                            self.request, bind=1)

            if result is not None:
                self.response.setBody(result)
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
            data = self.publish()
        except (ConflictError, Retry) as error:
            self.abort()
            self.publication_done = True
            if self.request.supports_retry() and not self.data_sent:
                # If can still retry, and didn't send any data yet, do it.
                logger.info('Conflict, retrying request %s' % (
                        self.request['URL']))
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
                        self.request['URL']))
                self.response.setStatus(503)
                self.response.setBody(RETRY_FAIL_ERROR_TEMPLATE)
                data = self.result()
        return data

    def __call__(self):
        """Publish the request and send the result via an iterator.
        """
        try:
            data = self.publish_and_retry()
            self.response.startWSGIResponse()
            return WSGIResult(self.request, self, data)
        except Exception:
            # In case of exception we didn't catch (like
            # AbortPublication), abort all the current transaction.
            self.abort()
            self.request.close()
            raise


class WSGIApplication(object):
    """Zope WSGI application.
    """

    def __init__(self, application, transaction, default_handle_errors=True):
        self.application = application
        self.transaction = transaction
        self.memory_maxsize = 2 << 20
        self.default_handle_errors = default_handle_errors

    def save_input(self, environ):
        """We want to save the request input in order to be able to
        retry a request: Zope need to be able to do .seek(0) on
        wsgi_input.
        """
        original_input = environ.get('wsgi.input')

        if original_input is not None:
            length = int(environ.get('CONTENT_LENGTH', '0'))
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
                'wsgi.handleErrors', self.default_handle_errors)
            self.save_input(environ)
            response = WSGIResponse(environ, start_response, debug_mode)
            request = WSGIRequest(environ['wsgi.input'], environ, response)
            publication = WSGIPublication(self, request, response)

            return publication()
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



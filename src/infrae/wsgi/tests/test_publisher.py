# -*- coding: utf-8 -*-
# Copyright (c) 2010-2012 Infrae. All rights reserved.
# See also LICENSE.txt

from cStringIO import StringIO
import unittest
import logging

from zope.interface import implements
from zope.publisher.interfaces.http import IResult
from zope.event import notify

from ZODB.POSException import ConflictError
from ZPublisher.Iterators import IStreamIterator
import zExceptions

import infrae.wsgi
from infrae.testing import ZCMLLayer, get_event_names
from infrae.wsgi.publisher import WSGIPublication
from infrae.wsgi.response import WSGIResponse
from infrae.wsgi.tests.mockers import (
    MockWSGIStartResponse, MockTransactionManager, MockRequest, MockApplication)


DEFAULT_ENVIRON = {
    'wsgi.url_scheme': 'http',
    'SERVER_NAME': 'infrae.com',
    'SERVER_PORT': '80',
    'HTTP_HOST': 'infrae.com',
    'PATH_INFO': '/index.html'}

# Some test views

def hello_view():
    return 'Hello world!'


def no_content_view():
    return u''


def bugous_view():
    raise ValueError("I am not happy")


def invalid_view():
    return object()


def not_found_view():
    raise zExceptions.NotFound("I am not here!")


def redirect_view():
    raise zExceptions.Redirect("http://infrae.com/products/silva")


def unauthorized_view():
    raise zExceptions.Unauthorized("Please authenticate")


def forbidden_view():
    raise zExceptions.Forbidden("Go away")


# I don't know how to track this in a better way than a global variable.
confict_count = 0

def not_so_conflictuous_view():
    global conflict_count
    if conflict_count != 0:
        conflict_count -= 1
        raise ConflictError()
    return u'I worked fine'


class TestNextCalled(object):
    """Event triggered each time next() of a TestResult is called.
    """


class TestResult(object):
    """An IResult iterator returning data.
    """
    implements(IResult)

    def __init__(self, data, fail=False):
        self.__next = iter(data).next
        self.__fail = fail

    def __iter__(self):
        return self

    def next(self):
        notify(TestNextCalled())
        # Error testing
        if self.__fail:
            raise ValueError()
        # Else return data
        return self.__next()


def result_view():
    return TestResult(['Hello ', 'World'])


def bugous_result_view():
    return TestResult(['Hello ', 'World'], fail=True)


class TestStreamIterator(object):
    """An IStreamIterator iterator returning data.
    """
    implements(IStreamIterator)

    def __init__(self, data, length, fail=False):
        self.__next = iter(data).next
        self.__length = length
        self.__fail = fail

    def next(self):
        notify(TestNextCalled())
        # Error testing
        if self.__fail:
            raise ValueError()
        return self.__next()

    def __len__(self):
        return self.__length


def streamiterator_view():
    return TestStreamIterator(['It\'s the ', 'world.'], 42)


def bugous_streamiterator_view():
    return TestStreamIterator(['It\'s the ', 'world.'], 42, fail=True)


def consume_wsgi_result(iterator):
    result = ''
    try:
        for piece in iterator:
            result += str(piece)
    finally:
        if hasattr(iterator, 'close'):
            iterator.close()
    return result


class LoggingTesting(object):

    def __init__(self, name, level=logging.NOTSET):
        self.name = name
        self.level = level
        self.__logged = StringIO()
        self.__settings = {}
        self.__handler = logging.StreamHandler(self.__logged)
        self.__logger = logging.getLogger(name)
        self.__settings['level'] = self.__logger.getEffectiveLevel()
        self.__settings['propagate'] = self.__logger.propagate
        self.__logger.propagate = False
        self.__logger.setLevel(level)
        self.__logger.addHandler(self.__handler)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__logger.removeHandler(self.__handler)
        self.__logger.setLevel(self.__settings['level'])
        self.__logger.propagate = self.__settings['propagate']

    def __get_logs(self):
        self.__handler.flush()
        return self.__logged.getvalue()

    def assertEmpty(self, msg=None):
        log = self.__get_logs()
        if msg is None:
            msg = 'Unexpected log entries in %s logger' % self.name
        assert len(log) == 0, msg

    def assertNotEmpty(self, msg=None):
        log = self.__get_logs()
        if msg is None:
            msg = 'Missing expected log entries in %s logger' % self.name
        assert len(log) != 0, msg

    def assertEqual(self, expected):
        lines = filter(lambda s:s ,
                       map(lambda s: s.strip(),
                           self.__get_logs().split('\n')))
        assert expected == lines, '%s != %s' % (lines, expected)

    def assertContains(self, expected, msg=None):
        lines = filter(lambda s:s ,
                       map(lambda s: s.strip(),
                           self.__get_logs().split('\n')))
        if msg is None:
            msg = '\nLogs:\n\n%s \n\ndoesn\'t contains:\n\n %s' % (
                '\n'.join(lines), expected)
        assert expected in lines, msg


class PublisherTestCase(unittest.TestCase):
    """Test that the publisher triggers the correct actions at the
    correct time with the help of mockers.
    """
    layer = ZCMLLayer(infrae.wsgi)

    def setUp(self):
        class WSGIApplication(object):
            transaction = MockTransactionManager()
            application = MockApplication()
            response = MockWSGIStartResponse()

        self.app = WSGIApplication()
        self.response = WSGIResponse(DEFAULT_ENVIRON.copy(), self.app.response)

    def new_request_for(self, method):
        # Help to create a request that will be rendered by the given view.
        data = DEFAULT_ENVIRON.copy()
        data['URL'] = 'http://infrae.com/index.html'
        return MockRequest(
            data=data,
            view=method,
            response=self.response,
            retry=2)

    def test_hello_view(self):
        """Test a working view which says hello world.
        """
        request = self.new_request_for(hello_view)
        with LoggingTesting('infrae.wsgi') as logs:
            publication = WSGIPublication(self.app, request, self.response)
            result = publication(lambda: request.close())

            self.assertEqual(
                request.mocker_called(),
                [('processInputs', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(),
                [('begin', (), {}),
                 ('recordMetaData', (hello_view, request), {}),
                 ('commit', (), {})])
            self.assertEqual(
                self.app.response.status, '200 OK')
            self.assertEqual(
                self.app.response.headers,
                [('Content-Length', '12'),
                 ('Content-Type', 'text/html;charset=utf-8')])
            self.assertEqual(
                get_event_names(),
                ['PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationAfterRender',
                 'PublicationBeforeCommit',
                 'PublicationSuccess'])

            body = consume_wsgi_result(result)

            self.assertEqual(body, 'Hello world!')
            self.assertEqual(
                request.mocker_called(),  [('close', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(), [])
            self.assertEqual(
                get_event_names(), [])

            logs.assertEmpty()

    def test_no_content(self):
        """Test a working view with no content.
        """
        request = self.new_request_for(no_content_view)
        with LoggingTesting('infrae.wsgi') as logs:
            publication = WSGIPublication(self.app, request, self.response)
            result = publication(lambda: request.close())

            self.assertEqual(
                request.mocker_called(),
                [('processInputs', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(),
                [('begin', (), {}),
                 ('recordMetaData', (no_content_view, request), {}),
                 ('commit', (), {})])
            self.assertEqual(
                self.app.response.status, '204 No Content')
            self.assertEqual(
                self.app.response.headers,
                [('Content-Length', '0')])
            self.assertEqual(
                get_event_names(),
                ['PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationAfterRender',
                 'PublicationBeforeCommit',
                 'PublicationSuccess'])

            body = consume_wsgi_result(result)

            self.assertEqual(body, '')
            self.assertEqual(
                request.mocker_called(),  [('close', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(), [])
            self.assertEqual(
                get_event_names(), [])

            logs.assertEmpty()

    def test_result(self):
        """Test a view that return an object of type IResult. Since it
        is an iterator, commit/close will be only called after the
        iterator has be consumed.
        """
        request = self.new_request_for(result_view)
        with LoggingTesting('infrae.wsgi') as logs:
            publication = WSGIPublication(self.app, request, self.response)
            result = publication(lambda: request.close())


            self.assertEqual(
                request.mocker_called(),
                [('processInputs', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(),
                [('begin', (), {}),
                 ('recordMetaData', (result_view, request), {})])
            self.assertEqual(
                self.app.response.status, '200 OK')
            self.assertEqual(
                self.app.response.headers,
                [('Content-Type', 'text/html;charset=utf-8')])
            self.assertEqual(
                get_event_names(),
                ['PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationAfterRender',
                 'PublicationBeforeStreaming'])

            body = consume_wsgi_result(result)

            self.assertEqual('Hello World', body)
            self.assertEqual(
                request.mocker_called(),  [('close', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(), [('commit', (), {})])
            self.assertEqual(
                get_event_names(),
                ['TestNextCalled',
                 'TestNextCalled',
                 'TestNextCalled',
                 'PublicationBeforeCommit',
                 'PublicationSuccess'])

            logs.assertEmpty()

    def test_bugous_result(self):
        """test a view that return an IResult object, and does an
        error. The error is reported through the WSGI stack, but the
        transaction is aborted and the request is closed.
        """
        request = self.new_request_for(bugous_result_view)
        with LoggingTesting('infrae.wsgi') as logs:
            publication = WSGIPublication(self.app, request, self.response)
            result = publication(lambda: request.close())

            self.assertEqual(
                request.mocker_called(),
                [('processInputs', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(),
                [('begin', (), {}),
                 ('recordMetaData', (bugous_result_view, request), {})])
            self.assertEqual(
                self.app.response.status, '200 OK')
            self.assertEqual(
                self.app.response.headers,
                [('Content-Type', 'text/html;charset=utf-8')])
            self.assertEqual(
                get_event_names(),
                ['PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationAfterRender',
                 'PublicationBeforeStreaming'])

            self.assertRaises(ValueError, consume_wsgi_result, result)

            self.assertEqual(
                request.mocker_called(),  [('close', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(), [('abort', (), {})])
            self.assertEqual(
                get_event_names(),
                ['TestNextCalled',
                 'PublicationBeforeAbort',
                 'PublicationFailure'])

            logs.assertContains(
                "An error happened in the WSGI stack while iterating "
                "the result for the url 'http://infrae.com/index.html'")

    def test_result_with_conflict_error(self):
        """Test a view that return an object of type IResult, and does
        conflict error. Like for other iterator errors, the error is
        going throught the middleware stack, but the transaction is
        abort and the request is closed.
        """
        self.app.transaction.mocker_set_conflict(True)

        request = self.new_request_for(result_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication(lambda: request.close())

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (result_view, request), {})])
        self.assertEqual(
            self.app.response.status, '200 OK')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Type', 'text/html;charset=utf-8')])
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationAfterRender',
             'PublicationBeforeStreaming'])

        self.assertRaises(ConflictError, consume_wsgi_result, result)

        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('commit', (), {}),  ('abort', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled',
             'TestNextCalled',
             'TestNextCalled',
             'PublicationBeforeCommit',
             'PublicationBeforeAbort',
             'PublicationFailure'])

    def test_streamiterator(self):
        """Test a view that return an object of type
        IStreamIterator. It is basically an iterator like IResult, but
        it is able to give its size. commit/close will be called only
        at the end of the iteration.
        """
        request = self.new_request_for(streamiterator_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication(lambda: request.close())

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (streamiterator_view, request), {})])
        self.assertEqual(
            self.app.response.status, '200 OK')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '42'),
             ('Content-Type', 'text/html;charset=utf-8')])
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationAfterRender'])

        body = consume_wsgi_result(result)

        self.assertEqual('It\'s the world.', body)
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [('commit', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled',
             'TestNextCalled',
             'TestNextCalled',
             'PublicationBeforeCommit',
             'PublicationSuccess'])

    def test_bugous_streamiterator(self):
        """Test a view that return an object of type IStreamIterator,
        and does an error. The error is raised through the WSGI stack,
        but the transaction is aborted and the request is closed.
        """
        request = self.new_request_for(bugous_streamiterator_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication(lambda: request.close())

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (bugous_streamiterator_view, request), {})])
        self.assertEqual(
            self.app.response.status, '200 OK')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '42'),
             ('Content-Type', 'text/html;charset=utf-8')])
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationAfterRender'])

        self.assertRaises(ValueError, consume_wsgi_result, result)

        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [('abort', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled',
             'PublicationBeforeAbort',
             'PublicationFailure'])

    def test_streamiterator_with_conflict_error(self):
        """Test a view that return an object of type IStreamIterator,
        but does a conflict error while committing. The error goes
        throught the WSGI stack, but the transaction is aborted and
        the request is closed.
        """
        self.app.transaction.mocker_set_conflict(True)

        request = self.new_request_for(streamiterator_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication(lambda: request.close())

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (streamiterator_view, request), {})])
        self.assertEqual(
            self.app.response.status, '200 OK')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '42'),
             ('Content-Type', 'text/html;charset=utf-8')])
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationAfterRender'])

        self.assertRaises(ConflictError, consume_wsgi_result, result)

        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('commit', (), {}), ('abort', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled',
             'TestNextCalled',
             'TestNextCalled',
             'PublicationBeforeCommit',
             'PublicationBeforeAbort',
             'PublicationFailure'])

    def test_bugous_view(self):
        """Test a broken view.
        """
        request = self.new_request_for(bugous_view)
        with LoggingTesting('infrae.wsgi') as logs:
            publication = WSGIPublication(self.app, request, self.response)
            result = publication(lambda: request.close())

            self.assertEqual(
                request.mocker_called(),
                [('processInputs', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(),
                [('begin', (), {}),
                 ('recordMetaData', (bugous_view, request), {}),
                 ('abort', (), {})])
            self.assertEqual(
                self.app.response.status, '500 Internal Server Error')
            self.assertEqual(
               self.app.response.headers,
               [('Content-Length', '150'),
                ('Content-Type', 'text/html;charset=utf-8')])
            self.assertEqual(
                get_event_names(),
                ['PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationBeforeError',
                 'PublicationAfterRender',
                 'PublicationBeforeAbort',
                 'PublicationFailure'])

            body = consume_wsgi_result(result)

            self.assertTrue('I am not happy' in body)
            self.assertEqual(
                request.mocker_called(),  [('close', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(), [])
            self.assertEqual(
                get_event_names(), [])

            logs.assertNotEmpty()

    def test_invalid_view(self):
        """Test a view that doesn't return a string.
        """
        request = self.new_request_for(invalid_view)
        with LoggingTesting('infrae.wsgi') as logs:
            publication = WSGIPublication(self.app, request, self.response)
            result = publication(lambda: request.close())

            self.assertEqual(
                request.mocker_called(),
                [('processInputs', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(),
                [('begin', (), {}),
                 ('recordMetaData', (invalid_view, request), {}),
                 ('commit', (), {})])
            self.assertEqual(
                self.app.response.status, '200 OK')
            self.assertEqual(
               self.app.response.headers,
               [])
            self.assertEqual(
                get_event_names(),
                ['PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationAfterRender',
                 'PublicationBeforeCommit',
                 'PublicationSuccess'])

            consume_wsgi_result(result)

            self.assertEqual(
                request.mocker_called(),  [('close', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(), [])
            self.assertEqual(
                get_event_names(), [])

            logs.assertEqual(
                ["Invalid response data of type __builtin__.object "
                 "for url 'http://infrae.com/index.html'"])

    def test_not_found(self):
        """Test a view which does a not found exception.
        """
        request = self.new_request_for(not_found_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication(lambda: request.close())

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (not_found_view, request), {}),
             ('abort', (), {})])
        self.assertEqual(self.app.response.status, '404 Not Found')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '164'),
             ('Content-Type', 'text/html;charset=utf-8')])
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationBeforeError',
             'PublicationAfterRender',
             'PublicationBeforeAbort',
             'PublicationFailure'])

        body = consume_wsgi_result(result)

        self.assertTrue('Page not found' in body)
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [])
        self.assertEqual(
            get_event_names(), [])

    def test_redirect(self):
        """Test a view which raise a Redirect exception.
        """
        request = self.new_request_for(redirect_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication(lambda: request.close())

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (redirect_view, request), {}),
             ('commit', (), {})])
        self.assertEqual(self.app.response.status, '302 Moved Temporarily')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '0'),
             ('Location', 'http://infrae.com/products/silva')])
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationBeforeCommit',
             'PublicationSuccess'])

        body = consume_wsgi_result(result)

        self.assertEqual(body, '')
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [])
        self.assertEqual(
            get_event_names(), [])

    def test_unauthorized(self):
        """Test a view which raises an Unauthorized exception.
        """
        request = self.new_request_for(unauthorized_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication(lambda: request.close())

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (unauthorized_view, request), {}),
             ('commit', (), {})])
        self.assertEqual(self.app.response.status, '401 Unauthorized')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '0'),
             ('Www-Authenticate', 'basic realm="Zope"')])
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationBeforeCommit',
             'PublicationSuccess'])

        body = consume_wsgi_result(result)

        self.assertEqual(body, '')
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [])
        self.assertEqual(
            get_event_names(), [])

    def test_bugous_pas_handler(self):
        """Test than an error in a PAS unauthorized handler is contained.
        """
        request = self.new_request_for(unauthorized_view)
        with LoggingTesting('infrae.wsgi') as logs:
            response = WSGIResponse({}, self.app.response)
            response._unauthorized = bugous_view # Set the bugous handler
            publication = WSGIPublication(self.app, request, response)
            result = publication(lambda: request.close())

            self.assertEqual(
                request.mocker_called(),
                [('processInputs', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(),
                [('begin', (), {}),
                 ('recordMetaData', (unauthorized_view, request), {}),
                 ('commit', (), {})])
            self.assertEqual(self.app.response.status, '401 Unauthorized')
            self.assertEqual(
                self.app.response.headers,
                [('Content-Length', '0'),
                 ('Www-Authenticate', 'basic realm="Zope"')])
            self.assertEqual(
                get_event_names(),
                ['PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationBeforeCommit',
                 'PublicationSuccess'])

            body = consume_wsgi_result(result)

            self.assertEqual(body, '')
            self.assertEqual(
                request.mocker_called(),  [('close', (), {})])
            self.assertEqual(
                self.app.transaction.mocker_called(), [])
            self.assertEqual(
                get_event_names(), [])

            logs.assertContains(
                'Error while processing the unauthorized PAS handler')

    def test_forbidden(self):
        """Test a view which raises the Forbidden exception.
        """
        request = self.new_request_for(forbidden_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication(lambda: request.close())

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (forbidden_view, request), {}),
             ('commit', (), {})])
        self.assertEqual(self.app.response.status, '403 Forbidden')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '142'),
             ('Content-Type', 'text/html;charset=utf-8')])
        self.assertEqual(
            get_event_names(),
            ['PublicationStart',
             'PublicationAfterTraversal',
             'PublicationBeforeError',
             'PublicationAfterRender',
             'PublicationBeforeCommit',
             'PublicationSuccess'])

        body = consume_wsgi_result(result)

        self.assertTrue('Go away' in body)
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [])
        self.assertEqual(
            get_event_names(), [])

    def test_conflict_errors(self):
        """Test continuous conflict errors on a regular view.
        """
        self.app.transaction.mocker_set_conflict(True)

        request = self.new_request_for(hello_view)
        with LoggingTesting('infrae.wsgi') as logs:

            publication = WSGIPublication(self.app, request, self.response)
            body = consume_wsgi_result(publication(lambda: request.close()))

            self.assertEqual(
                self.app.transaction.mocker_called(),
                [('begin', (), {}),
                 ('recordMetaData', (hello_view, request), {}),
                 ('commit', (), {}),
                 ('abort', (), {}),
                 ('begin', (), {}),
                 ('recordMetaData', (hello_view, request), {}),
                 ('commit', (), {}),
                 ('abort', (), {}),
                 ('begin', (), {}),
                 ('recordMetaData', (hello_view, request), {}),
                 ('commit', (), {}),
                 ('abort', (), {})])
            self.assertEqual(
                self.app.response.status,
                '503 Service Unavailable')
            self.assertEqual(
                self.app.response.headers,
                [('Content-Length', '198'),
                 ('Content-Type', 'text/html;charset=utf-8')])
            self.assertTrue('Service temporarily unavailable' in body)
            self.assertEqual(
                get_event_names(),
                ['PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationAfterRender',
                 'PublicationBeforeCommit',
                 'PublicationBeforeAbort',
                 'PublicationFailure',
                 'PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationAfterRender',
                 'PublicationBeforeCommit',
                 'PublicationBeforeAbort',
                 'PublicationFailure',
                 'PublicationStart',
                 'PublicationAfterTraversal',
                 'PublicationAfterRender',
                 'PublicationBeforeCommit',
                 'PublicationBeforeAbort',
                 'PublicationFailure',])

            logs.assertContains(
                'Conflict error for request http://infrae.com/index.html')

    def test_conflict_errors_but_ok(self):
        """Test a view which works after triggering one conflict errors, itself.
        """
        self.app.transaction.mocker_set_conflict(1)

        request = self.new_request_for(hello_view)

        publication = WSGIPublication(self.app, request, self.response)
        body = consume_wsgi_result(publication(lambda: request.close()))

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {}), ('retry', (), {}),
             ('processInputs', (), {}), ('close', (), {}), ('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (hello_view, request), {}),
             ('commit', (), {}),
             ('abort', (), {}),
             ('begin', (), {}),
             ('recordMetaData', (hello_view, request), {}),
             ('commit', (), {})])
        self.assertEqual(self.app.response.status, '200 OK')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '12'),
             ('Content-Type', 'text/html;charset=utf-8')])
        self.assertEqual(body, 'Hello world!')
        self.assertEqual(
            get_event_names(),
             ['PublicationStart',
              'PublicationAfterTraversal',
              'PublicationAfterRender',
              'PublicationBeforeCommit',
              'PublicationBeforeAbort',
              'PublicationFailure',
              'PublicationStart',
              'PublicationAfterTraversal',
              'PublicationAfterRender',
              'PublicationBeforeCommit',
              'PublicationSuccess'])

    def test_conflict_errors_on_view_but_ok(self):
        """Test a view which works after triggering one conflict errors, itself.
        """
        global conflict_count
        conflict_count = 1

        request = self.new_request_for(not_so_conflictuous_view)
        publication = WSGIPublication(self.app, request, self.response)
        body = consume_wsgi_result(publication(lambda: request.close()))

        self.assertEqual(
            request.mocker_called(),
            [('processInputs', (), {}), ('retry', (), {}),
             ('processInputs', (), {}), ('close', (), {}), ('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('begin', (), {}),
             ('recordMetaData', (not_so_conflictuous_view, request), {}),
             ('abort', (), {}),
             ('begin', (), {}),
             ('recordMetaData', (not_so_conflictuous_view, request), {}),
             ('commit', (), {})])
        self.assertEqual(conflict_count, 0)
        self.assertEqual(self.app.response.status, '200 OK')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '13'),
             ('Content-Type', 'text/html;charset=utf-8')])
        self.assertEqual(body, 'I worked fine')
        self.assertEqual(
            get_event_names(),
             ['PublicationStart',
              'PublicationAfterTraversal',
              'PublicationBeforeAbort',
              'PublicationFailure',
              'PublicationStart',
              'PublicationAfterTraversal',
              'PublicationAfterRender',
              'PublicationBeforeCommit',
              'PublicationSuccess'])


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(PublisherTestCase))
    return suite

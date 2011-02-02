# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import unittest

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


# Some test views

def hello_view():
    return 'Hello world!'


def no_content_view():
    return u''


def bugous_view():
    raise ValueError("I am not happy")


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
        self.response = WSGIResponse({}, self.app.response)

    def new_request_for(self, method):
        # Help to create a request that will be rendered by the given view.
        return MockRequest(
            data={'PATH_INFO': '/', 'URL': 'http://infrae.com'},
            view=method,
            response=self.response,
            retry=2)

    def test_hello_view(self):
        """Test a working view which says hello world.
        """
        request = self.new_request_for(hello_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeCommit', 'PubSuccess'])

        body = consume_wsgi_result(result)

        self.assertEqual(body, 'Hello world!')
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [])
        self.assertEqual(
            get_event_names(), [])

    def test_no_content(self):
        """Test a working view with no content.
        """
        request = self.new_request_for(no_content_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeCommit', 'PubSuccess'])

        body = consume_wsgi_result(result)

        self.assertEqual(body, '')
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [])
        self.assertEqual(
            get_event_names(), [])

    def test_result(self):
        """Test a view that return an object of type IResult. Since it
        is an iterator, commit/close will be only called after the
        iterator has be consumed.
        """
        request = self.new_request_for(result_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeStreaming'])

        body = consume_wsgi_result(result)

        self.assertEqual('Hello World', body)
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [('commit', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled', 'TestNextCalled', 'TestNextCalled',
             'PubBeforeCommit', 'PubSuccess'])

    def test_bugous_result(self):
        """test a view that return an IResult object, and does an
        error. The error is reported through the WSGI stack, but the
        transaction is aborted and the request is closed.
        """
        request = self.new_request_for(bugous_result_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeStreaming'])

        self.assertRaises(ValueError, consume_wsgi_result, result)

        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [('abort', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled', 'PubBeforeAbort', 'PubFailure'])

    def test_result_with_conflict_error(self):
        """Test a view that return an object of type IResult, and does
        conflict error. Like for other iterator errors, the error is
        going throught the middleware stack, but the transaction is
        abort and the request is closed.
        """
        self.app.transaction.mocker_set_conflict(True)

        request = self.new_request_for(result_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeStreaming'])

        self.assertRaises(ConflictError, consume_wsgi_result, result)

        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('commit', (), {}),  ('abort', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled', 'TestNextCalled', 'TestNextCalled',
             'PubBeforeCommit', 'PubBeforeAbort', 'PubFailure'])

    def test_streamiterator(self):
        """Test a view that return an object of type
        IStreamIterator. It is basically an iterator like IResult, but
        it is able to give its size. commit/close will be called only
        at the end of the iteration.
        """
        request = self.new_request_for(streamiterator_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal'])

        body = consume_wsgi_result(result)

        self.assertEqual('It\'s the world.', body)
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [('commit', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled', 'TestNextCalled', 'TestNextCalled',
             'PubBeforeCommit', 'PubSuccess'])

    def test_bugous_streamiterator(self):
        """Test a view that return an object of type IStreamIterator,
        and does an error. The error is raised through the WSGI stack,
        but the transaction is aborted and the request is closed.
        """
        request = self.new_request_for(bugous_streamiterator_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal'])

        self.assertRaises(ValueError, consume_wsgi_result, result)

        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [('abort', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled', 'PubBeforeAbort', 'PubFailure'])

    def test_streamiterator_with_conflict_error(self):
        """Test a view that return an object of type IStreamIterator,
        but does a conflict error while committing. The error goes
        throught the WSGI stack, but the transaction is aborted and
        the request is closed.
        """
        self.app.transaction.mocker_set_conflict(True)

        request = self.new_request_for(streamiterator_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal'])

        self.assertRaises(ConflictError, consume_wsgi_result, result)

        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(),
            [('commit', (), {}), ('abort', (), {})])
        self.assertEqual(
            get_event_names(),
            ['TestNextCalled', 'TestNextCalled', 'TestNextCalled',
             'PubBeforeCommit', 'PubBeforeAbort', 'PubFailure'])

    def test_bugous_view(self):
        """Test a broken view.
        """
        request = self.new_request_for(bugous_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeAbort', 'PubFailure'])

        body = consume_wsgi_result(result)

        self.failUnless('I am not happy' in body)
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [])
        self.assertEqual(
            get_event_names(), [])

    def test_not_found(self):
        """Test a view which does a not found exception.
        """
        request = self.new_request_for(not_found_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeAbort', 'PubFailure'])

        body = consume_wsgi_result(result)

        self.failUnless('Page not found' in body)
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
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeCommit', 'PubSuccess'])

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
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeCommit', 'PubSuccess'])

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
        response = WSGIResponse({}, self.app.response)
        response._unauthorized = bugous_view # Set the bugous handler
        publication = WSGIPublication(self.app, request, response)
        result = publication()
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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeCommit', 'PubSuccess'])

        body = consume_wsgi_result(result)

        self.assertEqual(body, '')
        self.assertEqual(
            request.mocker_called(),  [('close', (), {})])
        self.assertEqual(
            self.app.transaction.mocker_called(), [])
        self.assertEqual(
            get_event_names(), [])

    def test_forbidden(self):
        """Test a view which raises the Forbidden exception.
        """
        request = self.new_request_for(forbidden_view)
        publication = WSGIPublication(self.app, request, self.response)
        result = publication()

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
            ['PubStart', 'PubAfterTraversal', 'PubBeforeCommit', 'PubSuccess'])

        body = consume_wsgi_result(result)

        self.failUnless('Go away' in body)
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
        publication = WSGIPublication(self.app, request, self.response)
        body = consume_wsgi_result(publication())

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
        self.assertEqual(self.app.response.status, '503 Service Unavailable')
        self.assertEqual(
            self.app.response.headers,
            [('Content-Length', '198'),
             ('Content-Type', 'text/html;charset=utf-8')])
        self.failUnless('Service temporarily unavailable' in body)
        self.assertEqual(
            get_event_names(),
            ['PubStart', 'PubAfterTraversal',
             'PubBeforeCommit', 'PubBeforeAbort', 'PubFailure',
             'PubStart', 'PubAfterTraversal',
             'PubBeforeCommit', 'PubBeforeAbort', 'PubFailure',
             'PubStart', 'PubAfterTraversal',
             'PubBeforeCommit', 'PubBeforeAbort', 'PubFailure',])

    def test_conflict_error_but_ok(self):
        """Test a view which works after triggering one conflict errors, itself.
        """
        global conflict_count
        conflict_count = 1

        request = self.new_request_for(not_so_conflictuous_view)
        publication = WSGIPublication(self.app, request, self.response)
        body = consume_wsgi_result(publication())

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
             ['PubStart', 'PubAfterTraversal', 'PubBeforeAbort', 'PubFailure',
              'PubStart', 'PubAfterTraversal', 'PubBeforeCommit', 'PubSuccess'])


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(PublisherTestCase))
    return suite

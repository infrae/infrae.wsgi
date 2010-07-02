# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from Acquisition import aq_base
from zExceptions.ExceptionFormatter import format_exception
from zope.browser.interfaces import IView

from cgi import escape
import sys
import logging
import collections

logger = logging.getLogger('infrae.wsgi')



def object_name(obj):
    return '%s.%s' % (obj.__class__.__module__, obj.__class__.__name__)


def object_path(obj):
    if hasattr(obj, 'getPhysicalPath'):
        return '/'.join(obj.getPhysicalPath())
    return 'n/a'


class ErrorSupplement(object):
    """Add more information about an error on a view in a traceback.
    """

    def __init__(self, cls):
        self.context = cls
        if IView.providedBy(cls):
            self.context = cls.context
        self.cls = cls

    def getInfo(self, as_html=0):
        info = list()
        info.append((u'Published class', object_name(self.cls),))
        info.append((u'Object path', object_path(self.context),))
        info.append(
            (u'Object type', getattr(self.context, 'meta_type', u'n/a',)))
        if not as_html:
            return '   - ' + '\n   - '.join(map(lambda x: '%s: %s' % x, info))

        return u'<p>Extra information:<br /><li>%s</li></p>' % ''.join(map(
                lambda x: u'<li><b>%s</b>: %s</li>' % (
                    escape(str(x[0])), escape(str(x[1]))),
                info))


class ErrorReporter(object):
    """Utility to help error reporting.
    """

    def __init__(self):
        self.__last_errors = collections.deque([], 20)
        self.__loggable_errors = [
            'NotFound', 'Redirect', 'Unauthorized', 'BrokenReferenceError']

    def is_loggable(self, error):
        """Tells you if this error is loggable.
        """
        error_name = error.__class__.__name__
        return error_name not in self.__loggable_errors

    def log_last_error(self, request, response, obj=None, extra=None):
        """Build an error report and log the last available error.
        """
        error_type, error_value, traceback = sys.exc_info()
        if (not response.debug_mode) and (not self.is_loggable(error_value)):
            return

        log_entry = ['\n']

        if extra is not None:
            log_entry.append(extra)

        if obj is not None:
            log_entry.append('Object class: %s\n' % object_name(obj))
            log_entry.append('Object path: %s\n' % object_path(obj))

        def log_request_info(title, key):
            value = request.get(key, 'n/a') or 'n/a'
            log_entry.append('%s: %s\n' % (title, value))

        log_request_info('Request URL', 'URL')
        log_request_info('Request method', 'method')
        log_request_info('User', 'AUTHENTICATED_USER')
        log_request_info('User-agent', 'HTTP_USER_AGENT')
        log_request_info('Refer', 'HTTP_REFERER')

        log_entry.extend(format_exception(error_type, error_value, traceback))
        self.log_error(request['URL'], ''.join(log_entry))


    def log_error(self, url, report):
        """Log a given error.
        """
        logger.error(report)
        self.__last_errors.append((url, report))


reporter = ErrorReporter()


def log_last_error(request, response, obj=None, extra=None):
    """Log the last triggered error.
    """
    reporter.log_last_error(request, response, obj=obj, extra=extra)

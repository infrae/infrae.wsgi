# -*- coding: utf-8 -*-
# Copyright (c) 2011-2012 Infrae. All rights reserved.
# See also LICENSE.txt

from OFS.interfaces import IObjectManager
from zExceptions import BadRequest
from urllib import quote


def reconstruct_url_from_environ(environ):
    """Reconstruct an URL from the WSGI environ.
    """
    # This code is taken from the PEP333
    url = environ['wsgi.url_scheme']+'://'

    if environ.get('HTTP_HOST'):
        url += environ['HTTP_HOST']
    else:
        url += environ['SERVER_NAME']

        if environ['wsgi.url_scheme'] == 'https':
            if environ['SERVER_PORT'] != '443':
               url += ':' + environ['SERVER_PORT']
        else:
            if environ['SERVER_PORT'] != '80':
               url += ':' + environ['SERVER_PORT']

    url += quote(environ.get('SCRIPT_NAME', ''))
    url += quote(environ.get('PATH_INFO', ''))
    if environ.get('QUERY_STRING'):
        url += '?' + environ['QUERY_STRING']
    return url


def split_path_info(path):
    """Split a path from a string as a list of components, removing
    what is useless.
    """
    result = []
    if not path:
        return result
    for item in path.split('/'):
        if item in ('REQUEST', 'aq_self', 'aq_base'):
            raise BadRequest(u"Invalid path %s" % path)
        if not item or item=='.':
            continue
        elif item == '..':
            if not len(result):
                raise BadRequest(u"Invalid path %s" % path)
            del result[-1]
        else:
            result.append(item)
    return result


def traverse(path, content, request=None):
    """Simple helper to traverse path from content, following only
    Zope 2 containers API.
    """
    for piece in path:
        if not IObjectManager.providedBy(content):
            raise BadRequest(
                u'Invalid path, not a container /%s.' % '/'.join(path))
        child = content._getOb(piece, None)
        if child is None:
            raise BadRequest(
                u'Invalid path, content not found /%s' % '/'.join(path))
        if request is not None:
            hook = getattr(child, '__before_publishing_traverse__', None)
            if hook is not None:
                hook(child, request)
            request['PARENTS'].append(child)
        content = child
    return content

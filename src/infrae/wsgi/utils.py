# -*- coding: utf-8 -*-
# Copyright (c) 2011 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$


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
            raise BadRequest(path)
        if not item or item=='.':
            continue
        elif item == '..':
            if not len(result):
                raise BadRequest(path)
            del result[-1]
        else:
            result.append(item)
    return result

# -*- coding: utf-8 -*-
# Copyright (c) 2010-2012 Infrae. All rights reserved.
# See also LICENSE.txt


def format_http_header(name):
    """This format an http header key.
    """
    return '-'.join(map(lambda s: s.capitalize(), name.split('-')))


class HTTPHeaders(dict):
    """Implement a case insensitive dictionary to store HTTP headers.
    """

    def __setitem__(self, key, value):
        dict.__setitem__(self, key.lower(), value)

    def __getitem__(self, key):
        return dict.__getitem__(self, key.lower())

    def update(self, values):
        for key, value in values:
            dict.__setitem__(self, key.lower(), value)

    def get(self, key, default=None):
        return dict.get(self, key.lower(), default)

    def has_key(self, key):
        return dict.has_key(self, key.lower())

    __contains__ = has_key

    def items(self):
        items = []
        for key, value in dict.items(self):
            items.append((format_http_header(key), str(value)))
        return items

    def iteritems(self):
        for key, value in dict.iteritems(self):
            yield((format_http_header(key), str(value)))

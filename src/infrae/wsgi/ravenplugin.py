# -*- coding: utf-8 -*-
# Copyright (c) 2013  Infrae. All rights reserved.
# See also LICENSE.txt

import raven
import raven.utils.wsgi as wsgi_utils
from .log import object_name, object_path


class RavenLoggingPlugin(object):

    def __init__(self, raven_config):
        self.client = raven.Client(**raven_config)

    def __call__(self, request, response, obj, error_info,
                 short_message, full_traceback, extra):
        raven_data = {
            'message': "".join(short_message),
            'sentry.interfaces.Http': {
                'url': request.get('URL', 'n/a'),
                'method': request.environ.get('REQUEST_METHOD', 'n/a'),
                'query_string': request.environ.get('QUERY_STRING', 'n/a'),
                'headers': dict(wsgi_utils.get_headers(request.environ)),
                'env': dict(wsgi_utils.get_environ(request.environ))
                }}
        raven_extra = {
            'User':  request.get('AUTHENTICATED_USER', 'n/a') or 'n/a'}
        if obj is not None:
            raven_extra.update({
                    'Object Class': object_name(obj),
                    'Object Name': object_path(obj),
                    })
        if extra is not None:
            raven_extra.update({
                    'Extra Information': extra
                    })

        self.client.captureException(
            exc_info=error_info, data=raven_data, extra=raven_extra)

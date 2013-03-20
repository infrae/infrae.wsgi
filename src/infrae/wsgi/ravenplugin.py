
import raven.utils.wsgi
from .log import object_name, object_path


class RavenLoggingPlugin(object):

    def __init__(self, raven_config):
        self.client = raven.Client(**raven_config)

    def __call__(self, request, response, obj, error_info,
                 short_message, full_traceback, extra):
        self.client.captureException(
            exc_info=error_info,
            data={
                'message': "".join(short_message),
                'sentry.interfaces.Http': {
                    'url': request.get('URL', 'n/a'),
                    'method': request.environ.get('REQUEST_METHOD', 'n/a'),
                    'query_string': request.environ.get('QUERY_STRING', 'n/a'),
                    'headers': dict(raven.utils.wsgi.get_headers(request.environ)),
                    'env': dict(raven.utils.wsgi.get_environ(request.environ))
                    }
                }, extra = {
                'Object Class': object_name(obj),
                'Object Name': object_path(obj),
                'Extra Information': extra or '',
                })

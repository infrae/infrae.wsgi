# -*- coding: utf-8 -*-
# Copyright (c) 2011-2012 Infrae. All rights reserved.
# See also LICENSE.txt

from five import grok
from zope.interface import Interface
from infrae.wsgi.interfaces import IRequest, IAuthenticator

from ZPublisher.BaseRequest import UNSPECIFIED_ROLES, old_validation
from zExceptions import Unauthorized


class ZopeAuthenticator(grok.MultiAdapter):
    """After traversing, authenticate using Zope method.
    """
    grok.adapts(Interface, IRequest)
    grok.provides(IAuthenticator)
    grok.implements(IAuthenticator)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def validate(self, content):
        auth = self.request._auth
        groups = content.__allow_groups__
        if hasattr(groups, 'validate'):
            if self.request.roles is UNSPECIFIED_ROLES:
                user = groups.validate(self.request, auth)
            else:
                user = groups.validate(self.request, auth, self.request.roles)
        else:
            user = old_validation(groups, self.request, auth, self.request.roles)
        return user

    def __call__(self, validated_hook=None):
        user = None

        # Authenticate user on the published object if available
        if hasattr(self.context, '__allow_groups__'):
            user = self.validate(self.context)

        index = 0
        if user is None:
            # Or on the first possible parent.
            parents = self.request['PARENTS']
            while index < len(parents):
                if hasattr(parents[index], '__allow_groups__'):
                    user = self.validate(parents[index])
                    if user is not None:
                        break
                index += 1

        if user is None:
            # Not authenticated
            if self.request.roles != UNSPECIFIED_ROLES:
                raise Unauthorized('Please authenticate')
        else:
            # Authenticated
            if validated_hook is not None:
                validated_hook(self.request, user)
            self.request['AUTHENTICATED_USER']=user
            self.request['AUTHENTICATION_PATH']='/'.join(
                self.request.steps[:-index])

        return user

# -*- coding: utf-8 -*-
# Copyright (c) 2010-2013 Infrae. All rights reserved.
# See also LICENSE.txt

from infrae.testing import suite_from_package, TestCase
from infrae.wsgi.testing.layer import BrowserLayer
from infrae.wsgi.testing.request import TestRequest
try:
    from infrae.wsgi.testing.intercept import (
        ZopeBrowserLayer, ZopeBrowser, http)
except ImportError:
    pass

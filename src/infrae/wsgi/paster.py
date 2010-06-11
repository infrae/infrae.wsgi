# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import logging
import pdb
import sys

from Zope2 import startup
from Zope2.Startup.run import configure
from infrae.wsgi.publisher import WSGIApplication
import Zope2

logger = logging.getLogger('infrae.wsgi')


def set_zope_debug_mode(debug_mode):
    """Set the Zope debug mode to the given value.
    """
    import App.config
    config = App.config.getConfiguration()
    config.debug_mode = debug_mode and 1 or 0
    import Globals
    Globals.DevelopmentMode = config.debug_mode


def zope2_application_factory(global_conf, zope_conf, **options):
    """Build a Zope2 WSGI application.
    """
    del sys.argv[1:]
    debug_mode = options.get('debug_mode', 'off') == 'on'

    configure(zope_conf)
    set_zope_debug_mode(debug_mode)
    logger.info("Zope configured")

    try:
        startup()
    except Exception:
        if debug_mode:
            # If debug_mode is on, debug possible starting errors.
            print "%s:" % sys.exc_info()[0]
            print sys.exc_info()[1]
            pdb.post_mortem(sys.exc_info()[2])
        raise

    # Some products / Zope code reset the debug mode. Re-set it again.
    set_zope_debug_mode(debug_mode)
    logger.info("Zope started")

    return WSGIApplication(
        Zope2.bobo_application,
        Zope2.zpublisher_transactions_manager,
        not debug_mode)


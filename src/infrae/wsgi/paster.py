# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import logging
import pdb
import sys

from Zope2 import startup
from infrae.wsgi.publisher import WSGIApplication
from zope.event import notify
from zope.processlifetime import ProcessStarting
import Zope2

logger = logging.getLogger('infrae.wsgi')


def configure_zope(config_filename, debug_mode=False):
    """Read zope.conf with zdaemon^Wzcrap.
    """
    from Zope2.Startup import options, handlers
    import AccessControl
    import App.config

    del sys.argv[1:]
    opts = options.ZopeOptions()
    opts.configfile = config_filename
    opts.realize(raise_getopt_errs=0)

    handlers.handleConfig(opts.configroot, opts.confighandlers)
    AccessControl.setImplementation(
        opts.configroot.security_policy_implementation)
    AccessControl.setDefaultBehaviors(
        not opts.configroot.skip_ownership_checking,
        not opts.configroot.skip_authentication_checking,
        opts.configroot.verbose_security)
    App.config.setConfiguration(opts.configroot)
    set_zope_debug_mode(debug_mode)


def set_zope_debug_mode(debug_mode):
    """Set the Zope debug mode to the given value.
    """
    import App.config
    config = App.config.getConfiguration()
    config.debug_mode = debug_mode and 1 or 0
    import Globals
    Globals.DevelopmentMode = config.debug_mode


def boot_zope(config_filename, debug_mode=False):
    """Boot Zope.
    """
    starter = configure_zope(config_filename, debug_mode)
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

    # Notify start of application
    notify(ProcessStarting())
    logger.info("Zope started")


def zope2_application_factory(global_conf, zope_conf, **options):
    """Build a Zope2 WSGI application.
    """
    debug_mode = options.get('debug_mode', 'off') == 'on'
    boot_zope(zope_conf, debug_mode)

    return WSGIApplication(
        Zope2.bobo_application,
        Zope2.zpublisher_transactions_manager,
        not debug_mode)


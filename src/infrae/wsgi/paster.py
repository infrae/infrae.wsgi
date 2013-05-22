# -*- coding: utf-8 -*-
# Copyright (c) 2010-2013 Infrae. All rights reserved.
# See also LICENSE.txt

import threading
import logging
import pdb
import sys

from Zope2 import startup
from infrae.wsgi.publisher import WSGIApplication
from infrae.wsgi.log import reporter
from zope.event import notify
from zope.processlifetime import ProcessStarting
import App.config
import Zope2

logger = logging.getLogger('infrae.wsgi')
bootstrap_lock = threading.Lock()
bootstrap_done = False


def configure_zope(config_filename, debug_mode=False):
    """Read zope.conf with zdaemon^Wzcrap.
    """
    from Zope2.Startup import options, handlers
    import AccessControl

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
    config = App.config.getConfiguration()
    config.debug_mode = debug_mode and 1 or 0
    import Globals
    Globals.DevelopmentMode = config.debug_mode


def mount_all_databases():
    """Call this to mount all available Zope databases.
    """
    config = App.config.getConfiguration()
    connection = Zope2.DB.open()
    root = connection.root()['Application']
    for path, name in config.dbtab.listMountPaths():
        if path != '/':
            try:
                # Get the database.
                # If it doesn't exist yet, it will be created.
                config.dbtab.getDatabase(name=name)
                try:
                    root.unrestrictedTraverse(path)
                    logger.info("Mounted %s on %s" % (name, path))
                except KeyError:
                    logger.info("Skipping mount %s on %s (traversal failed; possibly not set up yet." % (name, path))
            except AttributeError:
                pass
    connection.close()


def boot_zope(config_filename, debug_mode=False):
    """Boot Zope.
    """
    global bootstrap_done
    bootstrap_lock.acquire()
    try:
        if bootstrap_done:
            logger.info("Zope already configured, skipping configuration")
            return
        configure_zope(config_filename, debug_mode)
        logger.info("Zope configured")

        try:
            startup()
            mount_all_databases()
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
        bootstrap_done = True
        logger.info("Zope started")
    finally:
        bootstrap_lock.release()

def parse_raven_config(options):
    config = configuration_dict(options, 'raven', sep=".")
    for key in ['exclude_paths', 'include_paths', 'processors']:
        if key in config:
            value = configuration_list(config[key])
            if value:
                config[key] = value
    if config:
        from .ravenplugin import RavenLoggingPlugin
        reporter.subscribe_to_errors(RavenLoggingPlugin(config))

def zope2_application_factory(global_conf, zope_conf, **options):
    """Build a Zope2 WSGI application.
    """
    parse_raven_config(options)

    debug_mode = options.get('debug_mode', 'off') == 'on'
    zope_workers = configuration_int(options, 'zope_workers')
    boot_zope(zope_conf, debug_mode)

    # By default debug mode does not render exceptions as error pages
    # but allow them to propagate to outer wsgi middlewares
    # (e.g. z3c.evalexception). Setting this to 'off' will disable the
    # propagation
    debug_exceptions = (debug_mode and
                        options.get('debug_exceptions', 'on') == 'on')

    ignore_errors = configuration_list(options, 'ignore_errors')
    if ignore_errors:
        reporter.ignore_errors(ignore_errors)
    show_errors = configuration_list(options, 'show_errors')
    if show_errors:
        reporter.show_errors(show_errors)

    return WSGIApplication(
        Zope2.bobo_application,
        Zope2.zpublisher_transactions_manager,
        debug_mode,
        debug_exceptions,
        zope_workers)

# Utilities to read configuration options from paster file

def configuration_dict(options, key, sep="."):
    key_sep = key + sep
    result = {}
    for key, value in options.iteritems():
        if key.startswith(key_sep):
            prefix, result_key = key.split(sep, 1)
            value = value.strip()
            if value:
                result[result_key] = value
    return result

def configuration_list(options, key, default=''):
    return filter(lambda value: value,
                  map(lambda value: value.strip(),
                      options.get(key, default).split(',')))

def configuration_int(options, key, default='4'):
    value = options.get(key, default)
    try:
        return int(value)
    except:
        return int(default)

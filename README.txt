===========
infrae.wsgi
===========

``infrae.wsgi`` provides a support to run Zope 2 as a WSGI application.

.. contents::

Introduction
============

It basically does the same work than:

- ``repoze.zope2``,

- Zope 2 new builtin WSGI publisher.

Except than:

- It work with real Zope 2 applications and no monkey-patches,

- It pay specially attention to properly implement streaming. You can
  use your ZODB connection while streaming, (either with the
  ``.write`` method of request, or returning an ``IResult`` or an
  ``IStreamIterator`` iterator). ConflictError generate a final error
  if they happens during a streaming operation, not re-sending things
  again on the same HTTP connection,

- All ConflictError are properly managed.

- All those cases are tested.

It does not:

- Provide Zope 2 as a collection of WSGI middlewares, as Zope 2 paradigm /
  code base is not good for it,

- Do all fancy request body changes that old Zope 2 publisher does, as
  nobody use it anymore since a very long time.

Errors
------

Error messages are handled a bit differently than in
traditional Zope 2, in order to make things simpler.

They are views on errors (called ``error.html``), and wrapped in
acquisition around the context where they happened::

   from five import grok

   class CorpError(Exception):
       """Custom corporate error.
       """

   class CorpErrorMessage(grok.View):
       grok.context(CorpError)
       grok.name('error.html')

       def render(self):
           # aq_parent(self) is where the error happened
           return u'I Failed: %s' % str(self.error.args)


Errors are logged with useful information:

- Which is the URL triggering this error,

- The user-agent,

- The referent,

- The logged in username,

- On which object, its physical path and meta_type if possible.

The error log can be accessible online via ``/errorlog.html`` on any
Zope 2 content.

Errors can also be sent to a Sentry service (see Paste Deploy section).

The error log ignores certain errors by default: NotFound, Redirect,
Unauthorized, Forbidden, BadRequest, BrokenReferenceError.  The errlog.html page
has a form configure some (or all) of these errors to not be ignored.  This is
not a persistent setting and is forgotten on restart.

Installation
============

``infrae.wsgi`` has been and deployed with Paste Deploy and
``mod_wsgi``. It correctly respect the WSGI specification and should
work with any WSGI server.

Paste Deploy
------------

The application is available with the entry point
``infrae.wsgi#zope2``.

It expect an option variable called ``zope_conf`` that point to the
Zope 2 configuration file.

The option ``debug_mode`` can as well be specified, to run Zope in
debug mode. In debug mode, error pages will not be rendered by Zope
and the errors will propagate in the WSGI stack. This behavior will
let you debug errors with specialized middlewares.

To disable the error propagation in debug mode, the option
``debug_exceptions`` can be set to ``off``.

The option ``zope_workers`` can be used to specify the maximum of
threads Zope should allow to process requests at the same time
(default to ``4``). This can be usefull if you wish to allow more
threads in your wsgi environment, in case you have middlewares or
other applications that intercept the requests and support more
threads than Zope does.

The option ``show_errors`` accepts a comma-separated list of
errors which will not be ignored. This overrides the default list of
ignored errors (see the Errors section, above)

The option ``ignore_errors`` accepts a comma-separated list of errors
which will be ignored. This overrides the default list of ignored
errors too.

The configuration accepts options for `Raven`_ (Sentry's client)::

  raven.dsn = http://public:secret@example.com/1
  raven.include_paths = my.package, my.other.package
  raven.exclude_paths = my.package.crud

Those options requires `Raven`_ to be installed.

Virtual Hosting
---------------

You can add two headers in your proxy in order to control the virtual
hosting:

- ``X-VHM-URL``: That would the complete URL of your site, at which
  you want to see your Zope application, like
  ``http://www.mysite.com/application``.

- ``X-VHM-Path``: That would be an optional path to the Zope folder
  you see at the given URL instead of the Zope root, lile
  ``/my/folder``.


Testing
=======

A layer inheriting of `infrae.testing`_ ``Zope2Layer`` layer called
``BrowserLayer`` let you write functional tests.

It provides both an ``http`` function and a ``Browser`` class (like
the one provided by ``zope.testbrowser``) that you can use, and that
will connect to the tested application using the WSGI support provided
by this package.

This will let you do functional testing, and things will work exactly
like in your browser, as the requests will be processed the same way
than they are in real life (which is not really the case with the
``Testing`` module of Zope 2).

You will be actually able to test applications that do use streaming::


   import unittest

   from infrae.wsgi.testing import Browser, BrowserLayer
   import corp.testpackage


   class CorpTestCase(unittest.TestCase):
      layer = BrowserLayer(corp.testpackage)

      def setUp(self):
          self.root = self.layer.get_application()
          # Create some test content

      def test_feature(self):
          browser = Browser()
          browser.open('http://localhost/somepage')
          self.assertEqual(browser.status, 200)
          ...


.. _infrae.testing: http://pypi.python.org/pypi/infrae.testing
.. _Raven: http://raven.readthedocs.org/en/latest/

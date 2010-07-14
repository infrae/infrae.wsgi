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
debug mode.


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

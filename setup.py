# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from setuptools import setup, find_packages
import os

version = '1.4dev'

tests_require = [
    'infrae.testing',
    'wsgi_intercept',
    'zope.site',
    'zope.testbrowser',
    ]

setup(name='infrae.wsgi',
      version=version,
      description="WSGI support for Zope 2",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      classifiers=[
          "Environment :: Web Environment",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: Zope Public License",
          "Programming Language :: Python",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Framework :: Zope2",
          ],
      keywords='zope2 wsgi silva infrae',
      author='Sylvain Viollon',
      author_email='info@infrae.com',
      url='https://github.com/infrae/infrae.wsgi',
      license='ZPL',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      namespace_packages=['infrae'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        'Zope2 >= 2.12.4',
        'five.grok',
        'setuptools',
        'zope.event',
        'zope.interface',
        'zope.publisher',
        'zope.security',
        'zope.component',
        'zope.processlifetime'
        ],
      entry_points={
        'paste.app_factory': [
            'zope2 = infrae.wsgi.paster:zope2_application_factory',
            ],
        },
      tests_require = tests_require,
      extras_require = {'test': tests_require},
      )

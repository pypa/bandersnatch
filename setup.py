# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(name='bandersnatch',
      version='1.0dev',
      description='Mirroring tool that implements the client (mirror) side of PEP 381',
      long_description=open('README').read(),
      author='Christian Theune',
      author_email='ct@gocept.com',
      license = 'Academic Free License, version 3',
      url='http://bitbucket.org/ctheune/bandersnatch/',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      include_package_data=True,
      install_requires=[
          'distribute',
          'mock',
          'pytest',
          'pytest-cov',
          'requests',
          ],
      entry_points="""
            [console_scripts]
                bsn-mirror = bandersnatch.mirror:main
                bsn-processlogs = bandersnatch.apache_stats:main
      """)

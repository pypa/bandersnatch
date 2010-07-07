#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
from pep381client import version

setup(name='pep381client',
      version=version,
      description='Mirroring tool that implements the client (mirror) side of PEP 381',
      long_description=open('README').read(),
      author='Martin v. Loewis',
      author_email='martin@v.loewis.de',
      license = 'Academic Free License, version 3',
      url='http://bitbucket.org/loewis/pep381client/',
      packages=['pep381client'],
      scripts=['pep381run', 'mvindex', 'processlogs']
     )

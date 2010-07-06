#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup

setup(name='pep381client',
      version='1.3',
      description='Mirroring tool that implements the client (mirror) side of PEP 381',
      long_description=open('README').read(),
      author='Martin v. Loewis',
      author_email='martin@v.loewis.de',
      license = 'Academic Free License, version 3',
      url='http://bitbucket.org/loewis/pep381client/',
      packages=['pep381client'],
      scripts=['pep381run','processlogs']
     )

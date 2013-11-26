# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(name='bandersnatch',
      version='1.1',
      description='Mirroring tool that implements the client (mirror) side of PEP 381',
      long_description='\n\n'.join(
          [open('README').read(), open('CHANGES.txt').read()]),
      author='Christian Theune',
      author_email='ct@gocept.com',
      license='Academic Free License, version 3',
      url='http://bitbucket.org/ctheune/bandersnatch/',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      include_package_data=True,
      install_requires=[
          'setuptools',
          'mock',
          'pytest',
          'pytest-capturelog',
          'pytest-codecheckers',
          'pytest-cov',
          'pytest-timeout',
          'pytest-cache',
          'requests',
          'pdbpp'
          ],
      entry_points="""
            [console_scripts]
                bandersnatch = bandersnatch.main:main
            [zc.buildout]
                requirements = bandersnatch.buildout:Requirements

            [zest.releaser.prereleaser.after]
                update_requirements = bandersnatch.release:update_requirements
            [zest.releaser.releaser.after]
                update_stable_tag = bandersnatch.release:update_stable_tag
            [zest.releaser.postreleaser.after]
                update_requirements = bandersnatch.release:update_requirements
      """,
      classifiers=[
          'Programming Language :: Python :: 2.7'])

# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(name='pep381client',
      version='1.5',
      description='Mirroring tool that implements the client (mirror) side of PEP 381',
      long_description=open('README').read(),
      author='Martin v. Loewis',
      author_email='martin@v.loewis.de',
      license = 'Academic Free License, version 3',
      url='http://bitbucket.org/loewis/pep381client/',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      include_package_data=True,
      install_requires=[
          'distribute',
          'requests'],
      entry_points="""
            [console_scripts]
                pep381sync = pep381client.mirror:main
                pep381processlogs = pep381client.scripts.processlogs:main
                pep381check = pep381client.scripts.check:main
      """)

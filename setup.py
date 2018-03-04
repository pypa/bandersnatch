#!/usr/bin/env python3

from setuptools import setup, find_packages
from src.bandersnatch import __version__

# Naming these to use with tests_require
# - Bitbucket Pipelines will use requirements.txt for test deps
test_deps = [
    'flake8',
    'pep8',
    'pytest',
    'pytest-catchlog',
    'pytest-codecheckers',
    'pytest-cov',
    'pytest-timeout',
    'pytest-cache',
    'setuptools',  # tox tests require this - No idea why yet - @cooperlees
    'tox',
]

install_deps = [
    'packaging',
    'requests',
    'xmlrpc2',
]

setup(
    name='bandersnatch',
    version=__version__,
    description=(
        'Mirroring tool that implements the client (mirror) side of PEP 381'
    ),
    long_description='\n\n'.join(
        [open('README').read(), open('CHANGES.txt').read()]
    ),
    author='Christian Theune',
    author_email='ct@flyingcircus.io',
    license='Academic Free License, version 3',
    url='http://bitbucket.org/pypa/bandersnatch/',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    install_requires=install_deps,
    tests_require=test_deps,
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
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)

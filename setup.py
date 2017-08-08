#!/usr/bin/env python3

from setuptools import setup, find_packages

# TODO: Since we don't include test src in main pip package we should
# exclude these dependences from the install_deps - Need to be better @ tox
test_deps = [
    'flake8',
    'pep8',
    'pytest',
    'pytest-catchlog',
    'pytest-codecheckers',
    'pytest-cov',
    'pytest-timeout',
    'pytest-cache',
    'tox',
]

install_deps = [
    'setuptools',  # tox tests will fail without this
    'packaging',
    'requests',
    'xmlrpc2',
]

setup(
    name='bandersnatch',
    version='2.1.1.dev0',
    description='Mirroring tool that implements the client (mirror) side of PEP 381',
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
    install_requires=install_deps + test_deps,  # tox seems to need them all specified
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
      classifiers=['Programming Language :: Python :: 3.5'],
)

#!/usr/bin/env python3

from setuptools import find_packages, setup

from src.bandersnatch import __version__

install_deps = [
    'aiodns',
    'aiohttp',
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
        [open('README.md').read(), open('CHANGES.md').read()]
    ),
    long_description_content_type="text/markdown",
    author='Christian Theune',
    author_email='ct@flyingcircus.io',
    license='Academic Free License, version 3',
    url='http://bitbucket.org/pypa/bandersnatch/',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    install_requires=install_deps,
    entry_points="""
            [bandersnatch_filter_plugins.project]
                blacklist_project = bandersnatch_filter_plugins.blacklist_name:BlacklistProject
                whitelist_project = bandersnatch_filter_plugins.whitelist_name:WhitelistProject
            [bandersnatch_filter_plugins.release]
                blacklist_release = bandersnatch_filter_plugins.blacklist_name:BlacklistRelease
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
      """,  # noqa
    classifiers=[
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)

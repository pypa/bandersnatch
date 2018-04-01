#!/usr/bin/env python3

from setuptools import setup, find_packages
from src.bandersnatch import __version__

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

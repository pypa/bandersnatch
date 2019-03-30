#!/usr/bin/env python3

from sys import version_info

from setuptools import find_packages, setup

from src.bandersnatch import __version__

assert version_info >= (3, 6, 1), "bandersnatch requires Python >=3.6.1"


INSTALL_DEPS = ("aiohttp", "filelock", "packaging", "requests", "setuptools", "xmlrpc2")


setup(
    name="bandersnatch",
    version=__version__,
    description=("Mirroring tool that implements the client (mirror) side of PEP 381"),
    long_description="\n\n".join([open("README.md").read(), open("CHANGES.md").read()]),
    long_description_content_type="text/markdown",
    author="Christian Theune",
    author_email="ct@flyingcircus.io",
    license="Academic Free License, version 3",
    url="https://github.com/pypa/bandersnatch/",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=INSTALL_DEPS,
    entry_points="""
            [bandersnatch_filter_plugins.project]
                blacklist_project = bandersnatch_filter_plugins.blacklist_name:BlacklistProject
                whitelist_project = bandersnatch_filter_plugins.whitelist_name:WhitelistProject
                regex_project = bandersnatch_filter_plugins.regex_name:RegexProjectFilter
            [bandersnatch_filter_plugins.release]
                blacklist_release = bandersnatch_filter_plugins.blacklist_name:BlacklistRelease
                prerelease_release = bandersnatch_filter_plugins.prerelease_name:PreReleaseFilter
                regex_release = bandersnatch_filter_plugins.regex_name:RegexReleaseFilter
                latest_release = bandersnatch_filter_plugins.latest_name:LatestReleaseFilter
            [bandersnatch_filter_plugins.filename]
                exclude_platform = bandersnatch_filter_plugins.filename_name:ExcludePlatformFilter
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
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
)

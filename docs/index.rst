.. documentation master file
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Bandersnatch documentation
==========================

bandersnatch is a PyPI mirror client according to `PEP 381`
https://www.python.org/dev/peps/pep-0381/.

Bandersnatch hits the XMLRPC API of pypi.org to get all packages with serial
or packages since the last run's serial. bandersnatch then uses the JSON API
of PyPI to get shasums and release file paths to download and workout where
to layout the package files on a POSIX file system.

As of 6.0:

- Supports PEP691
  - HTML + JSON Simple Index

As of 4.0:

- Is fully asyncio based (mainly via aiohttp)
- Only stores PEP503 nomalized packages names for the /simple API
- Only stores JSON in normalized package name path too


.. sphinx_argparse_cli::
  :module: bandersnatch.main
  :func: _make_parser
  :title: Command line usage

Contents
--------

.. toctree::
    :maxdepth: 4

    installation
    storage_options
    mirror_configuration
    filtering_configuration
    serving
    CONTRIBUTING
    modules

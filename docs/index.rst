.. documentation master file
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Bandersnatch documentation
============

bandersnatch is a PyPI mirror client according to `PEP 381`
http://www.python.org/dev/peps/pep-0381/.

Bandersnatch hits the XMLRPC API of pypi.org to get all packages with serial
or packages since the last run's serial. bandersnatch then uses the JSON API
of PyPI to get shasums and release file paths to download and workout where
to layout the package files on a POSIX file system.

Contents:

.. toctree::
    :maxdepth: 3

    installation
    mirror_configuration
    filtering_configuration
    CONTRIBUTING
    CODE_OF_CONDUCT
    modules

Mirror from a mirror (Simple API)
=================================

Bandersnatch can mirror packages from another Python package index that
implements the Simple Repository API (PEP 503). This allows you to create
a secondary mirror from an existing mirror instead of directly from PyPI.

Configuration
-------------

Set the ``master`` option in your bandersnatch configuration to the base
URL of the upstream mirror.

Example::

    [mirror]
    master = https://example-mirror.org/simple/

Notes
-----

- The upstream mirror must implement the Simple Repository API (PEP 503).
- Ensure the URL ends with ``/simple/``.
- Some mirrors may have partial content or different filtering rules.
- Synchronization speed depends on the upstream mirror performance.

Use cases
---------

- Creating an internal mirror from an organizational mirror
- Reducing load on PyPI by chaining mirrors
- Regional or offline mirror setups

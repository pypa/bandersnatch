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
Troubleshooting
---------------

Bandersnatch 7.0+ uses the PEP 691 Simple API JSON format when available.

If the upstream mirror does not return JSON and instead serves HTML,
bandersnatch may fail with errors such as:

aiohttp.client_exceptions.ContentTypeError:
Attempt to decode JSON with unexpected mimetype: text/html

This happens when the upstream mirror does not correctly support the
Simple API JSON endpoint.

To verify JSON support, check:

- The `/simple/` endpoint responds with JSON when requested with:

  Accept: application/vnd.pypi.simple.v1+json

- The response `Content-Type` is:

  application/vnd.pypi.simple.v1+json

Currently, bandersnatch does not automatically fall back to the HTML
Simple API when JSON is unavailable. Ensure the upstream mirror is
configured correctly for JSON responses when chaining mirrors.

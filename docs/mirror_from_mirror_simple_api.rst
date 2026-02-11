Mirror from a mirror (Simple API)
=================================

Bandersnatch can mirror packages from another Python package index that
implements the Simple Repository API (PEP 503 + 691). This allows you
to create a secondary mirror from an existing mirror instead of directly
from PyPI.

Configuration
-------------

Set the ``master`` option in your bandersnatch configuration to the **base
URL** of the upstream mirror.

Example::

    [mirror]
    master = https://example-mirror.org

Bandersnatch automatically appends ``/simple`` to the configured
``master`` URL.

Requirements
------------

The upstream mirror must support:

- The Simple Repository API with **PEP 691 JSON responses**
  (``Accept: application/vnd.pypi.simple.v1+json``)
- The PyPI JSON metadata endpoint:
  ``/pypi/<project>/json``

Bandersnatch requires JSON responses for correct mirroring.

Notes
-----

- Some mirrors may have partial content or different filtering rules.
- Synchronization speed depends on the upstream mirror performance.
- If the upstream serves only HTML Simple API (PEP 503) and not JSON, mirroring will fail (no automatic fallback).


JSON vs HTML behavior
---------------------

Bandersnatch **only supports the JSON Simple API (PEP 691)**.

If the upstream mirror serves only HTML (PEP 503) and does not provide
JSON responses, bandersnatch will **fail fast** instead of falling back
to HTML parsing.

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

To verify JSON support, check:

- The ``/simple/`` endpoint responds with JSON when requested with:

  Accept: application/vnd.pypi.simple.v1+json

- The response ``Content-Type`` is:

  application/vnd.pypi.simple.v1+json

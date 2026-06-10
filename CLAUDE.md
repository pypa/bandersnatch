# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

bandersnatch is a PyPI mirror client implementing the client (mirror) side of PEP 381 + PEP 503 + PEP 691. It downloads PyPI package metadata and artifacts and lays them out on disk (or S3) so a webserver can serve a mirror. Uses the PEP 691 Simple JSON API by default (since 7.0). Requires Python >= 3.12.

## Commands

Tests, lint, and CI are driven through `tox` and the `test_runner.py` wrapper (the wrapper exists so CI works identically on Windows/Mac/Linux).

- Run the full unit test suite + coverage: `tox` (env `py3`). Equivalent to `coverage run -m pytest --strict-markers` then coverage report/html/xml.
- Run a single test file: `pytest src/bandersnatch/tests/test_mirror.py`
- Run a single test: `pytest src/bandersnatch/tests/test_mirror.py::test_name`
- Run S3-marked tests only: `pytest -m s3` (uses `moto` in-memory mock — no real bucket needed).
- CI entrypoint (selects tox vs integration test by `TOXENV`): `python test_runner.py`. With `TOXENV=INTEGRATION` it installs the package and hits real PyPI, pulling an allowlist and asserting expected files exist.
- Build docs: `tox -e doc_build` (sphinx; warnings are errors via `-W`).
- Lint/format is via pre-commit (`pre-commit run --all-files`): black (`--preview`, py312 target), isort (black profile), flake8 + bugbear, mypy, pyupgrade (py312-plus), mdformat. Run before committing — CI does not autofix.

`testpaths = src` and tests live next to the code in `tests/` subdirs. `pytest.ini` sets `asyncio_mode=strict`, so async tests need explicit `@pytest.mark.asyncio`.

## Architecture

The codebase is async (`aiohttp`) throughout. Entry point is `bandersnatch.main:main`, which dispatches on subcommands (each has a `_<cmd>_parser` setting `op=`): **mirror**, **sync** (mirror specific packages), **delete**, **verify**.

Core sync flow (`src/bandersnatch/`):
- `master.py` — `Master`: HTTP client talking to the upstream PyPI server (the "master"). Raises `StalePage` for serial/consistency issues.
- `mirror.py` — `Mirror` (base) and `BandersnatchMirror` (concrete): orchestrates the whole sync — fetches the changelog/list of packages to update, drives per-package work concurrently, writes the simple index, tracks serial/state.
- `package.py` — `Package`: represents one PyPI project; fetches its metadata and decides which release files to download.
- `simple.py` — generation of PEP 503 HTML and PEP 691 JSON simple-index formats (`SimpleFormat`/`SimpleFormats`).
- `configuration.py` + `config/` — config loading/validation. `config/` holds `exceptions.py` (`ConfigError`, `ConfigFileNotFound`), `proxy.py`, `diff_file_reference.py`. Defaults ship in `defaults.conf`; `example.conf` is the documented template.
- `delete.py`, `verify.py` — implement the `delete` and `verify` subcommands.
- `utils.py`, `log.py`, `errors.py` — shared helpers.

### Plugin system (two extension points, both via setuptools entry points)

Plugins are registered as entry points in `setup.cfg` — when adding a plugin, you must add the entry point there, not just the class.

- **Storage backends** — `bandersnatch_storage_plugins/` (group `bandersnatch_storage_plugins.v1.backend`). `filesystem.py` (default) and `s3.py`. Base/Protocol in `bandersnatch/storage.py`. This is what abstracts disk vs S3 so the rest of the code never touches the filesystem directly.
- **Filters** — `bandersnatch_filter_plugins/` (groups `bandersnatch_filter_plugins.v2.{project,metadata,release,release_file}`). Decide which projects/releases/files to include or skip (allowlist/blocklist/regex/prerelease/latest/platform/size/version-range). Base classes in `bandersnatch/filter.py`.

Both `filter.py` and `storage.py` carry an `API_REVISION` constant — bump it when changing the plugin base classes in a backwards-incompatible way so stale installed plugins are rejected rather than breaking at runtime.

### Other `src/` subprojects (not part of the importable `bandersnatch` package)

- `runner.py` — periodic `bandersnatch mirror` loop used in the Docker image.
- `banderx/` — example nginx webserver config/Docker container for serving the mirror (PEP 691 content negotiation).
- `bandersnatch_docker_compose/` — docker-compose example deployment.

## Releasing

A release is a PR followed by a GitHub Release. Steps:

1. **In a new branch/PR**, finalize `CHANGES.md`: rename the top `# Unreleased` heading to the new version number (e.g. `# 7.2.0`), keeping its `## New Features` / `## CI / test` / `## Documentation` / `## Bug Fixes` subsections. Add a fresh empty `# Unreleased` section above it for future work.
2. Bump `version =` in `setup.cfg` to the version the user asks for. It **must be valid semver and strictly greater** than the current value — verify against `git tag` (tags are the released versions) and refuse/flag if the requested version is not higher.
3. Push the PR and wait for it to land on `main` (CI must pass; `main` is normally PR-gated).
4. Once merged, cut a new GitHub Release tagged with that version (`gh release create <version>`), and paste the just-released version's `CHANGES.md` markdown (the section you renamed in step 1) as the release body.

## Conventions

- Version lives in `setup.cfg` (`version =`). User-facing changes get a `CHANGES.md` entry.
- Min supported Python is 3.12; CI matrix runs 3.12–3.15. New syntax for >=3.12 is acceptable.
- Optional features are extras: `s3` (s3path), `uvloop`, `safety_db`. uvloop is auto-installed/used when present (`main.py` tries to import it).

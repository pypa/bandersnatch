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

1. Bump the version in **both** places — they must match, and it's easy to update one and forget the other:

   - `version =` in `setup.cfg`
   - `__version_info__` in `src/bandersnatch/__init__.py` (set `major`/`minor`/`micro` accordingly and clear `releaselevel` to `""` for a final release)

   The version **must be valid semver and strictly greater** than the current value — verify against `git tag` (tags are the released versions) and refuse/flag if the requested version is not higher.

1. Push the PR and wait for it to land on `main` (CI must pass; `main` is normally PR-gated). The `Changelog Entry Check` workflow greps `CHANGES.md` for a `PR #<this PR's number>` line and fails on a release PR since the PR doesn't reference itself — add the `skip news` label to the PR to satisfy it.

1. Once merged, cut a new GitHub Release tagged with that version (`gh release create <version>`), and paste the just-released version's `CHANGES.md` markdown (the section you renamed in step 1) as the release body.

1. **Publishing a release triggers two more workflows** (`on: release: types: created`) that must be watched to completion, since a failure here means the release is tagged but not actually shipped: `pypi_upload.yml` (builds sdist/wheel, `twine upload`s to PyPI) and `docker_upload.yml` (builds+pushes `pypa/bandersnatch` images to DockerHub for `linux/amd64,linux/arm64`, both the plain and `s3-` tag variants). Find the runs with `gh run list --workflow=pypi_upload.yml --limit 3` / `--workflow=docker_upload.yml --limit 3` (match on the release tag as `headBranch` and `event == "release"`), watch with `gh run watch <id> --exit-status`, and after both succeed confirm the version actually landed by checking `https://pypi.org/pypi/bandersnatch/json` (`.info.version`). `docker_upload.yml` also runs on every push to `main`, independent of releases — that's expected, not a duplicate to worry about.

## Dependency updates (Dependabot)

Dependabot opens a batch of pip PRs roughly weekly, each a one-line pin bump in one of the
pinned requirements files: `requirements.txt` (runtime), `requirements_test.txt` (test/lint
tooling), `requirements_s3.txt` (the `s3` extra), `requirements_docs.txt` (sphinx docs).

What governs merging them:

- **`main` branch protection**: 1 approving review required, and **strict** required status
  checks — the branch must be up to date with `main` — on exactly three contexts:
  `bandersnatch CI python 3.14 on {ubuntu,macOS,windows}-latest`. `enforce_admins` is **off**,
  so a maintainer can merge without a separate review via `gh pr merge <n> --squash --admin`.
- **Squash is the only allowed merge method** (merge commits and rebase-merges are disabled);
  `delete_branch_on_merge` is on, so branches clean themselves up.
- Because required checks are strict, **merging one PR makes every other open PR `BEHIND`** and
  unmergeable until refreshed. So merge them **one at a time**: merge, then
  `gh pr update-branch <next> --rebase` (or comment `@dependabot rebase`), wait for **all** of
  that PR's checks to go green (see the policy below — not just the required three), then merge
  the next.
- Dependabot PRs carry the **`skip news`** label, which is what lets the `Changelog Entry Check`
  workflow pass without a `CHANGES.md` entry. Dependency bumps do not get changelog entries.
- Triage the batch with:
  `gh pr list --author "app/dependabot" --json number,title,mergeable,mergeStateStatus`
  then `gh pr checks <n>` per PR.

**Policy — when Claude may approve/merge without asking.** Only for **Dependabot-authored PRs**
(`app/dependabot`) where **EVERY check is passing** — not merely the required ones. Both
conditions must hold. Anything else — a human-authored PR, or a Dependabot PR with even one
failing *or still-pending* check — gets reported back for a human decision instead of merged. A
red check is a signal to investigate the bump, not to retry the merge.

**Do not gate on branch protection's required contexts.** Only three contexts are *required*
(`bandersnatch CI python 3.14 on {ubuntu,macOS,windows}-latest`), but a PR routinely carries ~17
checks: the 3.12/3.13/3.15 matrix, `html + linkcheck build`, `pre-commit.ci`,
`Changelog Entry Check`, and both codecov statuses. Waiting only on the required three merges PRs
while the rest are still running or already red. Gate on the whole set, e.g.:

```bash
s=$(gh pr checks <n> --json name,bucket)
jq -e '[.[] | select(.bucket != "pass")] | length == 0' <<<"$s" >/dev/null \
  && gh pr merge <n> --squash --admin \
  || jq -r '.[] | select(.bucket != "pass") | "  \(.bucket)\t\(.name)"' <<<"$s"
```

**Known flake: `codecov/project` reports a transient `-0.10%` that later self-heals.** CI uploads
coverage from *every* matrix job (`ci.yml`, 4 Pythons x 3 OSes = 12 uploads), and codecov computes
the `project` status from whatever has arrived so far. When it fires after only ~10 of the 12
uploads have landed it reports e.g. `91.96% (-0.10%)` and goes red; once the stragglers arrive the
commit reconciles to the true value and the check flips green on its own. Verified via the codecov
API — a red PR head and its green base had **identical** totals (`92.06%`, 5028 lines / 4629 hits
/ 256 misses), differing only in session count (10 vs 12).

So a red `codecov/project` on a pin bump is almost never a real regression — but **do not merge
through it**. Re-check a few minutes later and it will normally be green; merge then. Confirm with:

```bash
curl -s "https://api.codecov.io/api/v2/github/pypa/repos/bandersnatch/commits/<sha>" \
  | jq '{coverage: .report.totals.coverage, sessions: (.report.sessions | length)}'
```

Fewer sessions than the matrix size means uploads are still landing, not that coverage dropped. The
durable fix is a `codecov.yml` setting `after_n_builds` to the full matrix count so codecov waits
for every upload before reporting (a project `threshold` would only mask it).

**Claude needs local permission for this.** Approving and merging are blocked by Claude Code's
auto-mode classifier unless these rules exist in a settings file — user-level
`~/.claude/settings.local.json` works and applies to every repo:

```json
"Bash(gh pr review:*)",
"Bash(gh pr merge:*)",
"Bash(gh pr update-branch:*)"
```

Claude cannot add these itself — writing to its own permissions file is blocked by design, via
both Bash and the edit tools. The user adds them by editing the file, or by choosing "Yes, and
don't ask again" on the permission prompt (which requires leaving auto mode with `shift+tab`).
Never put them in a committed `.claude/settings.json` — this is a public repo.

### Known upstream-blocked bumps

- **#2258 `docutils` 0.22.4 → 0.23** — fails `html + linkcheck build` with
  `ResolutionImpossible`: `sphinx==9.1.0` (currently the latest sphinx) requires
  `docutils<0.23,>=0.21`. Nothing to fix on our side; leave it open until Sphinx relaxes the
  cap. Re-check with
  `curl -s https://pypi.org/pypi/sphinx/json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['info']['version'], [r for r in d['info']['requires_dist'] if 'docutils' in r])"`.

## Conventions

- Version lives in **two** places that must be kept in sync: `setup.cfg` (`version =`) and `src/bandersnatch/__init__.py` (`__version_info__`). User-facing changes get a `CHANGES.md` entry.
- Min supported Python is 3.12; CI matrix runs 3.12–3.15. New syntax for >=3.12 is acceptable.
- Optional features are extras: `s3` (s3path), `uvloop`, `safety_db`. uvloop is auto-installed/used when present (`main.py` tries to import it).

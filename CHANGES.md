# Unreleased

## New Features

- Added HTTPS support in Docker Compose + Enabled bind-mount volume for Nginx config + add documentation in README.md (PR #1653)

## Documentation

- Updated documentation for `[mirror]` configuration options `PR #1669`

# 6.5.0

## New Features

- Add option to filter releases based on upload time `PR #1594`
- `project_requirements_pinned` with a pinned version (range) disables additional release filter for this package `PR #1601`
- Add command configuration for bandersnatch in Docker Compose, including 'mirror' default, 'verify' and 'once' options, improve documentation for docker compose, and added "Removing the Repository" section in Docker Compose README with a link in the main README. `PR #1645`

# 6.4.0

- Move JSON Simple API to version 1.1 (as per PEP700) `PR #1557`
- Move to >= 3.10 project `PR #1457`

## Bug Fixes

- Support `py2` + `py3` bdist file name filtering `PR #1495`

# 6.3.0

## Bug Fixes

- Fix digest used for file hashes in PEP 691 simple JSON file output `PR #1442`
  - The `digest_name` setting from configuration (default value: `sha256`) will now be used for both HTML and JSON files.
  - This mirrors pypi.org ("Warehouse") behavior
  - Please use `bandersnatch mirror --force-check` to regenerate all your mirror's simple API
    - `bandersnatch sync` could also be a way to update important packages faster too

# 6.2.0

## New Features

- Add scandir() as Storage plugin API to speedup large directory read when generating global index `PR #1340`
- Declare support for Python 3.11 `PR #1338`
- Move Docker to build in 3.11 `PR #1341`
- Add "--force-check" parameter to runner.py `PR #1347`

## Bug Fixes

- Fixed read of requirement files with non UTF-8 encoding - compatible with pip `PR #1387`
- Type checking fixed to pass mypy > 1.0.0
- Don't attempt docker on forks `PR #1336`

## Notice

- This will be the last python 3.8 and 3.9 tested version. Going to plan to be >= 3.10

# 6.1.0

## New Features

- Add a `packages` config under `[filter_prerelease]` for prerelease filter to filter only specified packages. `PR #1328`

## Dropped Support

- Dropped LegacyVersion support for latest_name plugin `PR #1315`
- No longer issue PURGE requests on StalePage exceptions as PyPI now requires authentication `PR #1335`

## CI

- Format with black `--preview` style `PR #1313`
  - I contribute to black and want to help find bugs ...

# 6.0.1

## Bug Fixes

- Fixed JSON only mirroring adding correct path to diff_file_list `PR #1248`
- Fixed requirements file parsing when it contains pip options `PR #1231`

## New Features

- Added the possibility to limit the time range in which the docker image runner can execute the bandersnatch mirroring activity.
  This can be done by providing an optional command line argument with like `--hours-range 23-7` where the interval is expressed
  as `<start_hour>-<end_hour>`. `PR #1232`
- Add support for globbing in the allowed requirements list.
  User can specify `requirements*.txt` or `*.txt` to merge multiple requirements files `PR #1230`

# 6.0.0

## New Features

- Add [PEP691](https://peps.python.org/pep-0691/) simple index support `PR #1154`
- Add example nginx serving for PEP 691 `PR #1161`

# 5.3.0 (2022-07-29)

## New Features

- Add delete and verify support in s3 (and maybe swift) storage backend `PR #1142`
- Add `--skip-simple-root` option for `bandersnatch sync` command `PR #1145`

## Other

- Replace pyup with dependabot
  - Resulted in lots of depdendencies updating
- Docs typo fixes

# 5.2.0 (2022-05-02)

## New Features

- Add PEP 629 header to Simple API HTML `PR #1122`
- Added support to exclude specific Python minor versions `PR #1110` - Thanks **davidkim83**
- Add S3 Docker Image building `PR #1092`

## Other

- Got Swift usage documentation
- Move Docker containers to Python 3.10 `PR #1092`
- Python 3.10 is now supported `PR #1073` - Thanks **isidentical**
- Move minio docker image running to official image

# 5.1.1 (2021-12-14)

## Bug fixes

- Fix debug output for package changes at end of mirror operation `PR #1066` - Thanks **forky2**

## Other

- Update lots of dependency version pins
- Fix documentation build CI

# 5.1.0 (2021-11-02)

## New Features

- Add support of downloading packages from alternative mirror `PR #928` -- Thanks **happyaron**
- Add support of s3 storage `PR #886` -- Thanks **LeoQuote**

## Bug fixes

- Add bandersnatch command line help to the documentation main page `PR #920` - Thanks **ichard26**
- Generate data-yanked tag in simple page `PR #931` - Thanks **happyaron**
- Protect repository metadata from being trashed when disk is full `PR #962` - Thanks **happyaron**
- Fix tox to used pinned requirements\*.txt files for deps - `PR #1011` - Thanks **cooperlees**

## Documentation

- Add Storage Options documentation `PR #1006` - Thanks **cooperlees**
- Update all dependencies to latest except pyparsing + docutils

## Dependencies

- Change pyup to run monthly + auto add skip_news `PR #1043` - Thanks **cooperlees**

# 5.0.0 (2021-4-28)

## New Features

- bandersnatch is now a >= 3.8 Python project
- New size_project_metadata filter plugin, which can deny download of projects larger than defined threshold - `PR #806`
- Add option to compare file size and upload time instead of sha256sum for downloading - `PR #822`
- Add optional uvloop support - `PR #891` - Thanks **cooperlees**
- Move to official docker upload action w/arm64 images uploaded - `PR #896` - Thanks **cooperlees**

## Deprecations

- blacklist/whitelist will no longer work in bandersnatch configuration - `PR #897` - Thanks **cooperlees**
  - Please use allowlist/denylist respectively

## Bug Fixes

- Unused storage plugins are loaded and cause non-fatal errors if dependencies are missing - `PR #799` - Thanks **electricworry**
- Replaced usages of `asynctest` with `unittest.mock` in tests - `PR #807` and `PR #856` - Thanks **ichard26**
- Remove debugging line that loads entire files into memory. - `PR #858` - Thanks **asrp**
- Removed terrible isinstance check of unittest.Mock in mirror.py - `PR #859` - Thanks **ichard26**
- Put potential time consuming IO operations into executor - `PR #877`
- Migrated Markdown documentation from recommonmark to MyST-Parser + docs config clean up - `PR #879` - Thanks **ichard26**
- Use `shutil.move()` for temp file management - `PR #883` - Thanks **happyaron**
- Fixed logging bug in `SizeProjectMetadataFilter` to show it activated - `PR #889` - Thanks **cooperlees**
- Attempt to wrap all potentially block calls in a ThreadPoolExecutor - `PR #894` - Thanks **cooperlees**

# 4.4.0 (2020-12-31)

## New Features

- Build a swift and non swift docker image - `PR #754`
- Split Docker Build to accept build args to optionally include swift support - `PR #741` - Thanks **nlaurance-pyie**
- Slimmer docker image - `PR #738` - Thanks **nlaurance-pyie**
- Renamed black/white to block/allow lists - `PR #737` - Thanks **nlaurance-pyie**
- packages allowlist can be defined from requirements like files - `PR #739` - Thanks **nlaurance-pyie**
- Simplify logging around filters - `PR #678` - Thanks **@dalley**

## Bug Fixes

- Handling of timeouts that can occur in verify. - `PR #785` - Thanks **electricworry**
- Added retry logic on timeouts when fetching metadata - `PR #773` - Thanks **gerrod3**
- Fix links, improve docs CI, and improve external object linking - `PR #776` - Thanks **ichard26**
- Handle 404 status for json verify - `PR #763` - Thanks **electricworry**
- Clean up isort config after upgrade to 5+ - `PR #767` - Thanks **ichard26**
- Remove duplicate max() target serial finding code + update typing - `PR #745`
- swift.py: use BaseFileLock's lock_file property - `PR #699` - Thanks **hauntsaninja**
- Move to latest isort + mypy fixes - `PR #706`
- Update change log url in project metadata - `PR #673` - Thanks **@abn**

# 4.3.0 (2020-8-25)

## New Features

- Add SOCKS proxy support to aiohttp via aiohttp-socks - `PR #668`
- Add support for skipping mirroring release files (metadata only) - `PR #670` - Thanks **@abn**

## Bug Fixes

- Move GitHub actions to v2 tags - `PR #666` - Thanks **@ryuichi1208**

# 4.2.0 (2020-8-20)

## New Features

Thanks to RedHat engineers **@dalley** + **@gerrod3** for all this refactor work in PR #591

- New generic Mirror class to perform Python metadata syncing
  - *(previous Mirror class has been renamed to BandersnatchMirror)*
- Package's filter methods are now part of its public API
- New `errors.py` file to house Bandersnatch specific errors

## Internal API Changes

- Old Mirror class has been renamed to BandersnatchMirror.  Performs same functionality with use of new Mirror API.
- BandersnatchMirror now performs all filesystem operations throughout the sync process including the ones previously
  in Package.
- Package no longer performs filesystem operations.  Properties `json_file`, `json_pypi_symlink`, `simple_directory`
  and methods `save_json_metadata`, `sync_release_files`, `gen_data_requires_python`, `generate_simple_page`,
  `sync_simple_page`, `_save_simple_page_version`, `_prepare_versions_path`, `_file_url_to_local_url`,
  `_file_url_to_local_path`, `download_file` have all been moved into BandersnatchMirror. Package's `sync` has been
  refactored into Bandersnatch's `process_package`.
- Package class is no longer created with an instance of Mirror
- StaleMetadata exception has been moved to new errors.py file
- PackageNotFound exception has been moved to new errors.py file

## Bug Fixes

- Fixed Fix latest_release plugin to ensure latest version is included - `PR #660` - Thanks **@serverwentdown**

## 4.1.1 (2020-8-12)

### Bug Fixes

- Fixed name parsing issue for allow/blocklist project filters - `PR #651` - Thanks **@gerrod3**

# 4.1.0 (2020-8-9)

*Storage abstraction refactor + Type Annotating!*

## New Features

- bandersnatch is now 100% type annotated - `PRs #546 #561 #592 #593` - Thanks **@ichard26** + **@rkm**
- Move to storage abstraction - `PR #445` - Thanks **@techalchemy**
  - Can now support more than just filesystem e.g. swift
- Add `sync` subcommand to force a sync on a particular PyPI package - `PR #572` - Thanks **@z4yx**
- Added new allowlist filter - `PR #626` - Thanks **@gerrod3**
- Make webdir/pypi/json/PKG symlinks relative - `PR #637` - Thanks **@indrat**
  - Makes mirror files more portable
- Add __main__ and program name override to ArgumentParser - `PR #643` - Thanks **@rkm**
  - Allow non pkg_resources install to work

## Internal API Changes

- Refactored the removal of releases for release_plugins to happen inside of Package `PR #608` - Thanks **@gerrod3**
- Minor refactor of Package class `PR #606` - Thanks **@dralley**
- Refactored filter loading into separate class `PR #599` - Thanks **@gerrod3**
- Move legacy directory cleanup to mirror.py `PR #586`
- Move verify to use Master for HTTP calls - `PR #555`
- Move http request code for package metadata to master.py - `PRs #550` - Thanks **@dralley**

## Bug Fixes

- Fixed allow/blocklist release filtering pre-releases - `PR #641` - Thanks **@gerrod3**
- Casefold *(normalize per PEP503)* package names in blacklist/whitelist plugins config - `PR #629` - Thanks **@lepaperwan**
- Fix passing package info to filters in verify action. `PR #638` - Thanks **@indrat**
- Fix todo file removal - `PR #571`
- Introduce a new `global-timeout` config option for aiohttp coroutines - Default 5 hours - `PR #540` - Thanks **@techalchemy**
- Many doc fixes - `PRs #542 #551 #557 #605 #628 #630` - Thanks **@pgrimaud** + **@ichard26** + **@hugovk**
- Move to setting timeout only on session + 10 * total_timeout (over sock timeouts) - `PR #535`
- Stop using `include_package_data` option in setup.cfg to get config files included in more installs - `PR #519`

## 4.0.3 (2020-5-7)

- Change aiohttp-xmlrpc to use Master.session to ensure config shared - `PR #506` - Thanks **@alebourdoulous** for reporting
  - e.g. Maintin trust of proxy server environment variables

## 4.0.2 (2020-4-26)

- Raise for error HTML response on all aiohttp session requests - `PR #494 / #496` - Thanks **@windtail**
- Pass str to shutil.move due to Python bug - `PR #497` - Thanks **@SanketDG**
- Some more type hints added to `verify.py` - `PR #488` - Thanks **@SanketDG**
- Ignore `atime` on stat in test `test_package_sync_does_not_touch_existing_local_file` comparison
  as it causes stat compare fail on a slower run - `PR #487` - Thanks **@SanketDG**

## 4.0.1 (2020-4-5)

- Pass correct aiohttp timeout objects - `PR #478`
- Replace pkg_resources with importlib.resources - `PR #479` - Thanks **@SanketDG**

# 4.0.0 (2020-3-29)

*asyncio aiohttp refactor*

- Replace requests with aiohttp - `PR #440`
  - Replace xmlrpc2 with aiohttp-xmlrpc - `PR #404`
- Only store PEP503 Normalized Simple API directories - `PR #465 + #455`
- Flag errors when KeyboardInterrupt raised during sync - `PR #421`
- Finish Windows Support + Add CI - `PRs #469 + #471` - Thanks **@FaustinCarter**
- Autobuild Docker images with master - `PR #88` - Thanks **@abitrolly**
- Only print conf deprecations if found in config - `PR #327`
- Add PyPI metadata and Python version plugin filters - `PR #391` - Thanks **@TemptorSent**
- Add in *GitHub Actions CI* for Linux (Ubuntu), MacOSX + Windows

# 3.6.0 (2019-09-24)

- Add `delete` subcommand to delete specific PyPI Packages from mirror - `PR #324`

# 3.5.0 (2019-09-14)

- Add support for differential file generation - Thanks **@artagel** - `PR #313`

## 3.4.1 (2019-06-18)

- Match prerelease versions with multiple digit suffixes - Thanks **@indrat**

# 3.4.0 (2019-05-30)

- Fix keep_index_versions by removing symlinks for non normalized_legacy_simple_directory
  index.htmnl - `Fixes #262` - Thanks **@ipbeegle**
- Version plugin api + allow external plugins + move to setup.cfg - `Fixes ` - Thanks **@dwighthubbard**
- Add in support for `[plugins]` config section with deprecation warning till 4.0
- Add a Maintainers guide + Mission Statement to README.md
- Lots of doc fixes - `Fixes #217-#222` - Thanks **@vinayak-mehta**
- Add last_serial in index.html - `Fixes #141` - Thanks **@rene-d**
- Rewrite of FilterReleasePlugin filter function - `Fixes #196` - Thanks **@rene-d**

## 3.3.1 (2019-04-14)

- Make plugins logs less noisy and more stateful (don't initialize multiple times) - `Fixes #134 #147 #193 #195`
- Latest releases plugin always keeps current version - `Fixes #196` - Thanks **@rene-d**

# 3.3.0 (2019-04-11)

- Add latest version and specific platform plugins - `Fixes #49` - Thanks **@rene-d**
- Generate data-requires-python attributes in index.html  - `Fixes #68` - Thanks **@z4yx**
- Make package filtering logging less noisy when disabled - `Fixes #146`
- Many pyup.io dependency upgrades

# 3.2.0 (2019-01-25)

- Change plugins to be off unless explicitly enabled via configuration - `Fixes #142`
- Change all path interactions to use **Pathlib** for more Windows support - `Addresses #23`
- Add a MacOS CI Run with azure pipelines
- Move test_runner from shell to Python for Windows - `Addresses #23`
- More testing improvements and refactor for verify.py
- We now have a reference Docker file + runner.py - `Fixes #113`
- Many pyup.io dependency upgrades

### Known Bug

- From 3.0.0 we've been implicitly turning on *ALL* plugins - This version reverses that

## 3.1.3 (2018-12-26)

- Print help message when no arguments given to bandersnatch - Thanks **@GreatBahram**
- aiohttp >= 3.5.0 test and we no longer have `.netrc` error message

## 3.1.2 (2018-12-02)

- Load default config or passed in config file only *(not both)* - `Fixes #95` - Thanks **@GreatBahram**
- Add `--force-check` to mirror to enable full PyPI Syncs - `Fixes #97` - Thanks **@GreatBahram**

## 3.1.1 (2018-11-25)

- Add missing `filelock` dependency to `setup.py` `Fixes #93`

## 3.1.0 (2018-11-25)

- Store N versions of index.html - `Fixes #9` - Thanks **@yeraydiazdiaz**
- Add CI Integration test - `Fixes #78` - Thanks **@cooperlees**
- Test / pin to latest dependencies via PyUP - `Fixes #70` - Thanks **@cooperlees**
- Revert pinning versions in `setup.py` - `Fixes #81`
- Add Pre-release + regex filter plguins `Fixes #83` - Thanks **@yeraydiazdiaz**

## 3.0.1 (2018-10-30)

- Fix setup.py *url* to point at GitHub (https://github.com/pypa/bandersnatch)

# 3.0.0 (2018-10-30)

- Move to asyncio executors around request calls `Fixes #81` *(on BitBucket)*
- Use platform.uname() to support Windows `Fixes #19`
- Add **bandersnatch verify** subcommand to re-download + delete unneeded packages `Fixes #8` + many follow on Issues during testing - Thanks **electricworry** & **tau3** for testing + fixes!
- Introduce much more Lint checks (black, isort, mypy) other than flake8 - Thanks **@asottile**
- Make tox run lint checks + print out test coverage - Thanks **@cooperlees**
- Add whitelist + blacklist plugins - Thanks **@dwighthubbard**
- Add generated documentation - Thanks **@dwighthubbard**
- Move to requiring Python >= 3.6.1 `Fixes #66`

**Moved to GitHub @ PyCon US 2018 - All `Fixes` now refer to GitHub issues**

## 2.2.1 (2018-05-01)

- Fix missed MANIFEST.in change for this file :P `Fixes #108` - Thanks **@cooperlees**

## 2.2.0 (2018-03-28)

- Allow digest_name to be specified. `Fixes #105` - Thanks **@ewdurbin** !
- synchronize generated index pages with warehouse - Thanks **@ewdurbin** !
- Allow root_uri to be configured - Thanks **@ewdurbin** !
  - This is how warehouse (pypi.org) will function

## 2.1.3 (2018-03-04)

- Change version from using pkg_resources and set it in package __init__.py.
  `Fixes #98`.
- Add ability to blacklist packages to sync via conf file. `Fixes #100`.

## 2.1.2

- Add saving of JSON metadata grabbed from pypi.facebook.com for syncing `Fixes #91` - Thanks **@cooperlees**
  - Can be disabled via config and disabled by default
  - bandersnatch symlinks WEB_ROOT/pypi/PKG_NAME/json to WEB_ROOT/json/PKG_NAME

## 2.1.0

- Fix proxy usage. A bug in the usage of requests on our XMLRPC client
  caused this to break. You can now set `*_proxy` environment variables
  and get them picked up properly. `Fixes #59`.
- Add a dict returned from mirror.synchronize() to show deleted
  and added files from the last run
- Fix sorting of releases to use filename and not url
- Tweak atomic file writes in utils.rewrite() to prefix the temporary
  file with the 'hidden' filename of the destination adding more
  support for hashed POSIX filesystems like GlusterFS. - Thanks **@cooperlees**

# 2.0.0 (2017-04-05)

- Move to Python 3. - Thanks **@cooperlees** !

  Official support starts with Python 3.5 but might get away with using an
  earlier version of Python 3 (maybe 3.3 or so). However, we plan to start
  using Python 3.5 features (like *asyncio*) in the near future, so please
  be advised that running with an older version of Python 3 is not
  a supported option for the long term.

- General update of our dependencies to pave the road for Python 3 support.

- Remove residual references to the old "statistics" script that isn't in
  use any longer.

- Fix return code -- we accidentally returned 1 on successful runs
  as debugging code was mixed in the main call. `Fixes #67`.

- Make the package-specific simple pages human-readable again. `Fixes #71`.

## 1.11 (2016-05-18)

- Add option to dir-hash index files. See
  https://bitbucket.org/pypa/bandersnatch/pull-requests/22/add-option-to-dir-hash-index-files for a lot more information. Thanks
  @iwienand!

- Fix an edge case: IO errors while marking off packages as "done"
  could result in crashing workers that would result in bandersnatch
  getting stuck. Thanks **@wjjt**!

## 1.10.0.1 (2016-05-11)

- Brownbag release for re-upload. My train's Wifi broke while uploading
  ending up with a partial file on PyPI. Can your train service do better
  than mine?

## 1.10 (2016-05-11)

This is release is massively supported by **@dstufft** getting bandersnatch
back in sync with current packaging ecosystem changes. All clap your hands
now, please.

- Refactor the generation update code to avoid weird update paths
  due to, well, my personal kink: 'over complication'.

- Generate the simple index ourselves instead of copying it from PyPI.

- Support files hosted on a separate domain.

- Implement PEP 503 normalization rules while also providing support
  for legacy and very legacy clients.

## 1.9 (2016-04-21)

- Fix a long standing, misunderstood bug: a non-deleting mirror would
  delete packages if they were fully removed from PyPI. `Fixes #61`

## 1.8 (2015-03-16)

- Don't require a X-PyPI-Last-Serial header on file downloads.
  (Thanks to **@dstufft**.)

- Increase our generation to help mirrors recover potential
  setuptools corruption after some data bug on PyPI.

## 1.7 (2014-12-14)

- Fixes #54 by reordering the simple index page and file fetching
  parts. Thanks **@dstufft** for the inspiration.

- Stop syncing serversig files and even start removing them.

## 1.6.1 (2014-09-24)

- Create a new generation to enforce a full sync when upgrading.
  This is required to get the canonical names for all packages.

## 1.6 (2014-09-24)

- Implement canonical package directory names to support an upcoming PIP
  release and other tools. (Thanks to **@dstufft**)

- Fix a race condition where workers could get stuck indefinitely waiting for
  another item in a depleted queue. (Thanks to **@hongqn**)

## 1.5 (2014-07-21)

- Delete broken tests that I forgot to remove.

- Reduce the officially sanctioned maximum number of connections.

## 1.4 (2014-04-15)

- Move towards replacing the XMLRPC API with JSON to make our requests
  cacheable. Also reduces the amount of requests needed dramatically.

- Remove apache stats script as this information is no longer being used anyway.

## 1.3 (2014-02-16)

- Move to xmlrpc2 to get SSL verification on XML-RPC calls, too. (`Fixes #40` and
  big thanks to **@ewdurbin**)

## 1.2 (2014-01-08)

- Potential performance improvement: use requests' session object to allow HTTP
  pipelining. Thanks to Wouter Bolsterlee for the recommendation in `Fixes #39`.

## 1.1 (2013-11-26)

- Made code Python 2.6 compatible. Thanks to **@ewdurbin** for the pull request.

## 1.0.5 (2013-07-25)

- Refactor lock acquisition to avoid shadowing exceptions when creating the
  lockfile vs. acquiring the lock.

- Move from distribute back to setuptools.

## 1.0.4 (2013-07-10)

- Slight brownbag release: the requirements.txt accidentally included a
  development version of py.test due to my usage of mr.developer.

## 1.0.3 (2013-07-08)

- Fix brownbag release with broken 'stable' tag and missing requirements.txt
  update.

## 1.0.2 (2013-07-08)

- Generate the index simple page ourselves: its not signed anyway and helps
  PyPI caching more aggressively.

- Add a py.test plugin to actually show a green bar. Hopefully will be
  integrated into py.test in the near future.

- Fix dealing with inconsistent todo files: empty files or with an incorrect
  header will just be deleted and processing resumes at the last known good
  state.

- Mark up requirement of Python 2.7 `Fixes #19`

- Fix dealing with new CDN cache issues. Thanks to **@dstufft** for making PyPI
  support mirrors again.

- Improve test coverage.

## 1.0.1 (2013-04-18)

- Fix packaging: include default config file. (Thanks to **Jannis Leidel**)

# 1.0 (2013-04-09)

- Update pip install documentation to use the a URL for referring to the
  requirements.txt directly.

- Adjust buildout and jenkins job to stop fighting over the distribute version
  to install.

## 1.0rc6 (2013-04-09)

- Hopefully fixed updating the stable tag when releasing.

## 1.0rc5 (2013-04-09)

- Experiment with zest.releaser integration to automatically generate
  requirements.txt during release process.

## 1.0rc4 (2013-04-09)

- Experiment with zest.releaser integration to automatically generate
  requirements.txt during release process.

## 1.0rc3 (2013-04-09)

- Experiment with zest.releaser integration to automatically generate
  requirements.txt during release process.

## 1.0rc2 (2013-04-09)

- Experiment with zest.releaser integration to automatically generate
  requirements.txt during release process.

## 1.0rc1 (2013-04-09)

- Initial release. Massive rewrite of pep381client.

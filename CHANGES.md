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

- Make plugins logs less noisy and more stateful (don't initalize multiple times) - `Fixes #134 #147 #193 #195`
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
-- This is how warehouse (pypi.org) will function


## 2.1.3 (2018-03-04)

- Change version from using pkg_resources and set it in package __init__.py.
  `Fixes #98`.
- Add ability to blacklist packages to sync via conf file. `Fixes #100`.


## 2.1.2

- Add saving of JSON metadata grabbed from pypi.facebook.com for syncing `Fixes #91` - Thanks **@cooperlees**
-- Can be disabled via config and disabled by default
-- bandersnatch symlinks WEB_ROOT/pypi/PKG_NAME/json to WEB_ROOT/json/PKG_NAME


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


1.10 (2016-05-11)
-----------------

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
-------------------

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

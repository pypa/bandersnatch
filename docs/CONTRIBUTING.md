# Contributing

So you want to help out? **Awesome**. Go you!

## Code of Conduct

Everyone interacting in the bandersnatch project's codebases, issue trackers,
chat rooms, and mailing lists is expected to follow the
[PSF Code of Conduct](https://github.com/pypa/.github/blob/main/CODE_OF_CONDUCT.md).

## Getting Started

Bandersnatch is developed using the [GitHub Flow](https://docs.github.com/en/get-started/quickstart/github-flow)

### Pre Install

Please make sure you system has the following:

- Python 3.8.0 or greater
- git client
- docker
  - *Optional* but needed to run S3 Tests

### Checkout `bandersnatch`

Lets now cd to where we want the code and clone the repo:

- `cd somewhere`
- `git clone git@github.com:pypa/bandersnatch.git`

### Development venv

One way to develop and install all the dependencies of bandersnatch is to use a venv.

- First create one and upgrade `pip`

```console
python3 -m venv /path/to/venv
/path/to/venv/bin/pip install --upgrade pip
```

For example:

```console
$ python3 -m venv bandersnatchvenv
$ bandersnatchvenv/bin/pip install --upgrade pip
Collecting pip
  Using cached https://files.pythonhosted.org/packages/0f/74/ecd13431bcc456ed390b44c8a6e917c1820365cbebcb6a8974d1cd045ab4/pip-10.0.1-py2.py3-none-any.whl
Installing collected packages: pip
  Found existing installation: pip 9.0.3
    Uninstalling pip-9.0.3:
      Successfully uninstalled pip-9.0.3
Successfully installed pip-10.0.1
```

- Then install the dependencies to the venv:

```console
/path/to/venv/bin/pip install -r requirements.txt -r test-requirements.txt
```

For example:

```console
$ bandersnatchvenv/bin/pip install -r requirements.txt -r test-requirements.txt
...
Collecting pyparsing==2.1.10 (from -r requirements.txt (line 3))
  Downloading https://files.pythonhosted.org/packages/2b/f7/e5a178fc3ea4118a0edce2a8d51fc14e680c745cf4162e4285b437c43c94/pyparsing-2.1.10-py2.py3-none-any.whl (56kB)
    100% |████████████████████████████████| 61kB 2.3MB/s
...
Installing collected packages: six, pyparsing, python-dateutil, packaging, requests, xmlrpc2, bandersnatch, pycodestyle, mccabe, pyflakes, flake8, pep8, py, pluggy, more-itertools, attrs, pytest, pytest-codecheckers, coverage, pytest-cov, pytest-timeout, apipkg, execnet, pytest-cache, virtualenv, tox
  Running setup.py install for pytest-codecheckers ... done
  Running setup.py install for pytest-cache ... done
Successfully installed apipkg-1.4 attrs-18.1.0 bandersnatch-2.1.3 coverage-4.5.1 execnet-1.5.0 flake8-3.5.0 mccabe-0.6.1 more-itertools-4.1.0 packaging-16.8 pep8-1.7.1 pluggy-0.6.0 py-1.5.3 pycodestyle-2.3.1 pyflakes-1.6.0 pyparsing-2.1.10 pytest-3.5.1 pytest-cache-1.0 pytest-codecheckers-0.2 pytest-cov-2.5.1 pytest-timeout-1.2.1 python-dateutil-2.6.0 requests-2.12.4 six-1.10.0 tox-3.0.0 virtualenv-15.2.0 xmlrpc2-0.3.1
```

- Then install bandersnatch in editable mode:

```console
/path/to/venv/bin/pip install -e .
```

- (Optional) finally setup pre-commit to run automatically before committing:

```console
/path/to/venv/bin/pre-commit run -a
```

Congrats, now you have a bandersnatch development environment ready to go! Just a few details to cover left.

### S3 Unit Tests

S3 unittests are more integration tests. They depend on [minio](https://docs.min.io/) to work.

- You will either need to skip them or install mino
- Install options: <https://docs.min.io/docs/>

#### Docker Install

Docker is an easy way to get minio to run for tests to pass.

```console
docker run \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio \
  -v /Users/cooper/tmp/minio:/data \
  minio/minio server /data --console-address ":9001"
```

## Creating a Pull Request

### Changelog entry

PRs must have an entry in CHANGES.md that references the PR number in the format of
"PR #{number}". You can get the number your PR will be assigned beforehand using
[Next PR Number](https://ichard26.github.io/next-pr-number/?owner=pypa&name=bandersnatch).
**Some trivial changes (eg. typo fixes) won't need an entry, but most
of the time, your change will. If unsure, take a look at what's been logged before
or just add one to be safe.**

This is enforced by a GitHub Actions workflow.

## Linting

We use pre-commit to run linters and formatters. If you never configured pre-commit to run automatically
or just want to do a full check of the codebase, please run pre-commit directly.

```console
cd bandersnatch
/path/to/venv/bin/pre-commit -a
```

## Running Bandersnatch

You will need to customize `src/bandersnatch/default.conf` and run via the following:

**WARNING: Bandersnatch will go off and sync from pypi.org and use large amounts of disk space!**

```console
cd bandersnatch
/path/to/venv/bin/pip install --upgrade .
/path/to/venv/bin/bandersnatch -c src/bandersnatch/default.conf mirror
```

## Running Unit Tests

We use tox to run tests. `tox.ini` has the options needed, so running tests is very easy.

```console
cd bandersnatch
/path/to/venv/bin/tox [-vv] [-e py3|docs]
```

Example output:

```console
$ tox
GLOB sdist-make: /Users/dhubbard/PycharmProjects/bandersnatch/setup.py
py36 create: /Users/dhubbard/PycharmProjects/bandersnatch/.tox/py36
py36 installdeps: -rtest-requirements.txt
py36 inst: /Users/dhubbard/PycharmProjects/bandersnatch/.tox/dist/bandersnatch-2.2.1.zip
py36 installed: apipkg==1.4,attrs==18.1.0,bandersnatch==2.2.1,certifi==2018.4.16,chardet==3.0.4,coverage==4.5.1,execnet==1.5.0,flake8==3.5.0,idna==2.6,mccabe==0.6.1,more-itertools==4.1.0,packaging==17.1,pep8==1.7.1,pluggy==0.6.0,py==1.5.3,pycodestyle==2.3.1,pyflakes==1.6.0,pyparsing==2.2.0,pytest==3.5.1,pytest-cache==1.0,pytest-codecheckers==0.2,pytest-cov==2.5.1,pytest-timeout==1.2.1,python-dateutil==2.7.3,requests==2.18.4,six==1.11.0,tox==3.0.0,urllib3==1.22,virtualenv==15.2.0,xmlrpc2==0.3.1
py36 runtests: PYTHONHASHSEED='42669967'
py36 runtests: commands[0] | pytest
========================================================================================================================= test session starts =========================================================================================================================
platform darwin -- Python 3.6.5, pytest-3.5.1, py-1.5.3, pluggy-0.6.0
rootdir: /Users/dhubbard/PycharmProjects/bandersnatch, inifile: pytest.ini
plugins: timeout-1.2.1, cov-2.5.1, codecheckers-0.2
timeout: 10.0s method: signal
collected 94 items

src/bandersnatch/__init__.py ..                                                                                                                                                                                                                                 [  2%]
src/bandersnatch/buildout.py ..                                                                                                                                                                                                                                 [  4%]
src/bandersnatch/log.py ..                                                                                                                                                                                                                                      [  6%]
src/bandersnatch/main.py ..                                                                                                                                                                                                                                     [  8%]
src/bandersnatch/master.py ..                                                                                                                                                                                                                                   [ 10%]
src/bandersnatch/mirror.py ..                                                                                                                                                                                                                                   [ 12%]
src/bandersnatch/package.py ..                                                                                                                                                                                                                                  [ 14%]
src/bandersnatch/release.py ..                                                                                                                                                                                                                                  [ 17%]
src/bandersnatch/utils.py ..                                                                                                                                                                                                                                    [ 19%]
src/bandersnatch/tests/conftest.py ..                                                                                                                                                                                                                           [ 21%]
src/bandersnatch/tests/test_main.py .......                                                                                                                                                                                                                     [ 28%]
src/bandersnatch/tests/test_master.py ...........                                                                                                                                                                                                               [ 40%]
src/bandersnatch/tests/test_mirror.py ....................                                                                                                                                                                                                      [ 61%]
src/bandersnatch/tests/test_package.py ..............................                                                                                                                                                                                           [ 93%]
src/bandersnatch/tests/test_utils.py ......                                                                                                                                                                                                                     [100%]

---------- coverage: platform darwin, python 3.6.5-final-0 -----------
Coverage HTML written to dir htmlcov


====================================================================================================================== 94 passed in 3.40 seconds ======================================================================================================================
_______________________________________________________________________________________________________________________________ summary _______________________________________________________________________________________________________________________________
  py36: commands succeeded
  congratulations :)
```

You want to see:

```console
py3: commands succeeded
congratulations :)
```

## Making a bandersnatch release to GitHub + PyPI

Please rely on our [pypi_upload](https://github.com/pypa/bandersnatch/blob/main/.github/workflows/pypi_upload.yml)
GitHub actions to build and upload our releases.

- To cut a release first make a PR updating:
  - the version in `setup.cfg` + `src/badnersnatch/__init__.py`
  - Update `CHANGES.md`. Here check for typos + missing commits that should be mentioned
    - Example PR: <https://github.com/pypa/bandersnatch/pull/1069>
- THen, once merged and CI is passing
  - Cut a [GitHub Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
    and GitHub Actions will package and upload to PyPI.
  - <https://github.com/pypa/bandersnatch/releases>
    - Select "Draft a new release"

### Conventions

- Use the version as the branch and tag names
- Copy the Change Log for the version from CHANGES.md
  - The web form supports markdown so it can be directly copied

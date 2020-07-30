# Contributing
So you want to help out? **Awesome**. Go you!

## Code of Conduct
Everyone interacting in the bandersnatch project's codebases, issue trackers,
chat rooms, and mailing lists is expected to follow the
[PSF Code of Conduct](https://github.com/pypa/.github/blob/main/CODE_OF_CONDUCT.md).

## Getting Started

Bandersnatch is developed using the [GitHub Flow](https://guides.github.com/introduction/flow/)

### Pre Install
Please make sure you system has the following:

- Python 3.6.1 or greater

### Development venv
One way to develop and install all the dependencies of bandersnatch is to use a venv.

- First create one and upgrade `pip`

```
python3.6 -m venv /path/to/venv
/path/to/venv/bin/pip install --upgrade pip
```

For example:
```console
$ python3.6 -m venv bandersnatchvenv
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

``` console
/path/to/venv/bin/pip install -r requirements.txt -r test-requirements.txt
```

For example:
```console
$ bandersnatchvenv/bin/pip install -r requirements.txt -r test-requirements.txt
Collecting six==1.10.0 (from -r requirements.txt (line 2))
  Downloading https://files.pythonhosted.org/packages/c8/0a/b6723e1bc4c516cb687841499455a8505b44607ab535be01091c0f24f079/six-1.10.0-py2.py3-none-any.whl
Collecting pyparsing==2.1.10 (from -r requirements.txt (line 3))
  Downloading https://files.pythonhosted.org/packages/2b/f7/e5a178fc3ea4118a0edce2a8d51fc14e680c745cf4162e4285b437c43c94/pyparsing-2.1.10-py2.py3-none-any.whl (56kB)
    100% |████████████████████████████████| 61kB 2.3MB/s
Collecting python-dateutil==2.6.0 (from -r requirements.txt (line 4))
  Downloading https://files.pythonhosted.org/packages/40/8b/275015d7a9ec293cf1bbf55433258fbc9d0711890a7f6dc538bac7b86bce/python_dateutil-2.6.0-py2.py3-none-any.whl (194kB)
    100% |████████████████████████████████| 194kB 1.3MB/s
Collecting packaging==16.8 (from -r requirements.txt (line 5))
  Downloading https://files.pythonhosted.org/packages/87/1b/c39b7c65b5612812b83d6cab7ef2885eac9f6beb0b7b8a7071a186aea3b1/packaging-16.8-py2.py3-none-any.whl
Collecting requests==2.12.4 (from -r requirements.txt (line 6))
  Downloading https://files.pythonhosted.org/packages/ed/9e/60cc074968c095f728f0d8d28370e8d396fa60afb7582735563cccf223dd/requests-2.12.4-py2.py3-none-any.whl (576kB)
    100% |████████████████████████████████| 583kB 3.2MB/s
Collecting xmlrpc2==0.3.1 (from -r requirements.txt (line 7))
Collecting bandersnatch==2.1.3 (from -r requirements.txt (line 8))
  Downloading https://files.pythonhosted.org/packages/25/41/9082fcbf20ff536f990e538957eed7474d78b9dcecd018530684ae058995/bandersnatch-2.1.3-py3-none-any.whl
Collecting flake8 (from -r test-requirements.txt (line 1))
  Downloading https://files.pythonhosted.org/packages/b9/dc/14e9d94c770b8c4ef584e906c7583e74864786a58d47de101f2767d50c0b/flake8-3.5.0-py2.py3-none-any.whl (69kB)
    100% |████████████████████████████████| 71kB 4.8MB/s
Collecting pep8 (from -r test-requirements.txt (line 2))
  Downloading https://files.pythonhosted.org/packages/42/3f/669429ce58de2c22d8d2c542752e137ec4b9885fff398d3eceb1a7f5acb4/pep8-1.7.1-py2.py3-none-any.whl (41kB)
    100% |████████████████████████████████| 51kB 9.6MB/s
Collecting pytest (from -r test-requirements.txt (line 3))
  Downloading https://files.pythonhosted.org/packages/76/52/fc48d02492d9e6070cb672d9133382e83084f567f88eff1c27bd2c6c27a8/pytest-3.5.1-py2.py3-none-any.whl (192kB)
    100% |████████████████████████████████| 194kB 2.8MB/s
Collecting pytest-codecheckers (from -r test-requirements.txt (line 4))
  Downloading https://files.pythonhosted.org/packages/53/09/263669db13955496e77017f389693c1e1dd77d98fd4afd51b133162e858f/pytest-codecheckers-0.2.tar.gz
Collecting pytest-cov (from -r test-requirements.txt (line 5))
  Downloading https://files.pythonhosted.org/packages/30/7d/7f6a78ae44a1248ee28cc777586c18b28a1df903470e5d34a6e25712b8aa/pytest_cov-2.5.1-py2.py3-none-any.whl
Collecting pytest-timeout (from -r test-requirements.txt (line 6))
  Downloading https://files.pythonhosted.org/packages/69/7f/33a67c2494c6c337daca935192b7de09d30b54e568c981ed0681380393c4/pytest_timeout-1.2.1-py2.py3-none-any.whl
Collecting pytest-cache (from -r test-requirements.txt (line 7))
  Downloading https://files.pythonhosted.org/packages/d1/15/082fd0428aab33d2bafa014f3beb241830427ba803a8912a5aaeaf3a5663/pytest-cache-1.0.tar.gz
Requirement already satisfied: setuptools in /private/tmp/bandersnatchvenv/lib/python3.6/site-packages (from -r test-requirements.txt (line 8)) (39.0.1)
Collecting tox (from -r test-requirements.txt (line 9))
  Downloading https://files.pythonhosted.org/packages/e6/41/4dcfd713282bf3213b0384320fa8841e4db032ddcb80bc08a540159d42a8/tox-3.0.0-py2.py3-none-any.whl (60kB)
    100% |████████████████████████████████| 61kB 2.2MB/s
Collecting pycodestyle<2.4.0,>=2.0.0 (from flake8->-r test-requirements.txt (line 1))
  Downloading https://files.pythonhosted.org/packages/e4/81/78fe51eb4038d1388b7217dd63770b0f428370207125047312886c923b26/pycodestyle-2.3.1-py2.py3-none-any.whl (45kB)
    100% |████████████████████████████████| 51kB 4.4MB/s
Collecting mccabe<0.7.0,>=0.6.0 (from flake8->-r test-requirements.txt (line 1))
  Downloading https://files.pythonhosted.org/packages/87/89/479dc97e18549e21354893e4ee4ef36db1d237534982482c3681ee6e7b57/mccabe-0.6.1-py2.py3-none-any.whl
Collecting pyflakes<1.7.0,>=1.5.0 (from flake8->-r test-requirements.txt (line 1))
  Downloading https://files.pythonhosted.org/packages/d7/40/733bcc64da3161ae4122c11e88269f276358ca29335468005cb0ee538665/pyflakes-1.6.0-py2.py3-none-any.whl (227kB)
    100% |████████████████████████████████| 235kB 2.6MB/s
Collecting py>=1.5.0 (from pytest->-r test-requirements.txt (line 3))
  Downloading https://files.pythonhosted.org/packages/67/a5/f77982214dd4c8fd104b066f249adea2c49e25e8703d284382eb5e9ab35a/py-1.5.3-py2.py3-none-any.whl (84kB)
    100% |████████████████████████████████| 92kB 3.8MB/s
Collecting pluggy<0.7,>=0.5 (from pytest->-r test-requirements.txt (line 3))
  Downloading https://files.pythonhosted.org/packages/ba/65/ded3bc40bbf8d887f262f150fbe1ae6637765b5c9534bd55690ed2c0b0f7/pluggy-0.6.0-py3-none-any.whl
Collecting more-itertools>=4.0.0 (from pytest->-r test-requirements.txt (line 3))
  Downloading https://files.pythonhosted.org/packages/7a/46/886917c6a4ce49dd3fff250c01c5abac5390d57992751384fe61befc4877/more_itertools-4.1.0-py3-none-any.whl (47kB)
    100% |████████████████████████████████| 51kB 3.9MB/s
Collecting attrs>=17.4.0 (from pytest->-r test-requirements.txt (line 3))
  Downloading https://files.pythonhosted.org/packages/41/59/cedf87e91ed541be7957c501a92102f9cc6363c623a7666d69d51c78ac5b/attrs-18.1.0-py2.py3-none-any.whl
Collecting coverage>=3.7.1 (from pytest-cov->-r test-requirements.txt (line 5))
  Downloading https://files.pythonhosted.org/packages/a3/7e/c94c21d643bfe7017615994df7b52292a33c8dcf36a6f694af110594edba/coverage-4.5.1-cp36-cp36m-macosx_10_12_x86_64.whl (178kB)
    100% |████████████████████████████████| 184kB 3.3MB/s
Collecting execnet>=1.1.dev1 (from pytest-cache->-r test-requirements.txt (line 7))
  Downloading https://files.pythonhosted.org/packages/f9/76/3343e69a2a1602052f587898934e5fea395d22310d39c07955596597227c/execnet-1.5.0-py2.py3-none-any.whl
Collecting virtualenv>=1.11.2 (from tox->-r test-requirements.txt (line 9))
  Downloading https://files.pythonhosted.org/packages/ed/ea/e20b5cbebf45d3096e8138ab74eda139595d827677f38e9dd543e6015bdf/virtualenv-15.2.0-py2.py3-none-any.whl (2.6MB)
    100% |████████████████████████████████| 2.6MB 3.3MB/s
Collecting apipkg>=1.4 (from execnet>=1.1.dev1->pytest-cache->-r test-requirements.txt (line 7))
  Downloading https://files.pythonhosted.org/packages/94/72/fd4f2e46ce7b0d388191c819ef691c8195fab09602bbf1a2f92aa5351444/apipkg-1.4-py2.py3-none-any.whl
Installing collected packages: six, pyparsing, python-dateutil, packaging, requests, xmlrpc2, bandersnatch, pycodestyle, mccabe, pyflakes, flake8, pep8, py, pluggy, more-itertools, attrs, pytest, pytest-codecheckers, coverage, pytest-cov, pytest-timeout, apipkg, execnet, pytest-cache, virtualenv, tox
  Running setup.py install for pytest-codecheckers ... done
  Running setup.py install for pytest-cache ... done
Successfully installed apipkg-1.4 attrs-18.1.0 bandersnatch-2.1.3 coverage-4.5.1 execnet-1.5.0 flake8-3.5.0 mccabe-0.6.1 more-itertools-4.1.0 packaging-16.8 pep8-1.7.1 pluggy-0.6.0 py-1.5.3 pycodestyle-2.3.1 pyflakes-1.6.0 pyparsing-2.1.10 pytest-3.5.1 pytest-cache-1.0 pytest-codecheckers-0.2 pytest-cov-2.5.1 pytest-timeout-1.2.1 python-dateutil-2.6.0 requests-2.12.4 six-1.10.0 tox-3.0.0 virtualenv-15.2.0 xmlrpc2-0.3.1
```

## Running Bandersnatch

You will need to customize `src/bandersnatch/default.conf` and run via the following:

**WARNING: Bandersnatch will go off and sync from pypi.org and use large amounts of disk space!**

``` console
cd bandersnatch
/path/to/venv/bin/pip install --upgrade .
/path/to/venv/bin/bandersnatch -c src/bandersnatch/default.conf mirror
```

## Running Unit Tests

We use tox to run tests. `tox.ini` has the options needed, so running tests is very easy.

```
cd bandersnatch
/path/to/venv/bin/tox [-vv]
```

For example:
``` console
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
```
py36: commands succeeded
congratulations :)
```


## Making a release
*To be completed - @cooper has never used zc.buildout*

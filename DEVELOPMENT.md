# bandernstach development

So you want to help out? **Awesome**. Go you!

## Getting Started

We use GitHub. To get started I'd suggest visiting https://guides.github.com/

### Pre Install
Please make sure you system has the following:

- Python 3.6 or greater
- git cli client

Also esure you can authenticate with GitHub via SSH Keys or HTTPS.

### Checkout `bandersnatch`

Lets now cd to where we want the code and use hg:

- `cd somewhere`
- `git clone git@github.com:pypa/bandersnatch.git`

### Development venv

One way to develop and install all the dependencies of bandersnatch is to use a venv.

- Lets create one and upgrade `pip`

```
python3 -m venv /path/to/venv
/path/to/venv/bin/pip install --upgrade pip setuptools
```

- Then we should install the dependencies to the venv:

```
/path/to/venv/bin/pip install -r requirements.txt
/path/to/venv/bin/pip install -r test-requirements.txt
```

## Running Bandersnatch

You will need to customize `src/bandersnatch/default.conf` and run via the following:

**WARNING: Bandersnatch will go off and sync from pypi.org and use disk space!**

```
cd bandersnatch
/path/to/venv/bin/pip install --upgrade .
/path/to/venv/bin/bandersnatch --help

/path/to/venv/bin/bandersnatch -c src/bandersnatch/default.conf mirror
```

## Running Unit Tests

We use tox to run tests. `tox.ini` has the options needed, so running tests is very easy.

```
cd bandersnatch
/path/to/venv/bin/tox [-vv]
```

You want to see:
```
py36: commands succeeded
congratulations :)
```


## Making a release

*To be completed - @cooper has never used zc.buildout*

* Tests green?
* run `bin/fullrelease`

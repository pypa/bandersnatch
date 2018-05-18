## Installation

The following instructions will place the bandersnatch executable in a
virtualenv under `bandersnatch/bin/bandersnatch`.

- bandersnatch **requires** `>= Python 3.5`


### pip

This installs the latest stable, released version.

```
  $ virtualenv --python=python3.5 bandersnatch
  $ cd bandersnatch
  $ bin/pip install -r https://bitbucket.org/pypa/bandersnatch/raw/stable/requirements.txt
```

### zc.buildout

This installs the current development version. Use 'hg up <version>' and run
buildout again to choose a specific release.

```
  $ hg clone https://bitbucket.org/pypa/bandersnatch
  $ cd bandersnatch
  $ ./bootstrap.sh
```

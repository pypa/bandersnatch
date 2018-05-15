# Configuration

Bandersnatch uses a ConfigParser format configuration file for configuration.

## Mirror configuration settings

The mirror configuration settings are in a configuration section of the configuratinon file
named **\[mirror\]**.

This section contains settings to specify how the mirroring software should operate.

### directory

The mirror directory setting is a string that specifies the directory to
store the mirror files.

The directory used must meet the following requirements:
- The filesystem must be case-sensitive filesystem.
- The filesystem must support large numbers of sub-directories.
- The filesystem must support large numbers of files (inodes)

Example:
``` ini
[mirror]
directory = /srv/pypi
```

### json

The mirror json seting is a boolean (true/false) setting that indicates that
the json packaging metadata should be mirrored in additon to the packages.

Example:
``` ini
[mirror]
json = false
```

### master

The master setting is a string containing a url of the server which will be mirrored.

The master url string must use https: protocol.

The default value is: https://pypi.org

Example:
``` ini
[mirror]
master = https://pypi.org
```

### timeout

The timeout value is an integer that indicates the maximum number of seconds for web requests.

The default value for this setting is 10 seconds.

Example:
``` ini
[mirror]
timeout = 10
```

### workers

The workers value is an integer from from 1-10 that indicates the number of concurrent downloads.

The default value is 3.

Recommendations for the workers setting:
- leave the default of 3 to avoid overloading the pypi master
- official servers located in data centers could run 10 workers
- anything beyond 10 is probably unreasonable and is not allowed.

### hash-index

The hash-index is a boolean (true/false) ot determine if package hashing should be used.

The Recommended setting: the default of false for full pip/pypi compatability.

```eval_rst
.. warning:: Package index directory hashing is incompatible with pip, and so this should only be used in an environment where it is behind an application that can translate URIs to filesystem locations.
```

#### Apache rewrite rules when using hash-index

When using this setting with an apache server.  The apache server will need the following rewrite rules:

```
RewriteRule ^([^/])([^/]*)/$ /mirror/pypi/web/simple/$1/$1$2/
RewriteRule ^([^/])([^/]*)/([^/]+)$/ /mirror/pypi/web/simple/$1/$1$2/$3
```

#### NGINX rewrite rules when using hash-index

When using this setting with an nginx server.  The nginx server will need the following rewrite rules:

```
rewrite ^/simple/([^/])([^/]*)/$ /simple/$1/$1$2/ last;
rewrite ^/simple/([^/])([^/]*)/([^/]+)$/ /simple/$1/$1$2/$3 last;
```

### stop-on-error

The stop-on-error setting is a boolean (true/false) setting that indicates if bandersnatch
should execute immediately if it encounters an error.

If this setting is false it will not stop when an error is encountered but it will not
mark the sync as successful when the sync is complete.

``` ini
[mirror]
stop-on-error = false
```

### delete-packages

The **delete-packages** setting is a boolean (true/false) value.  If this
setting is true (enabled).  Bandersnatch will delete any packages from the
mirror that have been deleted on the master.

The default value for this setting is false.

```eval_rst
.. important:: if you are running an official mirror than you *need* to leave this on.
```

### log-config

The log-config setting is as string containing the filename of a python logging configuration
file.

Example:
```ini
[mirror]
log-config = /etc/bandersnatch-log.conf
```

### root_uri

The root_uri is a string containing a uri which is the root added to relative links.

``` eval_rst
.. note:: This is generally not necessary, but was added for the official internal PyPI mirror, which requires serving packages from https://files.pythonhosted.org
```

Example:
```ini
[mirror]
root_uri = https://example.com
```

## Blacklist Settings

The blacklist settings are in a configuration section named **\[blacklist\]**,
this section provides settings to indicate packages that should not be
mirrored from pypi.

This is useful to avoid syncing broken or malicious packages.

### packages

The packages setting is a list of python [pep440 version specifier](https://www.python.org/dev/peps/pep-0440/#id51) of packages to not be mirrored.

Any packages matching the version specifier will not be downloaded.

Example:
``` ini
[blacklist]
packages =
    example1
    example2>=1.4.2,<1.9,!=1.5.*,!=1.6.*
```

### filenames

The filenames setting specifies filenames or filename glob that should not be synced.

This is useful to prevent mirroring package files that are in a format that is not used by
users of the mirror.

Example:
```ini
filenames =
    *.exe
    *.msi
    *.win32.whl
    *.win_amd64.whl
````
## Mirror configuration

The mirror configuration settings are in a configuration section of the configuration file
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

### global-timeout

The global-timeout value is an integer that indicates the maximum runtime of individual asyncio coroutines.

The default value for this setting is 18000 seconds, or 5 hours.

Example:
```ini
[mirror]
global-timeout = 18000
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

The Recommended setting: the default of false for full pip/pypi compatibility.

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


### diff-file

The diff file is a string containing the filename to log the files that were downloaded during the mirror.
This file can then be used to synchronize external disks or send the files through some other mechanism to offline systems.
You can then sync the list of files to an attached drive or ssh destination such as a diode:
```
rsync -av --files-from=/srv/pypi/mirrored-files / /mnt/usb/
```

You can also use this file list as an input to 7zip to create split archives for transfers, allowing you to size the files as you needed:
```
7za a -i@"/srv/pypi/mirrored-files" -spf -v100m path_to_new_zip.7z
```

Example:
```ini
[mirror]
diff-file = /srv/pypi/mirrored-files
```



### diff-append-epoch

The diff append epoch is a boolean (true/false) setting that indicates if the diff-file should be appended with the current epoch time.
This can be used to track diffs over time so the diff file doesn't get cobbered each run.  It is only used when diff-file is used.

Example:
```ini
[mirror]
diff-append-epoch = true
```

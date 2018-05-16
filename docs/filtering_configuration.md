## Mirror filtering

The mirror filter configuration settings are in the same configuration file as the mirror settings.

There are different configuration sections for the different plugin types.

### Blacklist filtering settings

The blacklist settings are in a configuration section named **\[blacklist\]**,
this section provides settings to indicate packages, projects and releases that should
not be mirrored from pypi.

This is useful to avoid syncing broken or malicious packages.

### plugins

The plugins setting is a list of plugins to enable.

``` eval_rst
.. note: If this setting is missing, all installed plugins are enabled.
```

Example (enable all installed filter plugins):
``` eval_rst
[blacklist]
plugins = all
```

Example (only enable filtering of whole projects/packages):
``` eval_rst
[blacklist]
plugins =
    blacklist_project
```

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
[blacklist]
filenames =
    *.exe
    *.msi
    *.win32.whl
    *.win_amd64.whl
````
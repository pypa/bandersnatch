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
- *Explicitly* enabling plugins is now **mandatory** for *activating plugins*
- They will *do nothing* without activation

Also, enabling will get plugin's defaults if not configured in their respective sections.

``` ini
[plugins]
enabled = all
```

Example (only enable specific plugins):
``` ini
[plugins]
enabled =
    blacklist_project
    whitelist_project
    ...
```

### packages

The packages setting is a list of python [pep440 version specifier](https://www.python.org/dev/peps/pep-0440/#id51) of packages to not be mirrored.

Any packages matching the version specifier will not be downloaded.

Example:
``` ini
[plugins]
enabled =
    blacklist_project
    whitelist_project

[blacklist]
packages =
    example1
    example2>=1.4.2,<1.9,!=1.5.*,!=1.6.*

[whitelist]
packages =
    black
    ptr
```

### Prerelease filtering

Bandersnatch includes a plugin to filter our pre-releases of packages. To enable this plugin simply add `prerelease_release` to the enabled plugins list.

``` ini
[plugins]
enabled =
    prerelease_release
```

### Regex filtering

Advanced users who would like finer control over which packages and releases to filter can use the regex Bandersnatch plugin.

This plugin allows arbitrary regular expressions to be defined in the configuration, any package name or release version that matches will *not* be downloaded.

The plugin can be activated for packages and releases separately. For example to activate the project regex filter simply add it to the configuration as before:

``` ini
[plugins]
enabled =
    regex_project
```

If you'd like to filter releases using the regex filter use `regex_release` instead.

The regex plugin requires an extra section in the config to define the actual patterns to used for filtering:

``` ini
[filter_regex]
packages =
    .+-evil$
releases =
    .+alpha\d$
```

Note the same `filter_regex` section may include a `packages` and a `releases` entry with any number of regular expressions.


### Platform-specific binaries filtering

This filter allows advanced users not interesting in Windows/macOS/Linux specific binaries to not mirror the corresponding files.


``` ini
[plugins]
enabled =
    exclude_platform
platforms =
    windows
```

Available platforms are: `windows` `macos` `freebsd` `linux`.


### Keep only latest releases

You can also keep only the latest releases based on greatest [Version](https://packaging.pypa.io/en/latest/version/) numbers.

``` ini
[plugins]
enabled =
    latest_release

[latest_release]
keep = 3
```

By default, the plugin does not filter out any release. You have to add the `keep` setting.

You should be aware that it can break requirements.

## Mirror filtering

_NOTE: All references to whitelist/blacklist are deprecated, and will be replaced with allowlist/denylist in 5.0_

The mirror filter configuration settings are in the same configuration file as the mirror settings.
There are different configuration sections for the different plugin types.

Filtering Plugin pacakage lists need to use the **Raw PyPI Name**
(non [PEP503](https://www.python.org/dev/peps/pep-0503/#normalized-names) normailized)
in order to get filtered.

E.g. to Blacklist [ACMPlus](https://pypi.org/project/ACMPlus/) you'd need to
use that *exact* case in `bandersnatch.conf`

- A PR would be welcome fixing the normalization but it's an invasive PR

### Plugins Enabling

The plugins setting is a list of plugins to enable.

Example (enable all installed filter plugins):

- *Explicitly* enabling plugins is now **mandatory** for *activating plugins*
- They will *do nothing* without activation

Also, enabling will get plugin's defaults if not configured in their respective sections.

```ini
[plugins]
enabled = all
```

Example (only enable specific plugins):

```ini
[plugins]
enabled =
    blacklist_project
    whitelist_project
    ...
```

### blacklist / whitelist filtering settings

The blacklist settings are in a configuration sections named **\[blacklist\]** and **\[whitelist\]**
this section provides settings to indicate packages, projects and releases that should
not be mirrored from PyPI.

This is useful to avoid syncing broken or malicious packages.

### packages

The packages setting is a list of python [pep440 version specifier](https://www.python.org/dev/peps/pep-0440/#id51) of packages to not be mirrored. Enable version specifier filtering for whitelist and blacklist packages through enabling the 'blacklist_release' and 'allowlist_release' plugins, respectively.

Any packages matching the version specifier for blacklist packages will not be downloaded. Any packages not matching the version specifier for whitelist packages will not be downloaded.

Example:

```ini
[plugins]
enabled =
    blacklist_project
    blacklist_release
    whitelist_project
    allowlist_release

[blacklist]
packages =
    example1
    example2>=1.4.2,<1.9,!=1.5.*,!=1.6.*

[whitelist]
packages =
    black==18.5
    ptr
```

### Metadata Filtering
Packages and release files may be selected by filtering on specific metadata value.

General form of configuration entries is:

```ini
[filter_some_metadata]
tag:tag:path.to.object =
    matcha
    matchb
```

#### Project Regex Matching

Filter projects to be synced based on regex matches against their raw metadata entries straight from parsed downloaded json.

Example:

```ini
[regex_project_metadata]
not-null:info.classifiers =
        .*Programming Language :: Python :: 2.*
```

Valid tags are `all`,`any`,`none`,`match-null`,`not-null`, with default of `any:match-null`

All metadata provided by json is available, including `info`, `last_serial`, `releases`, etc. headings.


#### Release File Regex Matching

Filter release files to be downloaded for projects based on regex matches against the stored metadata entries for each release file.

Example:

```ini
[regex_release_file_metadata]
any:release_file.packagetype =
    sdist
    bdist_wheel
```

Valid tags are the same as for projects.

Metadata available to match consists of `info`, `release`, and `release_file` top level structures, with `info`
containing the package-wide inthe fo, `release` containing the version of the release and `release_file` the metadata
for an individual file for that release.


### Prerelease filtering

Bandersnatch includes a plugin to filter our pre-releases of packages. To enable this plugin simply add `prerelease_release` to the enabled plugins list.

```ini
[plugins]
enabled =
    prerelease_release
```

### Regex filtering

Advanced users who would like finer control over which packages and releases to filter can use the regex Bandersnatch plugin.

This plugin allows arbitrary regular expressions to be defined in the configuration, any package name or release version that matches will *not* be downloaded.

The plugin can be activated for packages and releases separately. For example to activate the project regex filter simply add it to the configuration as before:

```ini
[plugins]
enabled =
    regex_project
```

If you'd like to filter releases using the regex filter use `regex_release` instead.

The regex plugin requires an extra section in the config to define the actual patterns to used for filtering:

```ini
[filter_regex]
packages =
    .+-evil$
releases =
    .+alpha\d$
```

Note the same `filter_regex` section may include a `packages` and a `releases` entry with any number of regular expressions.


### Platform-specific binaries filtering

This filter allows advanced users not interesting in Windows/macOS/Linux specific binaries to not mirror the corresponding files.


```ini
[plugins]
enabled =
    exclude_platform
[blacklist]
platforms =
    windows
```

Available platforms are: `windows` `macos` `freebsd` `linux`.


### Keep only latest releases

You can also keep only the latest releases based on greatest [Version](https://packaging.pypa.io/en/latest/version/) numbers.

```ini
[plugins]
enabled =
    latest_release

[latest_release]
keep = 3
```

By default, the plugin does not filter out any release. You have to add the `keep` setting.

You should be aware that it can break requirements.

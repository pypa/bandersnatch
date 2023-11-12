# Mirror filtering

_NOTE: All references to whitelist/blacklist are deprecated, and will be replaced with allowlist/blocklist in 5.0_

The mirror filter configuration settings are in the same configuration file as the mirror settings.
There are different configuration sections for the different plugin types.

Filtering Plugin package lists can use the
[PEP503](https://peps.python.org/pep-0503/#normalized-names) normalized
names. Any non-normalized names in `bandersnatch.conf` will be automatically
converted.

E.g. to Blocklist [discord.py](https://pypi.org/project/discord.py/) the string 'discord-py'
is correct, but 'discord.PY' will also work.

Plugins for release version filtering usually act in a way, that releases are only downloaded if all filter plugin rules are satisfied.
An exception to this rule is the `project_requirements_pinned` filter: if there is a version number/range specified no other filter are applied.
This allows smaller mirrors with newest versions and specifically needed ones.

## Plugins Enabling

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
    allowlist_project
    blocklist_project
    ...
```

## allowlist / blocklist filtering settings

The blocklist / allowlist settings are in configuration sections named **\[blocklist\]** and **\[allowlist\]**
these section provides settings to indicate packages, projects and releases that should /
should not be mirrored from PyPI.

This is useful to avoid syncing broken or malicious packages.

## packages

The packages setting is a list of python [pep440 version specifier](https://peps.python.org/pep-0440/#version-specifiers) of packages to not be mirrored. Enable version specifier filtering for blocklist and allowlist packages through enabling the 'blocklist_release' and 'allowlist_release' plugins, respectively.

Any packages matching the version specifier for blocklist packages will not be downloaded. Any packages not matching the version specifier for allowlist packages will not be downloaded.

Example:

```ini
[plugins]
enabled =
    blocklist_project
    blocklist_release
    allowlist_project
    allowlist_release

[blocklist]
packages =
    example1
    example2>=1.4.2,<1.9,!=1.5.*,!=1.6.*

[allowlist]
packages =
    black==18.5
    ptr
```

## Metadata Filtering

Packages and release files may be selected by filtering on specific metadata value.

General form of configuration entries is:

```ini
[filter_some_metadata]
tag:tag:path.to.object =
    matcha
    matchb
```

## requirements files Filtering

Packages and releases might be given as requirements.txt files

if requirements_path is missing it is assumed to be system root folder ('/')

```ini
[plugins]
enabled =
    project_requirements
    project_requirements_pinned
[allowlist]
requirements_path = /my_folder
requirements =
    requirements.txt
```

Requirements file can be also expressed as a glob file name. In the following example all the requirements files matching the `requirements-*.txt` pattern will be considered and loaded.

```ini
[plugins]
enabled =
    project_requirements
[allowlist]
requirements_path = /requirements
requirements =
    requirements-*.txt
```

### Project Regex Matching

Filter projects to be synced based on regex matches against their raw metadata entries straight from parsed downloaded json.

Example:

```ini
[regex_project_metadata]
not-null:info.classifiers =
        .*Programming Language :: Python :: 2.*
```

Valid tags are `all`,`any`,`none`,`match-null`,`not-null`, with default of `any:match-null`

All metadata provided by json is available, including `info`, `last_serial`, `releases`, etc. headings.

### Release File Regex Matching

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
containing the package-wide info, `release` containing the version of the release and `release_file` the metadata
for an individual file for that release.

## Prerelease filtering

Bandersnatch includes a plugin to filter our pre-releases of packages. To enable this plugin simply add `prerelease_release` to the enabled plugins list.

```ini
[plugins]
enabled =
    prerelease_release
```

If you only want to filter out the pre-releases for some specific projects (e.g. with nightly updates), list them in the configuration like:

```ini
[filter_prerelease]
packages =
    duckdb
```

## Regex filtering

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

## Platform/Python-specific binaries filtering

This filter allows advanced users not interesting in Windows/macOS/Linux specific binaries to not mirror the corresponding files.

You can also exclude Python versions by their minor version (ex. Python 2.6, 2.7) if you're sure your mirror does not need to serve these binaries.

```ini
[plugins]
enabled =
    exclude_platform
[blocklist]
platforms =
    windows
    py2.6
    py2.7
```

Available platforms are:

- `windows`
- `macos`
- `freebsd`
- `linux`

Available python versions are:

- `py2.4` ~ `py2.7`
- `py3.1` ~ `py3.10`

## Keep only latest releases

You can also keep only the latest releases based on greatest [Version](https://packaging.pypa.io/en/latest/version.html) numbers.

```ini
[plugins]
enabled =
    latest_release

[latest_release]
keep = 3
sort_by = [version|time]
```

By default, the plugin does not filter out any release. You have to add the `keep` setting.
The default is to sort by `version` number (parsed according to semantic versioning).
As an alternative, `time` can be used to sort releases chronologically by upload time and select the last `keep` ones.

You should be aware that it can break requirements. Prereleases are also kept.

## Block projects above a specified size threshold

There is an increasing number of projects that consume a large amount of space.
At the time of writing (Jan 2021) the [stats](https://pypi.org/stats/) shows some
of the top projects consume over 100GB each, and the top 100 projects all consume
more than 8GB each.

If your usecase for a PyPI mirror is to have the diversity of packages but you
have storage constraints, it may be preferable to block large packages. This
can be done with the `size_project_metadata` plugin.

```ini
[plugins]
enabled =
    size_project_metadata

[size_project_metadata]
max_package_size = 1G
```

This will block the download of any project whose total size exceeds 1GB. (The
value of `max_package_size` can be either an integer number of bytes or a human-
readable value as shown.)

It can be combined with an allowlist to overrule the size limit for large projects
you are actually interested in and want make exceptions for. The following has the
logic of including all projects where the size is \<1GB *or* the name is
[numpy](https://pypi.org/project/numpy/).

```ini
[plugins]
enabled =
    size_project_metadata

[allowlist]
packages =
    numpy

[size_project_metadata]
max_package_size = 1G
```

If the allowlist_project is also enabled, then the filter becomes a logical
and, e.g. the following will include all projects where the size is \<1GB *and* the
name appears in the allowlist:

```ini
[plugins]
enabled =
    size_project_metadata
    allowlist_project

[allowlist]
packages =
    numpy
    scapy
    flask

[size_project_metadata]
max_package_size = 1G
```

Note that because projects naturally grow in size, one that was once within the
size can grow beyond the limit, and will stop being updated. It is then a choice
for the maintainer to make whether to add the package to the exception list
(and possibly run a `bandersnatch mirror --force-check`) or to prune the project
from the mirror (with `bandersnatch delete <package_name>`).

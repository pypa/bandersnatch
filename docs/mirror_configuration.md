# Mirror Configuration

The **\[mirror\]** section of the configuration file contains general options for how Bandersnatch should operate. This includes settings like the source repository to mirror, how to store mirrored files, and the kinds of files to include in the mirror.

## Examples

These examples only show `[mirror]` options; a complete configuration may include [mirror filtering plugins][filter-plugins] and/or options for a [storage backend][storage-backends].

### Minimal

The simplest configuration may only set an output folder:

```ini
[mirror]
directory = /srv/pypi
```

This will mirror index files and package release files from pypi.org. Add configuration for [mirror filtering plugins][filter-plugins] to control what packages are mirrored.

### More Options

This shows a few of the more common configuration options:

```ini
[mirror]
directory = /srv/pypi

; parallel downloads, keep low to avoid overwhelming upstream
workers = 2

; per-request time limit
timeout = 15

; per-coroutine time limit
global-timeout = 9000

; save list of downloaded file names
diff-file = /srv/pypi/new-files
diff-append-epoch  = true

; save previous versions of index files
keep_index_versions = 3
```

### Alternative Download Source

It is possible to download metadata from one repository, but package release files from another:

```ini
[mirror]
directory = /srv/pypi
; Project and package metadata received from this repository
master = https://pypi.org/
; Package distribution artifacts downloaded from here if possible
download-mirror = https://pypi-mirror.example.com/
```

This will download release files from `https://pypi-mirror.example.com` if possible and fall back to PyPI if a download fails. See [](./mirror_configuration.md#download-mirror). Add [](./mirror_configuration.md#download-mirror-no-fallback) to download release files exclusively from `download-mirror`.

### Index Files Only

It is possible to mirror just index files without downloading any package release files:

```ini
[mirror]
directory = /srv/pypi-filtered
simple-format = ALL
release-files = false
root_uri = https://files.pythonhosted.org/
```

This will mirror index files for projects and versions allowed by your [mirror filters][filter-plugins], but will not download any package release files. File URLs in index files will use the configured `root_uri`. See [](./mirror_configuration.md#release-files) and [](./mirror_configuration.md#root_uri).

## Option Reference

%
% mirror output / file structure related
%

### `directory`

The directory where mirrored files are stored. _This option is always required._

:Type: folder path
:Required: **yes**

The exact interpretation of this value depends on the configured [storage backend](./mirror_configuration.md#storage-backend). For the default [filesystem](#storage-backend-filesystem) backend, the directory used should meet the following requirements:

- The filesystem must be case-sensitive.
- The filesystem must support large numbers of sub-directories.
- The filesystem must support large numbers of files (inodes)

### `storage-backend`

The [storage backend][storage-backends] used to save data and metadata when mirroring packages.

:Type: string
:Default: `filesystem`

```{seealso}
Available storage backends are documented at [][storage-backends].
```

### `simple-format`

The formats to generate for project index files.

:Type: one of `HTML`, `JSON`, or `ALL`
:Default: `ALL`

The [Simple Repository API][simple-repository-api] allows serving project indexes in either HTML format, JSON format, or both. Bandersnatch generates both formats by default. [](#file-structure-simple-format) describes the generated folder structure and file names.

### `release-files`

Mirror package release files. Release files are the uploaded sdist and wheel files for mirrored projects.

:Type: boolean
:Default: true

Disabling this will mirror repository [index files](./mirror_configuration.md#simple-format) and/or [project metadata](./mirror_configuration.md#json) without downloading any associated package files. [](#file-structure-release-files) describes the folder structure for mirrored package release files.

```{note}
If `release-files = false`, you should also specify the [](./mirror_configuration.md#root_uri) option.
```

### `json`

Save copies of JSON project metadata downloaded from PyPI.

:Type: boolean
:Default: false

When enabled, this saves copies of all JSON project metadata downloaded from the [PyPI JSON API](https://warehouse.pypa.io/api-reference/json.html). This does _not_ effect the generation of simple repository API index files in JSON format ([](./mirror_configuration.md#simple-format)). The project metadata can be consumed by other tools or used for debugging. Bandersnatch does not make additional use of these files.

[](#file-structure-json) describes the folder structure for saved JSON metadata files.

### `root_uri`

A base URL to generate absolute URLs for package release files.

:Type: URL
:Default: `https://files.pythonhosted.org/`

Bandersnatch creates index files containing relative URLs by default. Setting this option generates index files with absolute URLs instead.

If [](./mirror_configuration.md#release-files) is disabled _and_ this option is unset, Bandersnatch uses a default value of `https://files.pythonhosted.org/`.

```{note}
This is generally not necessary, but was added for the official internal PyPI mirror, which requires serving packages from `<https://files.pythonhosted.org>`.
```

### `diff-file`

Create a file containing the paths of all files downloaded during a mirror operation.

:Type: file or folder path
:Default: none

This is useful when mirroring to an offline network where it is required to only transfer new files to the downstream mirror. The diff file can be used to copy new files to an external drive, sync the list of files to an SSH destination such as a diode, or send the files through some other mechanism to an offline system.

If the specified path is a directory, Bandersnatch will use the file name "`mirrored-files`" within that directory.

The file will be overwritten on each mirror operation unless [](./mirror_configuration.md#diff-append-epoch) is enabled.

#### Example Usage

The diff file can be used with rsync for copying only new files:

```console
rsync -av --files-from=/srv/pypi/mirrored-files / /mnt/usb/
```

It can also be used with 7zip to create split archives for transfers:

```console
7za a -i@"/srv/pypi/mirrored-files" -spf -v100m path_to_new_zip.7z
```

### `diff-append-epoch`

Appending the current epoch time to the file name for [](./mirror_configuration.md#diff-file).

:Type: boolean
:Default: false

For example, the configuration:

```ini
[mirror]
; ...
diff-file = /srv/pypi/new-files
diff-append-epoch = true
```

Will generate diff files with names like `/srv/pypi/new-files-1568129735`. This can be used to track diffs over time by creating a new diff file each run. It is only used when [](./mirror_configuration.md#diff-file) is used.

### `hash-index`

Group generated project index folders by the first letter of their normalized project name.

:Type: boolean
:Default: false

Enabling this changes the way generated index files are organized. Project folders are grouped into subfolders alphabetically as shown here: [](#file-structure-hash-index). This has the effect of splitting up a large `/web/simple` directory into smaller subfolders, each containing a subset of the index files. This can improve file system efficiency when mirroring a very large number of projects, but requires a web server capable of translating Simple Repository API URLs into file paths.

```{warning}
It is recommended to leave this set to `false` for full pip/pypi compatibility.

The path structure created by this option is _incompatible_ with the [Simple Repository API][simple-repository-api]. Serving the generated `web/simple/` folder directly will not work with pip. `hash-index` should only be used with a web server that can translate request URIs into alternative filesystem locations.

Requests for subfolders of `/web/simple` must be re-written using the first letter of the requested project name:

- Requested path: `/simple/someproject/index.html`
- Translated path: `/simple/s/someproject/index.html`
```

#### Example Apache `RewriteRule` Configuration

Configuration like the following is required to use the `hash-index` option with an Apache web server:

```
RewriteRule ^([^/])([^/]*)/$ /mirror/pypi/web/simple/$1/$1$2/
RewriteRule ^([^/])([^/]*)/([^/]+)$/ /mirror/pypi/web/simple/$1/$1$2/$3
```

#### Example NGINX `rewrite` Configuration

Configuration like the following is required to use `hash-index` with an NGINX web server:

```
rewrite ^/simple/([^/])([^/]*)/$ /simple/$1/$1$2/ last;
rewrite ^/simple/([^/])([^/]*)/([^/]+)$/ /simple/$1/$1$2/$3 last;
```

%
% Mirror source / network related options
%

### `master`

The URL of the Python package repository server to mirror.

:Type: URL
:Default: `https://pypi.org`

Bandersnatch requests metadata for projects and packages from this repository server, and downloads package release files from the URLs specified in the received metadata.

The URL _must_ use the `https:` protocol.

```{seealso}
Bandersnatch can download package release files from an alternative source by configuring a [](./mirror_configuration.md#download-mirror).
```

### `proxy`

Use an HTTP proxy server.

:Type: URL
:Default: none

The proxy server is used when sending requests to a repository server set by the [](./mirror_configuration.md#master) or [](./mirror_configuration.md#download-mirror) option.

```{seealso}
The proxy value will be passed to `aiohttp` as the "proxy" parameter, like `aiohttp.get(link, proxy=yourproxy)`. Check the aioproxy manual for more details: <https://docs.aiohttp.org/en/stable/client_advanced.html#proxy-support>
```

### `timeout`

The network request timeout to use for all connections, in seconds. This is the maximum allowed time for individual web requests.

:Type: number, in seconds
:Default: 10

```{note}
The default is purposefully set to a very low value. This is so temporary problems will fail quickly and allow retrying, instead of having a process hang infinitely and leave TCP unable to catch up for a long time.
```

### `global-timeout`

The maximum runtime of individual aiohttp coroutines, in seconds.

:Type: number, in seconds
:Default: 18000

```{note}
The default is purposefully set to a very high value - 18,000 seconds, or 5 hours. This supports coroutines mirroring large package files on slow connections.
```

### `download-mirror`

Download package release files from an alternative repository server.

:Type: URL
:Default: none

By default, Bandersnatch downloads packages from the URL supplied in the master server's JSON response. Setting this option to a repository URL will try to download release files from that repository first, and fallback to the URL supplied by the master server if that is unsuccessful (unable to get content or checksum mismatch).

This is useful to sync most of the files from an existing, nearby mirror - for example, when creating a new mirror identical to an existing one for the purpose of load sharing.

### `download-mirror-no-fallback`

Disable the fallback behavior for [](./mirror_configuration.md#download-mirror).

:Type: boolean
:Default: false

When set to `true`, Bandersnatch only downloads package distribution artifacts from the repository set in [](./mirror_configuration.md#download-mirror) and ignores file URLs received from the [](./mirror_configuration.md#master) server.

```{warning}
This could lead to more failures than expected and is not recommended for most scenarios.
```

%
% processing and miscellaneous options
%

### `cleanup`

Enable cleanup of legacy simple directories with non-normalized names.

:Type: boolean
:Default: false

Bandersnatch versions prior to 4.0 used directories with non-normalized package names for compatability with older versions of pip. Enabling this option checks for and removes these directories.

```{seealso}
[Python Packaging User Guide - Names and Normalization](https://packaging.python.org/en/latest/specifications/name-normalization/)
```

### `workers`

The number of worker threads used for parallel downloads.

:Type: number, 1 ≤ N ≤ 10
:Default: 3

Recommendations:

- leave the default of 3 to avoid overloading the pypi master
- official servers located in data centers could run up to 10 workers
- anything beyond 10 is probably unreasonable and is disallowed

### `verifiers`

The number of parallel consumers used for verifying metadata.

:Type: number
:Default: 3

### `stop-on-error`

Stop mirror/sync operations immediately when an error occurs.

:Type: boolean
:Default: false

By default Bandersnatch continues syncing after an error occurs, but will mark the sync as unsuccessful. If `stop-on-error = true`, it will stop all syncing as soon as possible if an error occurs. This can be helpful when debugging the cause of an unsuccessful sync.

### `compare-method`

The method used to compare existing files with upstream files.

:Type: one of `hash`, `stat`
:Default: `hash`

- `hash`: compare by creating a checksums of a local file content. This is slower than `stat`, but more reliable. The hash algorithm is specified by [](./mirror_configuration.md#digest_name).
- `stat`: compare by using file size and change time. This can reduce IO workload when frequently verifying a large number of files.

### `digest_name`

The algorithm used to compute file hashes when [](./mirror_configuration.md#compare-method) is set to `hash`.

:Type: one of `sha256`, `md5`
:Default: `sha256`

### `keep_index_versions`

Store previous versions of generated index files.

:Type: number
:Default: 0

This can be used as a safeguard against upstream changes generating blank index.html files.

By default or when set to 0, no prior versions are stored and `index.html` is the latest version.

When enabled by setting a value > 0, Bandersnatch stores the most recently generated versions of each index file, up to the configured number of versions. Prior versions are stored under `versions/index_<serial>_<timestamp>.html` and the current `index.html` is a symlink to the latest version.

### `log-config`

Provide a custom logging configuration file.

:type: file path
:Default: none

The file must be a Python `logging.config` module configuration file in INI format, as used with [](inv:python:py:function:#logging.config.fileConfig). The specified configuration replaces Bandersnatch's default logging configuration.

```{seealso}

% myst-inv.exe 'https://docs.python.org/3' -d std -o label -n logging-config-fileformat

Refer to [](inv:python:std:label#logging-config-fileformat) for the logging configuration file format.
```

#### Sample Alternative Logging Configuration

```ini
[loggers]
keys=root,file
[handlers]
keys=root,file
[formatters]
keys=common
[logger_root]
level=NOTSET
handlers=root
[logger_file]
level=INFO
handlers=file
propagate=1
qualname=bandersnatch
[formatter_common]
format=%(asctime)s %(name)-12s: %(levelname)s %(message)s
[handler_root]
class=StreamHandler
level=DEBUG
formatter=common
args=(sys.stdout,)
[handler_file]
class=handlers.TimedRotatingFileHandler
level=DEBUG
formatter=common
delay=False
args=('/repo/bandersnatch/banderlogfile.log', 'D', 1, 0)

```

## Folder Structures

(file-structure-simple-format)=

### `simple-format` index files

Folder structure of generated index files for [](./mirror_configuration.md#simple-format):

```text
<mirror directory>/
└── web/
    ├── packages/...
    └── simple/
        ├── index.html
        ├── index.v1_html
        ├── index.v1_json
        ├── someproject/
        │   ├── index.html
        │   ├── index.v1_html
        │   └── index.v1_json
        ├── anotherproject/
        │   ├── index.html
        │   ├── index.v1_html
        │   └── index.v1_json
        └── ...
```

This path structure is compatible with the [Simple Repository API][simple-repository-api].

If `simple-format` is set to `HTML`, Bandersnatch will only create `index.html` and `index.v1_html`. If `simple-format` is set to `JSON`, it will only create `index.v1_json`.

(file-structure-release-files)=

### `release-files` folder structure

Package release files are distributed into subdirectories based on their checksum:

```text
<mirror directory>/
└── web/
    ├── packages/
    │   ├── 1a/
    │   │   └── 70/
    │   │       └── e63223f8116931d365993d4a6b7ef653a4d920b41d03de7c59499962821f/
    │   │           └── click-8.1.6-py3-none-any.whl
    │   ├── 8b/
    │   │   ├── 3a/
    │   │   │   └── b569b932cf737b525eb4c7a2b615ec07b102dff64f1d8a0fe52a48b911fc/
    │   │   │       └── diff-2023.12.5.tar.gz
    │   │   └── e2/
    │   │       └── 4823d9f02d2743a02e2c236f98b96b52f7a16b2bedc0e3148322dffbd06f/
    │   │           └── black-24.1.0-cp39-cp39-win_amd64.whl
    │   ├── 31/
    │   │   ├── 5f/
    │   │   │   └── ...
    │   │   └── 7a/
    │   │       └── ...
    │   └── ...
    └── simple/
        ├── click/
        ├── diff/
        ├── black/
        ├── ...
        └── index.html
```

By default, generated index files contain releative links into the `web/packages/` directory.

(file-structure-json)=

### `json` API metadata files

Folder structure of saved PyPI project metadata when [](./mirror_configuration.md#json) is enabled:

```text
<mirror directory>/
├── web/
│   └── json/
│       ├── someproject
│       ├── anotherproject
│       └── ...
├── pypi/
│   ├── someproject/
│   │   └── json
│   ├── anotherproject/
│   │   └── json
│   └── ...
├── packages/
│   └── ...
└── simple/
    └── ...
```

The files `web/json/someproject` and `web/pypi/someproject/json` both contain the JSON metadata for a PyPI project with the normalized name "someproject".

(file-structure-hash-index)=

### `hash-index` index files

When [](./mirror_configuration.md#hash-index) is enabled, project index folders are grouped by the first letter of their name - for example:

```text
<mirror directory>/
└── web/
    └── simple/
        ├── b/
        │   ├── boto3/
        │   │   └── index.html
        │   └── botocore/
        │       └── index.html
        ├── c/
        │   ├── charset-normalizer/
        │   │   └── index.html
        │   ├── certifi/
        │   │   └── index.html
        │   └── cryptography/
        │       └── index.html
        ├── t/
        │   └── typing-extensions/
        │       └── index.html
        ├── ...
        └── index.html
```

The content of the index files themselves is unchanged.

## Default Configuration File

Bandersnatch loads default values from a configuration file inside the package. You can use this file as a reference or as the basis for your own configuration.

```{literalinclude} ../src/bandersnatch/default.conf
---
name: default.conf
language: ini
caption: Default configuration file from `src/bandersnatch/default.conf`
---
```

[filter-plugins]: ./filtering_configuration.md
[simple-repository-api]: https://packaging.python.org/en/latest/specifications/simple-repository-api/
[storage-backends]: ./storage_options.md

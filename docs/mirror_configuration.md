# Mirror Configuration

The **\[mirror\]** section of the configuration file contains general options for how Bandersnatch should operate. This includes settings like the source repository to mirror, how to store mirrored files, and the kinds of files to include in the mirror.

The following options are currently _required_:

- [](#directory)
- [](#master)
- [](#workers)
- [](#timeout)
- [](#global-timeout)
- [](#stop-on-error)
- [](#hash-index)

## Examples

These examples only show `[mirror]` options; a complete configuration may include [mirror filtering plugins][filter-plugins] and/or options for a [storage backend][storage-backends].

### Minmal

A basic configuration with reasonable defaults for the required options:

```ini
[mirror]
; base destination path for mirrored files
directory = /srv/pypi

; upstream package repository to mirror
master = https://pypi.org

; parallel downloads - keep low to avoid overwhelming upstream
workers = 3

; per-request time limit
timeout = 15

; global time limit - applied to aiohttp coroutines
global-timeout = 18000

; continue syncing when an error occurs
stop-on-error = false

; use PyPI-compatible folder structure for index files
hash-index = false
```

This will mirror index files and package release files from PyPI and store the mirror in `/srv/pypi`. Add configuration for [mirror filtering plugins][filter-plugins] to optionally filter what packages are mirrored in a variety of ways.

### Alternative Download Source

It is possible to download metadata from one repository, but package release files from another:

```ini
[mirror]
directory = /srv/pypi
; Project and package metadata received from this repository
master = https://pypi.org
; Package distribution artifacts downloaded from here if possible
download-mirror = https://pypi-mirror.example.com/

; required options from basic config
workers = 3
timeout = 15
global-timeout = 18000
stop-on-error = false
hash-index = false
```

This will download release files from `https://pypi-mirror.example.com` if possible and fall back to PyPI if a download fails. See [](#download-mirror). Add [](#download-mirror-no-fallback) to download release files exclusively from `download-mirror`.

### Index Files Only

It is possible to mirror just index files without downloading any package release files:

```ini
[mirror]
directory = /srv/pypi-filtered
master = https://pypi.org
simple-format = ALL
release-files = false
root_uri = https://files.pythonhosted.org/

; required options from basic config
workers = 3
timeout = 15
global-timeout = 18000
stop-on-error = false
hash-index = false
```

This will mirror index files for projects and versions allowed by your [mirror filters][filter-plugins], but will not download any package release files. File URLs in index files will use the configured `root_uri`. See [](#release-files) and [](#root_uri).

## Option Reference

%
% mirror output / file structure related
%

### `directory`

The directory where mirrored files are stored. _This option is always required._

:Type: folder path
:Required: **yes**

The exact interpretation of this value depends on the configured [storage backend](#storage-backend). For the default [filesystem](./storage_options.md#filesystem-support) backend, the directory used should meet the following requirements:

- The filesystem must be case-sensitive.
- The filesystem must support large numbers of sub-directories.
- The filesystem must support large numbers of files (inodes)

### `storage-backend`

The [storage backend][storage-backends] used to save data and metadata when mirroring packages.

:Type: string
:Required: no
:Default: `filesystem`

```{seealso}
Available storage backends are documented at [][storage-backends].
```

### `simple-format`

The [Simple Repository API][simple-repository-api] index file formats to generate.

:Type: one of `HTML`, `JSON`, or `ALL`
:Required: no
:Default: `ALL`

[PEP 691 – JSON-based Simple API for Python Package Indexes](https://peps.python.org/pep-0691/) extended the Simple Repository API to support both HTML and JSON. Bandersnatch generates project index files in both formats by default. Set this option to restrict index files to a single data format.

[](#simple-format-index-files) describes the generated folder structure and file names.

### `release-files`

Mirror package release files. Release files are the uploaded sdist and wheel files for mirrored projects.

:Type: boolean
:Required: no
:Default: true

Disabling this will mirror repository [index files](#simple-format) and/or [project metadata](#json) without downloading any associated package files. [](#release-files-folder-structure) describes the folder structure for mirrored package release files.

```{note}
If `release-files = false`, you should also specify the [](#root_uri) option.
```

### `json`

Save copies of JSON project metadata downloaded from PyPI.

:Type: boolean
:Required: no
:Default: false

When enabled, this saves copies of all JSON project metadata downloaded from [PyPI's JSON API](https://warehouse.pypa.io/api-reference/json.html). These files are used by the <project:#bandersnatch-verify> subcommand.

[](#json-api-metadata-files) describes the folder structure generated by this option. The format of the saved JSON is not standardized and is specific to [Warehouse](https://warehouse.pypa.io/).

```{note}
This option does _not_ effect the generation of simple repository API index files in JSON format ([](#simple-format)).
```

### `root_uri`

A base URL to generate absolute URLs for package release files.

:Type: URL
:Required: no
:Default: `https://files.pythonhosted.org/`

Bandersnatch creates index files containing relative URLs by default. Setting this option generates index files with absolute URLs instead.

If [](#release-files) is disabled _and_ this option is unset, Bandersnatch uses a default value of `https://files.pythonhosted.org/`.

```{note}
This is generally not necessary, but was added for the official internal PyPI mirror, which requires serving packages from `<https://files.pythonhosted.org>`.
```

### `diff-file`

File location to write a list of all new or changed files during a mirror operation.

:Type: file or folder path
:Required: no
:Default: `<mirror directory>/mirrored-files`

Bandersnatch creates a plain-text file at the specified location containing a list of all files created or updated during the last mirror/sync operation. The files are listed as absolute paths separated by blank lines.

This is useful when mirroring to an offline network where it is required to only transfer new files to the downstream mirror. The diff file can be used to copy new files to an external drive, sync the list of files to an SSH destination such as a diode, or send the files through some other mechanism to an offline system.

If the specified path is a directory, Bandersnatch will use the file name "`mirrored-files`" within that directory.

The file will be overwritten on each mirror operation unless [](#diff-append-epoch) is enabled.

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

Append the current epoch time to the file name for [](#diff-file).

:Type: boolean
:Required: no
:Default: false

For example, the configuration:

```ini
[mirror]
; ...
diff-file = /srv/pypi/new-files
diff-append-epoch = true
```

Will generate diff files with names like `/srv/pypi/new-files-1568129735`. This can be used to track diffs over time by creating a new diff file each time Bandersnatch runs.

### `hash-index`

Group generated project index folders by the first letter of their normalized project name.

:Type: boolean
:Required: **yes**

Enabling this changes the way generated index files are organized. Project folders are grouped into subfolders alphabetically as shown here: [](#hash-index-index-files). This has the effect of splitting up a large `/web/simple` directory into smaller subfolders, each containing a subset of the index files. This can improve file system efficiency when mirroring a very large number of projects, but requires a web server capable of translating Simple Repository API URLs into file paths.

```{warning}
It is recommended to set this to `false` for full pip/pypi compatibility.

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
:Required: **yes**

Bandersnatch requests metadata for projects and packages from this repository server, and downloads package release files from the URLs specified in the received metadata.

To mirror packages from PyPI, set this to `https://pypi.org`.

The URL _must_ use the `https:` protocol.

```{seealso}
Bandersnatch can download package release files from an alternative source by configuring a [](#download-mirror).
```

### `proxy`

Use an HTTP proxy server.

:Type: URL
:Required: no
:Default: none

The proxy server is used when sending requests to a repository server set by the [](#master) or [](#download-mirror) option.

```{seealso}
HTTP proxies are supported through the `aiohttp` library. See the aiohttp manual for details on what connection types are supported: <https://docs.aiohttp.org/en/stable/client_advanced.html#proxy-support>
```

```{note}
Alternatively, you can specify a proxy URL by setting one of the environment variables `HTTPS_PROXY`, `HTTP_PROXY`, or `ALL_PROXY`. _This method supports both HTTP and SOCKS proxies._ Support for `socks4`/`socks5` uses the [aiohttp-socks](https://github.com/romis2012/aiohttp-socks) library.

SOCKS proxies are not currently supported via the `mirror.proxy` config option.
```

### `timeout`

The network request timeout to use for all connections, in seconds. This is the maximum allowed time for individual web requests.

:Type: number, in seconds
:Required: **yes**

```{note}
It is recommended to set this to a relatively low value, e.g. 10 - 30 seconds. This is so temporary problems will fail quickly and allow retrying, instead of having a process hang infinitely and leave TCP unable to catch up for a long time.
```

### `global-timeout`

The maximum runtime of individual aiohttp coroutines, in seconds.

:Type: number, in seconds
:Required: **yes**

```{note}
It is recommended to set this to a relatively high value, e.g. 3,600 - 18,000 (1 - 5 hours). This supports coroutines mirroring large package files on slow connections.
```

### `download-mirror`

Download package release files from an alternative repository server.

:Type: URL
:Required: no
:Default: none

By default, Bandersnatch downloads packages from the URL supplied in the master server's JSON response. Setting this option to a repository URL will try to download release files from that repository first, and fallback to the URL supplied by the master server if that is unsuccessful (unable to get content or checksum mismatch).

This is useful to sync most of the files from an existing, nearby mirror - for example, when creating a new mirror identical to an existing one for the purpose of load sharing.

### `download-mirror-no-fallback`

Disable the fallback behavior for [](#download-mirror).

:Type: boolean
:Required: no
:Default: false

When set to `true`, Bandersnatch only downloads package distribution artifacts from the repository set in [](#download-mirror) and ignores file URLs received from the [](#master) server.

```{warning}
This could lead to more failures than expected and is not recommended for most scenarios.
```

%
% processing and miscellaneous options
%

### `cleanup`

Enable cleanup of legacy simple directories with non-normalized names.

:Type: boolean
:Required: no
:Default: false

Bandersnatch versions prior to 4.0 used directories with non-normalized package names for compatability with older versions of pip. Enabling this option checks for and removes these directories.

```{seealso}
[Python Packaging User Guide - Names and Normalization](https://packaging.python.org/en/latest/specifications/name-normalization/)
```

### `workers`

The number of worker threads used for parallel downloads.

:Type: number, 1 ≤ N ≤ 10
:Required: **yes**

Use **1 - 3** workers to avoid overloading the PyPI master (and maybe your own internet connection). If you see timeouts and have a slow connection, try lowering this setting.

Official servers located in data centers could feasibly run up to 10 workers. Anything beyond 10 is considered unreasonable.

### `verifiers`

The number of concurrent consumers used for verifying metadata.

:Type: number
:Required: no
:Default: 3

```{seealso}
This option is used by the <project:#bandersnatch-verify> subcommand.
```

### `stop-on-error`

Stop mirror/sync operations immediately when an error occurs.

:Type: boolean
:Required: **yes**

When disabled (`stop-on-error = false`), Bandersnatch continues syncing after an error occurs, but will mark the sync as unsuccessful. When enabled, Bandersnatch will stop all syncing as soon as possible if an error occurs. This can be helpful when debugging the cause of an unsuccessful sync.

### `compare-method`

The method used to compare existing files with upstream files.

:Type: one of `hash`, `stat`
:Required: no
:Default: `hash`

- `hash`: compare by creating a checksums of a local file content. This is slower than `stat`, but more reliable. The hash algorithm is specified by [](#digest_name).
- `stat`: compare by using file size and change time. This can reduce IO workload when frequently verifying a large number of files.

### `digest_name`

The algorithm used to compute file hashes when [](#compare-method) is set to `hash`.

:Type: one of `sha256`, `md5`
:Default: `sha256`

### `keep_index_versions`

Store previous versions of generated index files.

:Type: number
:Required: no
:Default: 0 (do not keep previous index versions)

This can be used as a safeguard against upstream changes generating blank index.html files.

By default or when set to 0, no prior versions are stored and `index.html` is the latest version.

When enabled by setting a value > 0, Bandersnatch stores the most recently generated versions of each index file, up to the configured number of versions. Prior versions are stored under `versions/index_<serial>_<timestamp>.html` and the current `index.html` is a symlink to the latest version.

### `log-config`

Provide a custom logging configuration file.

:type: file path
:Required: no
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

### `simple-format` index files

Folder structure of generated index files for [](#simple-format):

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

### `json` API metadata files

Folder structure of saved PyPI project metadata when [](#json) is enabled:

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

### `hash-index` index files

When [](#hash-index) is enabled, project index folders are grouped by the first letter of their name - for example:

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

import os.path
import unittest.mock as mock
from datetime import datetime
from os import sep
from pathlib import Path
from typing import List

from freezegun import freeze_time
from requests import HTTPError

from bandersnatch.package import Package


def touch_files(paths: List[Path]):
    for path in paths:
        if not path.parent.exists():
            path.parent.mkdir(parents=True)
        with path.open("wb") as pfp:
            pfp.close()


def test_package_sync_404_json_info_keeps_package_on_non_deleting_mirror(
    mirror, requests
):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = {}

    response = mock.Mock()
    response.status_code = 404
    requests.prepare(HTTPError(response=response), 0)

    paths = [Path("web/packages/2.4/f/foo/foo.zip"), Path("web/simple/foo/index.html")]
    touch_files(paths)

    package = Package("foo", 10, mirror)
    package.sync()

    for path in paths:
        assert path.exists()


def test_package_sync_gives_up_after_3_stale_responses(caplog, mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ["0.1"]
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []

    requests.prepare(b"the simple page", "10")
    requests.prepare(b"the simple page", "10")
    requests.prepare(b"the simple page", "10")
    requests.prepare(b"the simple page", "10")

    package = Package("foo", 11, mirror)
    package.sleep_on_stale = 0

    package.sync()
    assert package.tries == 3
    assert mirror.errors
    assert "not updating. Giving up" in caplog.text


def test_package_sync_with_release_no_files_syncs_simple_page(mirror, requests):

    requests.prepare(
        {"info": {"name": "foo"}, "last_serial": 654_321, "releases": {}}, "10"
    )

    mirror.packages_to_sync = {"foo": 10}
    package = Package("foo", 10, mirror)
    package.sync()

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_with_release_no_files_syncs_simple_page_with_hash(
    mirror_hash_index, requests
):

    requests.prepare(
        {"info": {"name": "foo"}, "last_serial": 654_321, "releases": {}}, "10"
    )

    mirror_hash_index.packages_to_sync = {"foo": 10}
    package = Package("foo", 10, mirror_hash_index)
    package.sync()

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_with_canonical_simple_page(mirror, requests):

    requests.prepare(
        {"info": {"name": "foo"}, "last_serial": 654_321, "releases": {}}, "10"
    )

    mirror.packages_to_sync = {"Foo": 10}
    package = Package("Foo", 10, mirror)
    package.sync()

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for Foo</title>
  </head>
  <body>
    <h1>Links for Foo</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_with_canonical_simple_page_with_hash(mirror_hash_index, requests):

    requests.prepare(
        {"info": {"name": "foo"}, "last_serial": 654_321, "releases": {}}, "10"
    )
    mirror_hash_index.packages_to_sync = {"Foo": 10}
    package = Package("Foo", 10, mirror_hash_index)
    package.sync()

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for Foo</title>
  </head>
  <body>
    <h1>Links for Foo</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_with_normalized_simple_page(mirror, requests):

    requests.prepare(
        {"info": {"name": "foo"}, "last_serial": 654_321, "releases": {}}, "10"
    )

    mirror.packages_to_sync = {"Foo.bar-thing_other": 10}
    package = Package("Foo.bar-thing_other", 10, mirror)
    package.sync()

    # PEP 503 normalization
    assert (
        open("web/simple/foo-bar-thing-other/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for Foo.bar-thing_other</title>
  </head>
  <body>
    <h1>Links for Foo.bar-thing_other</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )

    # Legacy partial normalization as implemented by pip prior to 8.1.2
    assert (
        open("web/simple/foo.bar-thing-other/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for Foo.bar-thing_other</title>
  </head>
  <body>
    <h1>Links for Foo.bar-thing_other</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )

    # Legacy unnormalized as implemented by pip prior to 6.0
    assert (
        open("web/simple/Foo.bar-thing_other/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for Foo.bar-thing_other</title>
  </head>
  <body>
    <h1>Links for Foo.bar-thing_other</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_simple_page_root_uri(mirror, requests):
    requests.prepare(
        {
            "info": {"name": "foo", "version": "0.1"},
            "last_serial": 654_321,
            "releases": {
                "0.1": [
                    {
                        "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                        "filename": "foo.zip",
                        "digests": {
                            "md5": "6bd3ddc295176f4dca196b5eb2c4d858",
                            "sha256": (
                                "02db45ea4e09715fbb1ed0fef30d7324db07c"
                                "9e87fb0d4e5470a3e4e878bd8cd"
                            ),
                        },
                        "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                    },
                    {
                        "url": "https://pypi.example.com/packages/2.7/f/foo/foo.whl",
                        "filename": "foo.whl",
                        "digests": {
                            "md5": "6bd3ddc295176f4dca196b5eb2c4d858",
                            "sha256": (
                                "678d78c1ad57455e848081723f7a7a9ff6cdd"
                                "859b46e9540f574f0a65eb04b0d"
                            ),
                        },
                        "md5_digest": "6bd3ddc295176f4dca196b5eb2c4d858",
                    },
                ]
            },
        },
        10,
    )
    requests.prepare(b"the release content", 10)
    requests.prepare(b"another release content", 10)

    mirror.packages_to_sync = {"foo": 10}
    mirror.root_uri = "https://files.pythonhosted.org"
    package = Package("foo", 10, mirror)
    package.sync()
    mirror.root_uri = None

    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>
    <a href="https://files.pythonhosted.org/packages/2.7/f/foo/foo.whl#sha256=\
678d78c1ad57455e848081723f7a7a9ff6cdd859b46e9540f574f0a65eb04b0d\
">foo.whl</a><br/>
    <a href="https://files.pythonhosted.org/packages/any/f/foo/foo.zip#sha256=\
02db45ea4e09715fbb1ed0fef30d7324db07c9e87fb0d4e5470a3e4e878bd8cd\
">foo.zip</a><br/>
  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_simple_page_with_files(mirror, requests):
    requests.prepare(
        {
            "info": {"name": "foo", "version": "0.1"},
            "last_serial": 654_321,
            "releases": {
                "0.1": [
                    {
                        "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                        "digests": {
                            "md5": "6bd3ddc295176f4dca196b5eb2c4d858",
                            "sha256": (
                                "02db45ea4e09715fbb1ed0fef30d7324db07c"
                                "9e87fb0d4e5470a3e4e878bd8cd"
                            ),
                        },
                        "filename": "foo.zip",
                        "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                    },
                    {
                        "url": "https://pypi.example.com/packages/2.7/f/foo/foo.whl",
                        "digests": {
                            "md5": "6bd3ddc295176f4dca196b5eb2c4d858",
                            "sha256": (
                                "678d78c1ad57455e848081723f7a7a9ff6cdd"
                                "859b46e9540f574f0a65eb04b0d"
                            ),
                        },
                        "filename": "foo.whl",
                        "md5_digest": "6bd3ddc295176f4dca196b5eb2c4d858",
                    },
                ]
            },
        },
        10,
    )
    requests.prepare(b"the release content", 10)
    requests.prepare(b"another release content", 10)

    mirror.packages_to_sync = {"foo": 10}
    package = Package("foo", 10, mirror)
    package.sync()

    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>
    <a href="../../packages/2.7/f/foo/foo.whl#sha256=\
678d78c1ad57455e848081723f7a7a9ff6cdd859b46e9540f574f0a65eb04b0d\
">foo.whl</a><br/>
    <a href="../../packages/any/f/foo/foo.zip#sha256=\
02db45ea4e09715fbb1ed0fef30d7324db07c9e87fb0d4e5470a3e4e878bd8cd\
">foo.zip</a><br/>
  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_simple_page_with_existing_dir(mirror, requests):
    requests.prepare(
        {
            "info": {"name": "foo", "version": "0.1"},
            "last_serial": 654_321,
            "releases": {"0.1": []},
        },
        "10",
    )

    mirror.packages_to_sync = {"foo": 10}
    package = Package("foo", 10, mirror)
    os.makedirs(package.simple_directory)
    package.sync()

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_simple_page_with_existing_dir_with_hash(
    mirror_hash_index, requests
):
    requests.prepare(
        {
            "info": {"name": "foo", "version": "0.1"},
            "last_serial": 654_321,
            "releases": {"0.1": []},
        },
        "10",
    )

    mirror_hash_index.packages_to_sync = {"foo": 10}
    package = Package("foo", 10, mirror_hash_index)
    os.makedirs(package.simple_directory)
    package.sync()

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )


def test_package_sync_with_error_keeps_it_on_todo_list(mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ["0.1"]
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []

    requests.side_effect = Exception

    mirror.packages_to_sync = {"foo"}
    package = Package("foo", 10, mirror)
    package.sync()
    assert "foo" in mirror.packages_to_sync


def test_package_sync_downloads_release_file(mirror, requests):
    requests.prepare(
        {
            "info": {"name": "foo", "version": "0.1"},
            "last_serial": 654_321,
            "releases": {
                "0.1": [
                    {
                        "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                        "filename": "foo.zip",
                        "digests": {
                            "md5": "b6bcb391b040c4468262706faf9d3cce",
                            "sha256": (
                                "02db45ea4e09715fbb1ed0fef30d7324db07c"
                                "9e87fb0d4e5470a3e4e878bd8cd"
                            ),
                        },
                        "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                    }
                ]
            },
        },
        10,
    )
    requests.prepare(b"the release content", 10)

    mirror.packages_to_sync = {"foo": None}
    package = Package("foo", 10, mirror)
    package.sync()

    assert open("web/packages/any/f/foo/foo.zip").read() == ("the release content")


def test_package_download_rejects_non_package_directory_links(mirror):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ["0.1"]
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {
            "url": "https://pypi.example.com/foo/bar/foo/foo.zip",
            "digests": {
                "md5": "b6bcb391b040c4468262706faf9d3cce",
                "sha256": (
                    "02db45ea4e09715fbb1ed0fef30d7324db07c"
                    "9e87fb0d4e5470a3e4e878bd8cd"
                ),
            },
            "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
        }
    ]

    mirror.packages_to_sync = {"foo"}
    package = Package("foo", 10, mirror)
    package.sync()
    assert mirror.errors
    assert "foo" in mirror.packages_to_sync
    assert not os.path.exists("web/foo/bar/foo/foo.zip")


def test_sync_keeps_superfluous_files_on_nondeleting_mirror(mirror, requests):
    test_files = [Path("web/packages/2.4/f/foo/foo.zip")]
    touch_files(test_files)

    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ["0.1"]
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []

    mirror.packages_to_sync = {"foo"}
    package = Package("foo", 10, mirror)
    package.sync()

    assert test_files[0].exists()


def test_package_sync_replaces_mismatching_local_files(mirror, requests):
    requests.prepare(
        {
            "info": {"name": "foo", "version": "0.1"},
            "last_serial": 654_321,
            "releases": {
                "0.1": [
                    {
                        "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                        "filename": "foo.zip",
                        "digests": {
                            "md5": "b6bcb391b040c4468262706faf9d3cce",
                            "sha256": (
                                "02db45ea4e09715fbb1ed0fef30d7324db07c"
                                "9e87fb0d4e5470a3e4e878bd8cd"
                            ),
                        },
                        "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                    }
                ]
            },
        },
        10,
    )
    requests.prepare(b"the release content", 10)

    test_files = [Path("web/packages/any/f/foo/foo.zip")]
    touch_files(test_files)
    with test_files[0].open("wb") as f:
        f.write(b"this is not the release content")

    mirror.packages_to_sync = {"foo": None}
    package = Package("foo", 10, mirror)
    package.sync()

    assert test_files[0].open("r").read() == ("the release content")


def test_package_sync_does_not_touch_existing_local_file(mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ["0.1"]
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {
            "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
            "digests": {
                "md5": "b6bcb391b040c4468262706faf9d3cce",
                "sha256": (
                    "02db45ea4e09715fbb1ed0fef30d7324db07c"
                    "9e87fb0d4e5470a3e4e878bd8cd"
                ),
            },
            "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
        }
    ]

    requests.prepare(b"the release content", 10)

    test_files = [Path("web/packages/any/f/foo/foo.zip")]
    touch_files(test_files)
    with test_files[0].open("wb") as f:
        f.write(b"the release content")
    old_stat = test_files[0].stat()

    mirror.packages_to_sync = {"foo"}
    package = Package("foo", 10, mirror)
    package.sync()

    assert old_stat == os.stat(test_files[0])


def test_gen_data_requires_python(mirror, requests):
    fake_no_release = {}
    fake_release = {"requires_python": ">=3.6"}
    package = Package("foo", 10, mirror)

    assert package.gen_data_requires_python(fake_no_release) == ""
    assert (
        package.gen_data_requires_python(fake_release)
        == ' data-requires-python="&gt;=3.6"'
    )


def test_sync_incorrect_download_with_current_serial_fails(mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ["0.1"]
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {
            "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
            "digests": {
                "md5": "b6bcb391b040c4468262706faf9d3cce",
                "sha256": (
                    "02db45ea4e09715fbb1ed0fef30d7324db07c"
                    "9e87fb0d4e5470a3e4e878bd8cd"
                ),
            },
            "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
        }
    ]

    requests.prepare(b"not release content", 10)

    mirror.packages_to_sync = {"foo"}
    package = Package("foo", 10, mirror)
    package.sync()

    assert not os.path.exists("web{0}packages{0}any{0}f{0}foo{0}foo.zip".format(sep))
    assert mirror.errors


def test_sync_incorrect_download_with_old_serials_retries(mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ["0.1"]
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {
            "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
            "digests": {
                "md5": "b6bcb391b040c4468262706faf9d3cce",
                "sha256": (
                    "02db45ea4e09715fbb1ed0fef30d7324db07c"
                    "9e87fb0d4e5470a3e4e878bd8cd"
                ),
            },
            "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
        }
    ]

    requests.prepare(b"not release content", 9)

    mirror.packages_to_sync = {"foo"}
    package = Package("foo", 10, mirror)
    package.sync()

    assert not os.path.exists("web{0}packages{0}any{0}f{0}foo{0}foo.zip".format(sep))
    assert mirror.errors


def test_sync_incorrect_download_with_new_serial_fails(mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ["0.1"]
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {
            "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
            "digests": {
                "md5": "b6bcb391b040c4468262706faf9d3cce",
                "sha256": (
                    "02db45ea4e09715fbb1ed0fef30d7324db07c"
                    "9e87fb0d4e5470a3e4e878bd8cd"
                ),
            },
            "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
        }
    ]

    requests.prepare(b"not release content", 11)

    mirror.packages_to_sync = {"foo"}
    package = Package("foo", 10, mirror)
    package.sync()

    assert not os.path.exists("web{0}packages{0}any{0}f{0}foo{0}foo.zip".format(sep))
    assert mirror.errors


def test_survives_exceptions_from_record_finished_package(mirror, requests):
    def record_finished_package(name):
        import errno

        raise IOError(errno.EBADF, "Some transient error?")

    requests.prepare(
        {"info": {"name": "foo"}, "last_serial": 654_321, "releases": {}}, "10"
    )

    mirror.packages_to_sync = {"Foo": 10}
    mirror.record_finished_package = record_finished_package

    package = Package("Foo", 10, mirror)
    package.sync()

    assert (
        open("web{0}simple{0}foo{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for Foo</title>
  </head>
  <body>
    <h1>Links for Foo</h1>

  </body>
</html>
<!--SERIAL 654321-->\
"""
    )
    assert mirror.errors


@freeze_time("2018-10-28")
def test_keep_index_versions_stores_one_prior_version(mirror, requests):
    requests.prepare(
        {
            "info": {"name": "foo", "version": "0.1"},
            "last_serial": 654_321,
            "releases": {
                "0.1": [
                    {
                        "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                        "filename": "foo.zip",
                        "digests": {
                            "md5": "b6bcb391b040c4468262706faf9d3cce",
                            "sha256": (
                                "02db45ea4e09715fbb1ed0fef30d7324db07c"
                                "9e87fb0d4e5470a3e4e878bd8cd"
                            ),
                        },
                        "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                    }
                ]
            },
        },
        10,
    )
    requests.prepare(b"the release content", 10)

    mirror.packages_to_sync = {"foo": None}
    mirror.keep_index_versions = 1
    package = Package("foo", 10, mirror)
    package.sync()

    simple_path = Path("web/simple/foo")
    versions_path = simple_path / "versions"
    version_files = os.listdir(versions_path)
    assert len(version_files) == 1
    assert (
        version_files[0]
        == f"index_{package.serial}_{datetime.utcnow().isoformat()}Z.html"
    )
    link_path = simple_path / "index.html"
    assert link_path.is_symlink()
    assert os.path.basename(os.readlink(link_path)) == version_files[0]


def test_keep_index_versions_stores_different_prior_versions(mirror, requests):
    response = {
        "info": {"name": "foo", "version": "0.1"},
        "last_serial": 654_321,
        "releases": {
            "0.1": [
                {
                    "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                    "filename": "foo.zip",
                    "digests": {
                        "md5": "b6bcb391b040c4468262706faf9d3cce",
                        "sha256": (
                            "02db45ea4e09715fbb1ed0fef30d7324db07c"
                            "9e87fb0d4e5470a3e4e878bd8cd"
                        ),
                    },
                    "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                }
            ]
        },
    }
    requests.prepare(response, 10)
    requests.prepare(b"the release content", 10)

    simple_path = Path("web/simple/foo")
    versions_path = simple_path / "versions"
    mirror.packages_to_sync = {"foo": None}
    mirror.keep_index_versions = 2
    with freeze_time("2018-10-27"):
        package = Package("foo", 10, mirror)
        package.sync()

    requests.prepare(response, 11)
    requests.prepare(b"the release content", 11)
    with freeze_time("2018-10-28"):
        package = Package("foo", 11, mirror)
        package.sync()

    version_files = sorted(os.listdir(versions_path))
    assert len(version_files) == 2
    assert version_files[0].startswith("index_10_2018-10-27")
    assert version_files[1].startswith("index_11_2018-10-28")
    link_path = simple_path / "index.html"
    assert os.path.islink(link_path)
    assert os.path.basename(os.readlink(link_path)) == version_files[1]


def test_keep_index_versions_removes_old_versions(mirror, requests):
    simple_path = Path("web/simple/foo/")
    versions_path = simple_path / "versions"
    versions_path.mkdir(parents=True)
    versions_path.joinpath("index_10_2018-10-26T00:00:00Z.html").touch()
    versions_path.joinpath("index_10_2018-10-27T00:00:00Z.html").touch()

    response = {
        "info": {"name": "foo", "version": "0.1"},
        "last_serial": 654_321,
        "releases": {
            "0.1": [
                {
                    "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                    "filename": "foo.zip",
                    "digests": {
                        "md5": "b6bcb391b040c4468262706faf9d3cce",
                        "sha256": (
                            "02db45ea4e09715fbb1ed0fef30d7324db07c"
                            "9e87fb0d4e5470a3e4e878bd8cd"
                        ),
                    },
                    "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                }
            ]
        },
    }
    requests.prepare(response, 11)
    requests.prepare(b"the release content", 11)

    mirror.keep_index_versions = 2
    with freeze_time("2018-10-28"):
        package = Package("foo", 11, mirror)
        package.sync()

    version_files = sorted(f for f in versions_path.iterdir())
    assert len(version_files) == 2
    assert version_files[0].name.startswith("index_10_2018-10-27")
    assert version_files[1].name.startswith("index_11_2018-10-28")
    link_path = simple_path / "index.html"
    assert link_path.is_symlink()
    assert os.path.basename(os.readlink(link_path)) == version_files[1].name

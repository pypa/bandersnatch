import os.path
import unittest.mock as mock
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from requests import HTTPError

from bandersnatch import utils
from bandersnatch.configuration import BandersnatchConfig, Singleton
from bandersnatch.filter import filter_project_plugins
from bandersnatch.mirror import Mirror


class JsonDict(dict):
    """ Class to fake the object returned from requests lib in master.get() """

    def json(self):
        return self

    def iter_content(*args, **kwargs):
        yield b"abcdefg69"


# master.get() returned data needs to have a .json() method and iter_content
FAKE_RELEASE_DATA = JsonDict(
    releases={
        "0.1": [
            {
                "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                "filename": "foo.zip",
                "digests": {
                    "md5": "ebdad75ed9a852bbfd9be4c18bf76d00",
                    "sha256": (
                        "746e6da7eda8b75af9acbdd29808473df08a00362981f0"
                        "949023e387da1a4734"
                    ),
                },
                "md5_digest": "ebdad75ed9a852bbfd9be4c18bf76d00",
            }
        ]
    }
)


def test_limit_workers():
    try:
        Mirror(None, None, workers=11)
    except ValueError:
        pass


def test_mirror_loads_serial(tmpdir):
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("5")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    m = Mirror(str(tmpdir), mock.Mock())
    assert m.synced_serial == 1234


def test_mirror_recovers_from_inconsistent_serial(tmpdir):
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    m = Mirror(str(tmpdir), mock.Mock())
    assert m.synced_serial == 0


def test_mirror_generation_3_resets_status_files(tmpdir):
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("2")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("asdf")

    m = Mirror(str(tmpdir), mock.Mock())
    assert m.synced_serial is 0
    assert not os.path.exists(str(tmpdir / "todo"))
    assert not os.path.exists(str(tmpdir / "status"))
    assert open(str(tmpdir / "generation"), "r").read() == "5"


def test_mirror_generation_4_resets_status_files(tmpdir):
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("4")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("asdf")

    m = Mirror(str(tmpdir), mock.Mock())
    assert m.synced_serial is 0
    assert not os.path.exists(str(tmpdir / "todo"))
    assert not os.path.exists(str(tmpdir / "status"))
    assert open(str(tmpdir / "generation"), "r").read() == "5"


def test_mirror_filter_packages_match(tmpdir):
    """
    Packages that exist in the blacklist should be removed from the list of
    packages to sync.
    """
    test_configuration = """\
[blacklist]
packages =
    example1
"""
    Singleton._instances = {}
    with open("test.conf", "w") as testconfig_handle:
        testconfig_handle.write(test_configuration)
    BandersnatchConfig("test.conf")
    for plugin in filter_project_plugins():
        plugin.initialize_plugin()
    m = Mirror(str(tmpdir), mock.Mock())
    m.packages_to_sync = {"example1": None, "example2": None}
    m._filter_packages()
    assert "example1" not in m.packages_to_sync.keys()


def test_mirror_filter_packages_nomatch_package_with_spec(tmpdir):
    """
    Package lines with a PEP440 spec on them should not be filtered from the
    list of packages.
    """
    test_configuration = """\
[blacklist]
packages =
    example3>2.0.0
"""
    Singleton._instances = {}
    with open("test.conf", "w") as testconfig_handle:
        testconfig_handle.write(test_configuration)
    BandersnatchConfig("test.conf")
    for plugin in filter_project_plugins():
        plugin.initialize_plugin()
    m = Mirror(str(tmpdir), mock.Mock())
    m.packages_to_sync = {"example1": None, "example3": None}
    m._filter_packages()
    assert "example3" in m.packages_to_sync.keys()


def test_mirror_removes_empty_todo_list(tmpdir):
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("3")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("")
    Mirror(str(tmpdir), mock.Mock())
    assert not os.path.exists(str(tmpdir / "todo"))


def test_mirror_removes_broken_todo_list(tmpdir):
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("3")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("foo")
    Mirror(str(tmpdir), mock.Mock())
    assert not os.path.exists(str(tmpdir / "todo"))


def test_mirror_removes_old_status_and_todo_inits_generation(tmpdir):
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("foo")
    Mirror(str(tmpdir), mock.Mock())
    assert not os.path.exists(str(tmpdir / "todo"))
    assert not os.path.exists(str(tmpdir / "status"))
    assert open(str(tmpdir / "generation")).read().strip() == "5"


def test_mirror_with_same_homedir_needs_lock(mirror, tmpdir):
    try:
        Mirror(mirror.homedir, mirror.master)
    except RuntimeError:
        pass
    Mirror(os.path.join(mirror.homedir + "/test"), mirror.master)


def test_mirror_empty_master_gets_index(mirror):
    mirror.master.all_packages = mock.Mock()
    mirror.master.all_packages.return_value = {}

    mirror.synchronize()

    assert """\
/last-modified
/local-stats
/local-stats/days
/packages
/simple
/simple/index.html""" == utils.find(
        mirror.webdir
    )
    assert (
        open("web/simple/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
  </body>
</html>"""
    )
    assert open("status").read() == "0"


def test_mirror_empty_resume_from_todo_list(mirror, requests):
    response = mock.Mock()
    response.status_code = 404
    requests.prepare(HTTPError(response=response), 10)

    with open("todo", "w") as todo:
        todo.write("20\nfoobar 10")

    mirror.synchronize()

    assert """\
/.lock
/generation
/status
/web
/web/last-modified
/web/local-stats
/web/local-stats/days
/web/packages
/web/simple
/web/simple/index.html""" == utils.find(
        mirror.homedir
    )
    assert (
        open("web/simple/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
  </body>
</html>"""
    )
    assert open("status").read() == "20"


def test_mirror_sync_package(mirror, requests):
    mirror.master.all_packages = mock.Mock()
    mirror.master.all_packages.return_value = {"foo": 1}
    mirror.json_save = True
    # Recall bootstrap so we have the json dirs
    mirror._bootstrap()

    requests.prepare(FAKE_RELEASE_DATA, 1)
    requests.prepare(b"the release content", 1)

    mirror.master.get = mock.Mock()
    mirror.master.get.return_value = FAKE_RELEASE_DATA
    mirror.synchronize()

    assert """\
/json/foo
/last-modified
/packages/any/f/foo/foo.zip
/pypi/foo/json
/simple/foo/index.html
/simple/index.html""" == utils.find(
        mirror.webdir, dirs=False
    )
    assert (
        open("web/simple/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )
    assert open("status", "rb").read() == b"1"


def test_mirror_sync_package_error_no_early_exit(mirror, requests):
    mirror.master.all_packages = mock.Mock()
    mirror.master.all_packages.return_value = {"foo": 1}

    requests.prepare(
        {
            "releases": {
                "0.1": [
                    {
                        "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                        "filename": "foo.zip",
                        "digests": {
                            "md5": "b6bcb391b040c4468262706faf9d3cce",
                            "sha256": (
                                "02db45ea4e09715fbb1ed0fef30d7324db07c9e87fb0d4"
                                "e5470a3e4e878bd8cd"
                            ),
                        },
                        "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                    }
                ]
            }
        },
        1,
    )

    requests.prepare(b"the release content", 1)

    mirror.errors = True
    changed_packages = mirror.synchronize()

    assert """\
/.lock
/generation
/todo
/web/packages/any/f/foo/foo.zip
/web/simple/foo/index.html
/web/simple/index.html""" == utils.find(
        mirror.homedir, dirs=False
    )
    assert (
        open("web/simple/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )

    assert open("todo").read() == "1\n"

    # Check the returned dict is accurate
    expected = {"foo": {"web/packages/any/f/foo/foo.zip"}}
    assert changed_packages == expected


def test_mirror_sync_package_error_early_exit(mirror, requests):
    mirror.master.all_packages = mock.Mock()
    mirror.master.all_packages.return_value = {"foo": 1}

    requests.prepare(
        {
            "releases": {
                "0.1": [
                    {
                        "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                        "filename": "foo.zip",
                        "digests": {
                            "md5": "b6bcb391b040c4468262706faf9d3cce",
                            "sha256": (
                                "02db45ea4e09715fbb1ed0fef30d7324db07c9e87fb0"
                                "d4e5470a3e4e878bd8cd"
                            ),
                        },
                        "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                    }
                ]
            }
        },
        1,
    )
    requests.prepare(b"the release content", 1)

    with open("web/simple/index.html", "wb") as index:
        index.write(b"old index")
    mirror.errors = True
    mirror.stop_on_error = True
    with pytest.raises(SystemExit):
        mirror.synchronize()

    assert """\
/.lock
/generation
/todo
/web/packages/any/f/foo/foo.zip
/web/simple/foo/index.html
/web/simple/index.html""" == utils.find(
        mirror.homedir, dirs=False
    )
    assert open("web/simple/index.html").read() == "old index"
    assert open("todo").read() == "1\n"


def test_mirror_sync_package_with_hash(mirror_hash_index, requests):
    mirror_hash_index.master.all_packages = mock.Mock()
    mirror_hash_index.master.all_packages.return_value = {"foo": 1}

    requests.prepare(
        {
            "releases": {
                "0.1": [
                    {
                        "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                        "filename": "foo.zip",
                        "digests": {
                            "md5": "b6bcb391b040c4468262706faf9d3cce",
                            "sha256": (
                                "02db45ea4e09715fbb1ed0fef30d7324db07c9e87fb0d"
                                "4e5470a3e4e878bd8cd"
                            ),
                        },
                        "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                    }
                ]
            }
        },
        1,
    )

    requests.prepare(b"the release content", 1)

    mirror_hash_index.synchronize()

    assert """\
/last-modified
/packages/any/f/foo/foo.zip
/simple/f/foo/index.html
/simple/index.html""" == utils.find(
        mirror_hash_index.webdir, dirs=False
    )
    assert (
        open("web/simple/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )
    assert open("status").read() == "1"


def test_mirror_serial_current_no_sync_of_packages_and_index_page(mirror, requests):

    mirror.master.changed_packages = mock.Mock()
    mirror.master.changed_packages.return_value = {}
    mirror.synced_serial = 1

    mirror.synchronize()

    assert """\
/last-modified""" == utils.find(
        mirror.webdir, dirs=False
    )


def test_find_package_indexes_in_dir_threaded(mirror):
    directories = (
        "web/simple/peerme",
        "web/simple/click",
        "web/simple/zebra",
        "web/simple/implicit",
        "web/simple/pyaib",
        "web/simple/setuptools",
    )
    with TemporaryDirectory() as td:
        # Create local mirror first so we '_bootstrap'
        local_mirror = Mirror(td, mirror.master, stop_on_error=True)
        # Create fake file system objects
        mirror_base = Path(td)
        for directory in directories:
            mirror_base.joinpath(directory).mkdir(parents=True, exist_ok=True)
        with mirror_base.joinpath("web/simple/index.html").open("w") as index:
            index.write("<html></html>")

        packages = local_mirror.find_package_indexes_in_dir(
            mirror_base.joinpath("web/simple").as_posix()
        )
        assert "index.html" not in packages  # This should never be in the list
        assert len(packages) == 6  # We expect 6 packages with 6 dirs created
        assert packages[0] == "click"  # Check sorted - click should be first

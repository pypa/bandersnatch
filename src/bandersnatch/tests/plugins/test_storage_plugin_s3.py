from datetime import datetime

from s3path import S3Path

from bandersnatch.tests.mock_config import mock_config
from bandersnatch_storage_plugins import s3


def test_rewrite(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    with backend.rewrite(f"/{s3_mock.bucket}/test") as fp:
        fp.write("testcontent\n")
    assert s3.S3Path("/test-bucket/test").read_text() == "testcontent\n"


def test_update_safe(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    with backend.update_safe(
        f"/{s3_mock.bucket}/todo", mode="w+", encoding="utf-8"
    ) as fp:
        fp.write("flask\n")
    assert s3.S3Path(f"/{s3_mock.bucket}/todo").read_text() == "flask\n"


def test_path_mkdir(s3_mock: S3Path) -> None:
    new_folder = s3.S3Path(f"/{s3_mock.bucket}/test_folder")
    assert not new_folder.is_dir()
    new_folder.mkdir()
    assert new_folder.is_dir()


def test_path_glob(s3_mock: S3Path) -> None:
    files = [
        "index.html",
        "s1/index.html",
        "s3/index.html",
        "s3/index.html",
        "s3/not.html",
    ]
    for f in files:
        s3.S3Path(f"/{s3_mock.bucket}/{f}").touch()

    glob_result = list(s3.S3Path(f"/{s3_mock.bucket}").glob("**/index.html"))
    assert s3.S3Path(f"/{s3_mock.bucket}/s1/index.html") in glob_result
    assert s3.S3Path(f"/{s3_mock.bucket}/s3/not.html") not in glob_result


def test_lock(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    s3lock = backend.get_lock(f"/{s3_mock.bucket}/.lock")
    with s3lock.acquire(timeout=30):
        assert s3lock.is_locked is True
    assert s3lock.is_locked is False


def test_compare_files(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    backend.write_file(f"/{s3_mock.bucket}/file1", "test")
    backend.write_file(f"/{s3_mock.bucket}/file2", "test")
    assert (
        backend.compare_files(f"/{s3_mock.bucket}/file1", f"/{s3_mock.bucket}/file2")
        is True
    )


def test_read_write_file(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    backend.write_file(f"/{s3_mock.bucket}/file1", "test")

    assert backend.read_file(f"/{s3_mock.bucket}/file1", text=True) == "test"


def test_delete_file(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    sample_file = backend.PATH_BACKEND(f"/{s3_mock.bucket}/file1")
    sample_file.touch()
    assert sample_file.exists() is True

    backend.delete_file(f"/{s3_mock.bucket}/file1")
    assert sample_file.exists() is False


def test_delete_path(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder1/file1").touch()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/file2").touch()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/file3").touch()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/subdir1/file4").touch()

    assert str(backend.walk(f"/{s3_mock.bucket}/")[0]) == f"/{s3_mock.bucket}/folder1"
    assert (
        str(backend.walk(f"/{s3_mock.bucket}/")[1])
        == f"/{s3_mock.bucket}/folder1/file1"
    )

    assert backend.find(f"/{s3_mock.bucket}/folder1") == "file1"
    assert backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder1/file1").exists() is True
    assert backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/file3").exists() is True
    assert (
        backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/subdir1/file4").exists()
        is True
    )

    assert backend.is_file(f"/{s3_mock.bucket}/folder1/file1")
    assert backend.is_file(f"/{s3_mock.bucket}/folder2/file3")
    assert not backend.is_file(f"/{s3_mock.bucket}/folder2")

    backend.delete(f"/{s3_mock.bucket}/folder2")

    assert backend.exists(f"/{s3_mock.bucket}/folder1/file1") is True
    assert backend.exists(f"/{s3_mock.bucket}/folder2/file2") is False
    assert backend.exists(f"/{s3_mock.bucket}/folder2/file3") is False
    assert backend.exists(f"/{s3_mock.bucket}/folder2/subdir1/file4") is False


def test_mkdir_rmdir(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    backend.mkdir(f"/{s3_mock.bucket}/test_folder")

    assert backend.is_dir(f"/{s3_mock.bucket}/test_folder")

    backend.rmdir(f"/{s3_mock.bucket}/test_folder")

    assert not backend.is_dir(f"/{s3_mock.bucket}/test_folder")


def test_scandir(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    backend.mkdir(f"/{s3_mock.bucket}/test_folder")
    backend.mkdir(f"/{s3_mock.bucket}/test_folder/sub_dir")
    backend.write_file(f"/{s3_mock.bucket}/test_folder/sub_file", "test")
    for ent in backend.scandir(f"/{s3_mock.bucket}/test_folder"):
        if ent.name == "sub_dir":
            assert ent.is_dir()
        elif ent.name == "sub_file":
            assert ent.is_file()
        # no symlink for S3
        else:
            raise ValueError(f"unexpected dir entry {str(ent.name)}")
    backend.delete(f"/{s3_mock.bucket}/test_folder")


def test_plugin_init(s3_mock: S3Path) -> None:
    config_loader = mock_config(
        """
[mirror]
directory = /tmp/pypi
json = true
master = https://pypi.org
timeout = 60
global-timeout = 18000
workers = 3
hash-index = true
stop-on-error = true
storage-backend = swift
verifiers = 3
keep_index_versions = 2
compare-method = hash
[s3]
region_name = us-east-1
aws_access_key_id = 123456
aws_secret_access_key = 123456
endpoint_url = http://localhost:9090
signature_version = s3v4
"""
    )
    backend = s3.S3Storage(config=config_loader.config)
    backend.initialize_plugin()

    path = s3.S3Path("/tmp/pypi")
    resource, _ = path._accessor.configuration_map.get_configuration(path)
    assert resource.meta.client.meta.endpoint_url == "http://localhost:9090"

    config_loader = mock_config(
        """
[mirror]
directory = /tmp/pypi
json = true
master = https://pypi.org
timeout = 60
global-timeout = 18000
workers = 3
hash-index = true
stop-on-error = true
storage-backend = swift
verifiers = 3
keep_index_versions = 2
compare-method = hash
[s3]
endpoint_url = http://localhost:9090
"""
    )
    backend = s3.S3Storage(config=config_loader.config)
    backend.initialize_plugin()

    path = s3.S3Path("/tmp/pypi")
    resource, _ = path._accessor.configuration_map.get_configuration(path)
    assert resource.meta.client.meta.endpoint_url == "http://localhost:9090"


def test_upload_time(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder1/file1").touch()

    assert backend.get_upload_time(f"/{s3_mock.bucket}/folder1/file1").second == 0
    assert backend.get_upload_time(f"/{s3_mock.bucket}/folder1/file1").year == 1970

    dt = datetime(2008, 8, 8, 10, 10, 0)
    backend.set_upload_time(f"/{s3_mock.bucket}/folder1/file1", dt)

    assert datetime.timestamp(
        backend.get_upload_time(f"/{s3_mock.bucket}/folder1/file1")
    ) == datetime.timestamp(dt)


def test_file_size(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    backend.write_file(f"/{s3_mock.bucket}/file1", b"1234")
    assert backend.get_file_size(f"/{s3_mock.bucket}/file1") == 4


def test_copy_file(s3_mock: S3Path) -> None:
    backend = s3.S3Storage()
    backend.write_file(f"/{s3_mock.bucket}/file1", b"1234")

    backend.copy_file(f"/{s3_mock.bucket}/file1", f"/{s3_mock.bucket}/file2")
    assert backend.read_file(f"/{s3_mock.bucket}/file2") == "1234"

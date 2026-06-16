from datetime import datetime

import pytest
from s3path import S3Path, configuration_map

from bandersnatch.tests.mock_config import mock_config
from bandersnatch_storage_plugins import s3

pytestmark = pytest.mark.s3


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
    new_folder2 = s3.S3Path(f"/{s3_mock.bucket}/test_folder")
    assert new_folder2.is_dir()


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
    for ent in S3Path(f"/{s3_mock.bucket}/test_folder").iterdir():
        if ent.name == "sub_dir":
            assert ent.is_dir()
        elif ent.name == "sub_file":
            assert ent.is_file()
        # we now make .s3keep files to pass params so is expected
        elif ent.name == ".s3keep":
            continue
        # no symlink for S3
        else:
            raise ValueError(f"unexpected dir entry {str(ent.name)}")
    backend.delete(f"/{s3_mock.bucket}/test_folder")


def test_plugin_init(s3_mock: S3Path) -> None:
    config = mock_config("""
[mirror]
directory = /tmp/pypi
json = true
master = https://pypi.org
timeout = 60
global-timeout = 18000
workers = 3
hash-index = true
stop-on-error = true
storage-backend = s3
verifiers = 3
keep_index_versions = 2
compare-method = hash
[s3]
region_name = us-east-1
aws_access_key_id = 123456
aws_secret_access_key = 123456
endpoint_url = http://localhost:9090
signature_version = s3v4
""")
    backend = s3.S3Storage(config=config)
    backend.initialize_plugin()

    path = s3.S3Path("/tmp/pypi")
    resource, _ = configuration_map.get_configuration(path)
    assert resource.meta.client.meta.endpoint_url == "http://localhost:9090"

    config = mock_config("""
[mirror]
directory = /tmp/pypi
json = true
master = https://pypi.org
timeout = 60
global-timeout = 18000
workers = 3
hash-index = true
stop-on-error = true
storage-backend = s3
verifiers = 3
keep_index_versions = 2
compare-method = hash
[s3]
endpoint_url = http://localhost:9090
""")
    backend = s3.S3Storage(config=config)
    backend.initialize_plugin()

    path = s3.S3Path("/tmp/pypi")
    resource, _ = configuration_map.get_configuration(path)
    assert resource.meta.client.meta.endpoint_url == "http://localhost:9090"


def test_plugin_init_pool_matches_verify_concurrency(s3_mock: S3Path) -> None:
    """The boto3 client's HTTP connection pool must be sized to at least
    verify_concurrency, otherwise the dedicated verify thread pool would block
    on botocore's default 10-connection pool and the flag would be a no-op."""
    config = mock_config("""
[mirror]
directory = /tmp/pypi
master = https://pypi.org
storage-backend = s3
workers = 3
[s3]
region_name = us-east-1
aws_access_key_id = 123456
aws_secret_access_key = 123456
endpoint_url = http://localhost:9090
verify_concurrency = 64
""")
    backend = s3.S3Storage(config=config)
    backend.initialize_plugin()

    path = s3.S3Path("/tmp/pypi")
    resource, _ = configuration_map.get_configuration(path)
    assert resource.meta.client.meta.config.max_pool_connections == 64


def test_plugin_init_pool_floor_is_10(s3_mock: S3Path) -> None:
    """A tiny verify_concurrency must not shrink the pool below boto3's
    default of 10 (which other operations rely on)."""
    config = mock_config("""
[mirror]
directory = /tmp/pypi
master = https://pypi.org
storage-backend = s3
workers = 3
[s3]
region_name = us-east-1
aws_access_key_id = 123456
aws_secret_access_key = 123456
endpoint_url = http://localhost:9090
verify_concurrency = 2
""")
    backend = s3.S3Storage(config=config)
    backend.initialize_plugin()

    path = s3.S3Path("/tmp/pypi")
    resource, _ = configuration_map.get_configuration(path)
    assert resource.meta.client.meta.config.max_pool_connections == 10


def test_plugin_init_with_boto3_configs(s3_mock: S3Path) -> None:
    config = mock_config("""
[mirror]
directory = /tmp/pypi
json = true
master = https://pypi.org
timeout = 60
global-timeout = 18000
workers = 3
hash-index = true
stop-on-error = true
storage-backend = s3
verifiers = 3
keep_index_versions = 2
compare-method = hash
[s3]
region_name = us-east-1
aws_access_key_id = 123456
aws_secret_access_key = 123456
endpoint_url = http://localhost:9090
signature_version = s3v4
config_param_ServerSideEncryption = AES256
""")
    backend = s3.S3Storage(config=config)
    backend.initialize_plugin()

    assert backend.configuration_parameters["ServerSideEncryption"] == "AES256"

    # Verify that write with SSE AES256 succeeds and data is readable
    backend.write_file(f"/{s3_mock.bucket}/sse_test_file", "test")
    assert backend.read_file(f"/{s3_mock.bucket}/sse_test_file") == "test"


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


def test_set_and_get_hash(s3_mock: S3Path) -> None:
    """set_hash stores the digest in object metadata; get_hash reads it without
    downloading the full object (fast path)."""
    backend = s3.S3Storage()
    path = f"/{s3_mock.bucket}/pkgs/pkg-1.0.whl"
    backend.write_file(path, b"wheel content")

    # Before set_hash the fast path finds nothing and falls back to full read.
    expected = __import__("hashlib").sha256(b"wheel content").hexdigest()
    assert backend.get_hash(path) == expected

    # After set_hash the stored value is returned directly.
    backend.set_hash(path, "cafebabe" * 8)
    assert backend.get_hash(path) == "cafebabe" * 8


def test_iter_package_files(s3_mock: S3Path) -> None:
    """iter_package_files lists package files and excludes .s3keep entries."""
    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    files = [
        f"/{bucket}/web/packages/aa/bb/pkg-1.0.whl",
        f"/{bucket}/web/packages/aa/bb/pkg-2.0.whl",
    ]
    for f in files:
        backend.write_file(f, b"data")
    # mkdir creates a .s3keep file — it must NOT appear in results
    backend.mkdir(f"/{bucket}/web/packages/aa/cc")

    packages_path = s3.S3Path(f"/{bucket}/web/packages")
    found = {str(p) for p in backend.iter_package_files(packages_path)}
    assert {str(s3.S3Path(f)) for f in files} == found


@pytest.mark.asyncio
async def test_verify_files_s3_missing(s3_mock: S3Path) -> None:
    """verify_files yields the spec when the object does not exist."""
    import datetime

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    spec = FileSpec(
        path=s3.S3Path(f"/{bucket}/web/packages/aa/bb/missing.whl"),
        url="https://example.com/missing.whl",
        filename="missing.whl",
        size=100,
        digests={"sha256": "abc123"},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in backend.verify_files([spec])]
    assert bad == [spec]


@pytest.mark.asyncio
async def test_verify_files_s3_valid_with_metadata(s3_mock: S3Path) -> None:
    """verify_files does not yield a spec when stored sha256 metadata matches."""
    import datetime
    import hashlib

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/pkg-1.0.whl"
    backend.write_file(path, content)
    sha = hashlib.sha256(content).hexdigest()
    backend.set_hash(path, sha)

    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/pkg-1.0.whl",
        filename="pkg-1.0.whl",
        size=len(content),
        digests={"sha256": sha},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in backend.verify_files([spec])]
    assert bad == []


@pytest.mark.asyncio
async def test_verify_files_s3_corrupt_hash(s3_mock: S3Path) -> None:
    """verify_files yields the spec when stored sha256 metadata mismatches."""
    import datetime

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/pkg-1.0.whl"
    backend.write_file(path, content)
    backend.set_hash(path, "wrong" * 12 + "0000")

    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/pkg-1.0.whl",
        filename="pkg-1.0.whl",
        size=len(content),
        digests={"sha256": "correct" * 8 + "0000"},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in backend.verify_files([spec])]
    assert bad == [spec]


@pytest.mark.asyncio
async def test_verify_files_s3_legacy_valid(s3_mock: S3Path) -> None:
    """A pre-existing object with no stored hash metadata is verified by
    reading and hashing its content (the legacy, one-time GetObject path)."""
    import datetime
    import hashlib

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"legacy wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/legacy-1.0.whl"
    # write_file does not stamp sha256 metadata -> simulates a legacy object
    backend.write_file(path, content)
    sha = hashlib.sha256(content).hexdigest()

    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/legacy-1.0.whl",
        filename="legacy-1.0.whl",
        size=len(content),
        digests={"sha256": sha},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in backend.verify_files([spec])]
    assert bad == []


@pytest.mark.asyncio
async def test_verify_files_s3_legacy_corrupt(s3_mock: S3Path) -> None:
    """A legacy object whose content does not match the expected digest is
    flagged even when its size matches, proving the content hash (not just the
    size pre-filter) is what catches it."""
    import datetime

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"legacy wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/legacy-1.0.whl"
    backend.write_file(path, content)

    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/legacy-1.0.whl",
        filename="legacy-1.0.whl",
        size=len(content),  # size matches, so only the content hash can flag it
        digests={"sha256": "deadbeef" * 8},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in backend.verify_files([spec])]
    assert bad == [spec]


@pytest.mark.asyncio
async def test_verify_files_s3_legacy_backfills_hash(s3_mock: S3Path) -> None:
    """Hashing a valid legacy object back-fills its sha256 metadata so the next
    run is HEAD-only ("one-time after upgrade")."""
    import datetime
    import hashlib

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"legacy wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/legacy-1.0.whl"
    backend.write_file(path, content)  # no sha256 metadata
    sha = hashlib.sha256(content).hexdigest()

    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/legacy-1.0.whl",
        filename="legacy-1.0.whl",
        size=len(content),
        digests={"sha256": sha},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )

    # Sanity: metadata absent before verify.
    resource, _ = configuration_map.get_configuration(s3.S3Path(path))
    obj = resource.Object(bucket, "web/packages/aa/bb/legacy-1.0.whl")
    obj.load()
    assert "sha256" not in obj.metadata

    bad = [s async for s in backend.verify_files([spec])]
    assert bad == []

    # After a (non-dry-run) verify, the hash is stamped on the object.
    obj = resource.Object(bucket, "web/packages/aa/bb/legacy-1.0.whl")
    obj.load()
    assert obj.metadata.get("sha256") == sha


@pytest.mark.asyncio
async def test_verify_files_s3_dry_run_does_not_backfill(s3_mock: S3Path) -> None:
    """Dry-run detection must not mutate the backend: no metadata back-fill."""
    import datetime
    import hashlib

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"legacy wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/legacy-1.0.whl"
    backend.write_file(path, content)
    sha = hashlib.sha256(content).hexdigest()

    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/legacy-1.0.whl",
        filename="legacy-1.0.whl",
        size=len(content),
        digests={"sha256": sha},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )

    bad = [s async for s in backend.verify_files([spec], dry_run=True)]
    assert bad == []

    resource, _ = configuration_map.get_configuration(s3.S3Path(path))
    obj = resource.Object(bucket, "web/packages/aa/bb/legacy-1.0.whl")
    obj.load()
    assert "sha256" not in obj.metadata


@pytest.mark.asyncio
async def test_verify_files_s3_stat_mode_trusts_upload_time(s3_mock: S3Path) -> None:
    """In compare-method=stat, a matching upload time certifies the file with no
    content read — even a deliberately wrong expected hash is not consulted."""
    import configparser
    import datetime

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    # Drive compare-method without touching the global config singleton.
    cfg = configparser.ConfigParser()
    cfg.read_dict({"mirror": {"compare-method": "stat"}})
    backend.configuration = cfg

    bucket = s3_mock.bucket
    content = b"some wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/pkg-1.0.whl"
    backend.write_file(path, content)
    upload_time = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
    backend.set_upload_time(path, upload_time)

    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/pkg-1.0.whl",
        filename="pkg-1.0.whl",
        size=len(content),
        digests={"sha256": "deadbeef" * 8},  # wrong on purpose; stat must skip it
        upload_time=upload_time,
    )
    bad = [s async for s in backend.verify_files([spec])]
    assert bad == []


@pytest.mark.asyncio
async def test_verify_files_s3_stat_mode_mismatch_falls_through(
    s3_mock: S3Path,
) -> None:
    """In stat mode a non-matching upload_time immediately flags the file —
    there is no hash fallthrough; the corrupt digest is never consulted."""
    import configparser
    import datetime

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    cfg = configparser.ConfigParser()
    cfg.read_dict({"mirror": {"compare-method": "stat"}})
    backend.configuration = cfg

    bucket = s3_mock.bucket
    content = b"some wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/pkg-1.0.whl"
    backend.write_file(path, content)
    backend.set_upload_time(path, datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC))

    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/pkg-1.0.whl",
        filename="pkg-1.0.whl",
        size=len(content),
        digests={"sha256": "deadbeef" * 8},
        # upload_time differs from what's stored -> stat mismatch → flagged bad
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in backend.verify_files([spec])]
    assert bad == [spec]


def test_stamp_file_metadata(s3_mock: S3Path) -> None:
    """stamp_file_metadata writes both the hash digest and upload-time
    metadata to an S3 object and they can be read back correctly."""
    import datetime
    import hashlib

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"some release content"
    path = f"/{bucket}/web/packages/aa/bb/pkg-1.0.whl"
    backend.write_file(path, content)

    expected_hash = hashlib.sha256(content).hexdigest()
    upload_time = datetime.datetime(2024, 6, 1, 12, 0, 0, tzinfo=datetime.UTC)

    backend.stamp_file_metadata(path, expected_hash, upload_time)

    assert backend.get_hash(path) == expected_hash
    assert backend.get_upload_time(path) == upload_time


def test_stamp_file_metadata_single_copy(s3_mock: S3Path) -> None:
    """stamp_file_metadata issues exactly one CopyObject and zero HeadObject
    calls — the load() was removed because stamp is only called on freshly
    written objects that carry no prior metadata worth preserving."""
    import datetime
    import hashlib

    from s3path import configuration_map

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"wheel bytes"
    path = f"/{bucket}/web/packages/aa/bb/pkg-2.0.whl"
    backend.write_file(path, content)

    s3path_obj = s3.S3Path(path)
    resource, _ = configuration_map.get_configuration(s3path_obj)
    client = resource.meta.client

    copy_calls: list[dict] = []
    head_calls: list[dict] = []

    original_copy = client.copy_object
    original_head = client.head_object

    def counting_copy(**kwargs: object) -> object:
        copy_calls.append(kwargs)
        return original_copy(**kwargs)

    def counting_head(**kwargs: object) -> object:
        head_calls.append(kwargs)
        return original_head(**kwargs)

    client.copy_object = counting_copy
    client.head_object = counting_head
    try:
        expected_hash = hashlib.sha256(content).hexdigest()
        upload_time = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
        backend.stamp_file_metadata(path, expected_hash, upload_time)
    finally:
        client.copy_object = original_copy
        client.head_object = original_head

    assert len(copy_calls) == 1, f"Expected 1 CopyObject call, got {len(copy_calls)}"
    assert (
        len(head_calls) == 0
    ), f"Expected 0 HeadObject calls (no load()), got {len(head_calls)}"
    # Both keys must be present in the single operation
    metadata = copy_calls[0]["Metadata"]
    assert metadata.get("sha256") == expected_hash
    assert "uploaded-at" in metadata


def test_get_hash_streams_chunks(s3_mock: S3Path) -> None:
    """get_hash falls back to chunked streaming when no metadata digest is
    stored, and returns the correct hash without loading the whole file at once."""
    import hashlib

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    # Content larger than one 64 KB chunk to exercise the iteration loop.
    content = b"x" * (200 * 1024)
    path = f"/{bucket}/web/packages/cc/dd/large-1.0.whl"
    backend.write_file(path, content)

    expected = hashlib.sha256(content).hexdigest()
    # No set_hash called → must fall back to streaming.
    assert backend.get_hash(path) == expected


@pytest.mark.asyncio
async def test_verify_files_s3_legacy_backfill_preserves_existing_metadata(
    s3_mock: S3Path,
) -> None:
    """When the inline _backfill writes sha256 to a legacy object it must
    preserve any metadata keys already present (e.g. uploaded-at).
    The old self.set_hash path did this via load(); the new _backfill path
    does it by merging into head["Metadata"] — this test pins that contract."""
    import datetime
    import hashlib

    from bandersnatch.storage import FileSpec

    backend = s3.S3Storage()
    bucket = s3_mock.bucket
    content = b"legacy wheel with upload time"
    path = f"/{bucket}/web/packages/aa/bb/legacy-preserved.whl"
    backend.write_file(path, content)

    # Stamp only the upload time — no sha256 yet (simulates an object that was
    # written by set_upload_time before the sha256 metadata feature existed).
    upload_time = datetime.datetime(2023, 6, 1, tzinfo=datetime.UTC)
    backend.set_upload_time(path, upload_time)

    sha = hashlib.sha256(content).hexdigest()
    spec = FileSpec(
        path=s3.S3Path(path),
        url="https://example.com/legacy-preserved.whl",
        filename="legacy-preserved.whl",
        size=len(content),
        digests={"sha256": sha},
        upload_time=upload_time,
    )

    bad = [s async for s in backend.verify_files([spec])]
    assert bad == []

    # sha256 must be written…
    from s3path import configuration_map

    resource, _ = configuration_map.get_configuration(s3.S3Path(path))
    obj = resource.Object(bucket, "web/packages/aa/bb/legacy-preserved.whl")
    obj.load()
    assert obj.metadata.get("sha256") == sha
    # …and the pre-existing uploaded-at must NOT have been wiped.
    assert "uploaded-at" in obj.metadata

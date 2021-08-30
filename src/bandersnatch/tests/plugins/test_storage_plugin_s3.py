from bandersnatch_storage_plugins import s3


def test_rewrite(s3_mock: str) -> None:
    backend = s3.S3Storage()
    with backend.rewrite(f"/{s3_mock.bucket}/test") as fp:
        fp.write("testcontent\n")
    assert s3.S3Path("/test-bucket/test").read_text() == "testcontent\n"


def test_update_safe(s3_mock: str) -> None:
    backend = s3.S3Storage()
    with backend.update_safe(
        f"/{s3_mock.bucket}/todo", mode="w+", encoding="utf-8"
    ) as fp:
        fp.write("flask\n")
    assert s3.S3Path(f"/{s3_mock.bucket}/todo").read_text() == "flask\n"


def test_path_mkdir(s3_mock: str) -> None:
    new_folder = s3.S3Path(f"/{s3_mock.bucket}/test_folder")
    assert not new_folder.is_dir()
    new_folder.mkdir()
    assert new_folder.is_dir()


def test_path_glob(s3_mock: str) -> None:
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


def test_lock(s3_mock: str) -> None:
    backend = s3.S3Storage()
    s3lock = backend.get_lock(f"/{s3_mock.bucket}/.lock")
    with s3lock.acquire(timeout=30):
        assert s3lock.is_locked is True
    assert s3lock.is_locked is False


def test_compare_files(s3_mock: str) -> None:
    backend = s3.S3Storage()
    backend.write_file(f"/{s3_mock.bucket}/file1", "test")
    backend.write_file(f"/{s3_mock.bucket}/file2", "test")
    assert (
        backend.compare_files(f"/{s3_mock.bucket}/file1", f"/{s3_mock.bucket}/file2")
        is True
    )


def test_read_write_file(s3_mock: str) -> None:
    backend = s3.S3Storage()
    backend.write_file(f"/{s3_mock.bucket}/file1", "test")

    assert backend.read_file(f"/{s3_mock.bucket}/file1", text=True) == "test"


def test_delete_file(s3_mock: str) -> None:
    backend = s3.S3Storage()
    sample_file = backend.PATH_BACKEND(f"/{s3_mock.bucket}/file1")
    sample_file.touch()
    assert sample_file.exists() is True

    backend.delete_file(f"/{s3_mock.bucket}/file1")
    assert sample_file.exists() is False


def test_delete_path(s3_mock: str) -> None:
    backend = s3.S3Storage()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder1/file1").touch()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/file2").touch()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/file3").touch()
    backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/subdir1/file4").touch()

    assert backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder1/file1").exists() is True
    assert backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/file3").exists() is True
    assert (
        backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/subdir1/file4").exists()
        is True
    )

    backend.delete(f"/{s3_mock.bucket}/folder2")

    assert backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder1/file1").exists() is True
    assert backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/file2").exists() is False
    assert backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/file3").exists() is False
    assert (
        backend.PATH_BACKEND(f"/{s3_mock.bucket}/folder2/subdir1/file4").exists()
        is False
    )


def test_mkdir_rmdir(s3_mock: str) -> None:
    backend = s3.S3Storage()
    backend.mkdir(f"/{s3_mock.bucket}/test_folder")

    test_folder = backend.PATH_BACKEND(f"/{s3_mock.bucket}/test_folder")

    assert test_folder.is_dir()

    backend.rmdir(f"/{s3_mock.bucket}/test_folder")

    test_folder = backend.PATH_BACKEND(f"/{s3_mock.bucket}/test_folder")

    assert test_folder.is_dir() is False


def test_plugin_init(s3_mock: str) -> None:
    backend = s3.S3Storage()
    backend.initialize_plugin()

    assert backend.resource is not None

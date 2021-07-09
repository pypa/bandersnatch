from bandersnatch_storage_plugins import s3


def test_rewrite(s3_mock):
    backend = s3.S3Storage()
    with backend.rewrite(f"/{s3_mock.bucket}/test") as fp:
        fp.write("testcontent\n")
    assert s3.S3Path('/test-bucket/test').read_text() == "testcontent\n"


def test_update_safe(s3_mock):
    backend = s3.S3Storage()
    with backend.update_safe(f"/{s3_mock.bucket}/todo", mode="w+", encoding="utf-8") as fp:
        fp.write("flask\n")
    assert s3.S3Path(f"/{s3_mock.bucket}/todo").read_text() == "flask\n"


def test_path_mkdir(s3_mock):
    new_folder = s3.S3Path(f"/{s3_mock.bucket}/test_folder")
    assert not new_folder.is_dir()
    new_folder.mkdir()
    assert new_folder.is_dir()


def test_path_glob(s3_mock):
    files = ["index.html", "s1/index.html", "s3/index.html", "s3/index.html", "s3/not.html"]
    for f in files:
        s3.S3Path(f"/{s3_mock.bucket}/{f}").touch()

    glob_result = list(s3.S3Path(f"/{s3_mock.bucket}").glob("**/index.html"))
    assert s3.S3Path(f"/{s3_mock.bucket}/s1/index.html") in glob_result
    assert s3.S3Path(f"/{s3_mock.bucket}/s3/not.html") not in glob_result


def test_lock(s3_mock):
    backend = s3.S3Storage()
    s3lock = backend.get_lock(f"/{s3_mock.bucket}/.lock")
    with s3lock.acquire(timeout=30):
        assert s3lock.is_locked is True
    assert s3lock.is_locked is False


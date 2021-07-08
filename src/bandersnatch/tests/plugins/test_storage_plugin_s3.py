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

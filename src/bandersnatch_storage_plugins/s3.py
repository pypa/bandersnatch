from __future__ import annotations

import configparser
import contextlib
import datetime
import hashlib
import logging
import os
import pathlib
import tempfile
from fnmatch import fnmatch
from typing import IO, Any, Generator, Iterator

import boto3
import filelock
from botocore.client import Config
from s3path import PureS3Path
from s3path import S3Path as _S3Path
from s3path import register_configuration_parameter

from bandersnatch.storage import PATH_TYPES, StoragePlugin

logger = logging.getLogger("bandersnatch")


class S3Path(_S3Path):
    keep_file = ".s3keep"

    def mkdir(
        self, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
    ) -> None:
        self.joinpath(self.keep_file).touch()

    def glob(self, pattern: str) -> Iterator[S3Path]:
        bucket_name = self.bucket
        resource, _ = self._accessor.configuration_map.get_configuration(self)
        bucket = resource.Bucket(bucket_name)

        kwargs = {
            "Bucket": bucket_name,
            "Prefix": self._accessor.generate_prefix(self),
            "Delimiter": "",
        }
        continuation_token = None
        while True:
            if continuation_token:
                # mypy thinks we never get here due to response.get()
                # not being typed I think
                kwargs["ContinuationToken"] = continuation_token  # type: ignore
            response = bucket.meta.client.list_objects_v2(**kwargs)
            for file in response["Contents"]:
                file_path = S3Path(f"/{bucket_name}/{file['Key']}")
                if fnmatch(str(file_path.relative_to(self)), pattern):
                    yield file_path
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")


class S3FileLock(filelock.BaseFileLock):
    """
    Simply watches the existence of the lock file.
    """

    def __init__(
        self,
        lock_file: str,
        timeout: int = -1,
        backend: S3Storage | None = None,
    ) -> None:
        # The path to the lock file.
        self.backend: S3Storage | None = backend
        self._lock_file_fd: S3Storage | None
        super().__init__(lock_file, timeout=timeout)

    @property
    def path_backend(self) -> type[S3Path]:
        if self.backend is not None:
            return self.backend.PATH_BACKEND
        raise RuntimeError("Failed to retrieve s3 backend")

    def _acquire(self) -> None:
        try:
            logger.info("Attempting to acquire lock")
            fd: S3Path = self.path_backend(self.lock_file)
            fd.touch()
        except OSError as exc:
            logger.error("Failed to acquire lock...")
            logger.exception("Exception: ", exc)
        else:
            logger.info(f"Acquired lock: {self.lock_file}")
            self._lock_file_fd = fd
        return None

    def _release(self) -> None:
        self._lock_file_fd = None
        try:
            logger.info(f"Removing lock: {self.lock_file}")
            self.path_backend(self.lock_file).unlink()
        except OSError as exc:
            logger.error("Failed to remove lockfile")
            logger.exception("Exception: ", exc)
        else:
            logger.info("Successfully cleaned up lock")
        return None

    @property
    def is_locked(self) -> bool:
        return bool(self.path_backend(self.lock_file).exists())


class S3Storage(StoragePlugin):
    name = "s3"
    PATH_BACKEND = S3Path
    resource = None
    UPLOAD_TIME_METADATA_KEY = "uploaded-at"

    def get_config_value(
        self, config_key: str, *env_keys: Any, default: str | None = None
    ) -> str | None:
        value = None
        try:
            value = self.configuration["s3"][config_key]
        except KeyError:
            os_key = next(iter(k for k in env_keys if k in os.environ), None)
            if os_key is not None:
                value = os.environ[os_key]
        if value is None:
            value = default
        return value

    def initialize_plugin(self) -> None:
        """
        Code to initialize the plugin
        """
        region_name = self.get_config_value("region_name")
        aws_access_key_id = self.get_config_value("aws_access_key_id")
        aws_secret_access_key = self.get_config_value("aws_secret_access_key")
        endpoint_url = self.get_config_value("endpoint_url")
        signature_version = self.get_config_value("signature_version")
        try:
            mirror_base_path = PureS3Path(self.configuration.get("mirror", "directory"))
        except (configparser.NoOptionError, configparser.NoSectionError) as e:
            logger.error(
                "Mirror directory must be set when using s3 as storage backend"
            )
            raise e
        s3_args = {}
        if endpoint_url:
            s3_args["endpoint_url"] = endpoint_url
        if aws_access_key_id:
            s3_args["aws_access_key_id"] = aws_access_key_id
        if region_name:
            s3_args["region_name"] = region_name
        if aws_secret_access_key:
            s3_args["aws_secret_access_key"] = aws_secret_access_key
        if signature_version:
            s3_args["config"] = Config(signature_version=signature_version)
        resource = boto3.resource("s3", **s3_args)
        register_configuration_parameter(mirror_base_path, resource=resource)

    def get_flock_path(self) -> PATH_TYPES:
        """Not sure what it does
        this method is not implemented in neither filesystem or swift
        """
        pass

    def get_lock(self, path: str | None = None) -> S3FileLock:
        if path is None:
            path = str(self.mirror_base_path / ".lock")
        return S3FileLock(path, backend=self)

    def walk(self, root: PATH_TYPES, dirs: bool = True) -> list[S3Path]:
        if not isinstance(root, self.PATH_BACKEND):
            root = self.PATH_BACKEND(root)

        results: list[S3Path] = []
        for pth in root.iterdir():
            if pth.is_dir():
                if dirs:
                    results.append(pth)
                for subpath in self.walk(pth, dirs=dirs):
                    results.append(pth / subpath)
            else:
                results.append(pth)
        return results

    def find(self, root: PATH_TYPES, dirs: bool = True) -> str:
        """It's strongly discouraged to use this method as it takes a lot of time,
        S3Path.glob or S3Path.rglob will be better.
        """
        results = self.walk(root, dirs=dirs)
        results.sort()
        return "\n".join(str(result.relative_to(root)) for result in results)

    @contextlib.contextmanager
    def rewrite(
        self, filepath: PATH_TYPES, mode: str = "w", **kw: Any
    ) -> Generator[IO, None, None]:
        """Rewrite an existing file atomically to avoid programs running in
        parallel to have race conditions while reading."""
        if not isinstance(filepath, self.PATH_BACKEND):
            filepath = self.PATH_BACKEND(filepath)
        with filepath.open(mode=mode, **kw) as fh:
            yield fh

    @contextlib.contextmanager
    def update_safe(self, filename: PATH_TYPES, **kw: Any) -> Generator[IO, None, None]:
        """Rewrite a file atomically.

        Clients are allowed to delete the tmpfile to signal that they don't
        want to have it updated.
        """
        with tempfile.NamedTemporaryFile(
            delete=False,
            prefix=f"{os.path.basename(filename)}.",
            **kw,
        ) as tf:
            yield tf
            if not os.path.exists(tf.name):
                return
            local_filename_tmp = pathlib.Path(tf.name)
        self.copy_local_file(str(local_filename_tmp), str(filename))
        local_filename_tmp.unlink()

    def copy_local_file(self, source: PATH_TYPES, dest: PATH_TYPES) -> None:
        """Copy the contents of a local file to a destination in swift"""
        with open(source, "rb") as fh:
            self.write_file(str(dest), fh.read())
        return

    def compare_files(self, file1: PATH_TYPES, file2: PATH_TYPES) -> bool:
        """Compare two files, returning true if they are the same and False if not."""
        file1_contents = self.read_file(file1, text=False)
        file2_contents = self.read_file(file2, text=False)
        assert isinstance(file1_contents, bytes)
        assert isinstance(file2_contents, bytes)
        file1_hash = hashlib.sha256(file1_contents).hexdigest()
        file2_hash = hashlib.sha256(file2_contents).hexdigest()
        return file1_hash == file2_hash

    def copy_file(self, source: PATH_TYPES, dest: PATH_TYPES) -> None:
        if not isinstance(source, self.PATH_BACKEND):
            source = self.PATH_BACKEND(source)
        if not isinstance(dest, self.PATH_BACKEND):
            dest = self.PATH_BACKEND(dest)
        if not self.exists(source):
            raise FileNotFoundError(source)
        resource, _ = source._accessor.configuration_map.get_configuration(source)
        client = resource.meta.client
        client.copy_object(
            Key=dest.key,
            CopySource={"Bucket": source.bucket, "Key": source.key},
            Bucket=dest.bucket,
        )
        return

    def write_file(
        self,
        path: PATH_TYPES,
        contents: str | bytes,
        encoding: str | None = None,
    ) -> None:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        if isinstance(contents, str):
            with path.open(mode="w", encoding=encoding) as fp:
                fp.write(contents)
        elif isinstance(contents, bytes):
            with path.open(mode="wb") as fp:
                fp.write(contents)
        return

    @contextlib.contextmanager
    def open_file(
        self, path: PATH_TYPES, text: bool = True, encoding: str = "utf-8"
    ) -> Generator[IO, None, None]:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        mode = "r" if text else "rb"
        file_encoding = None
        if text:
            file_encoding = encoding
        with path.open(mode=mode, encoding=file_encoding) as fh:
            yield fh

    def read_file(
        self,
        path: PATH_TYPES,
        text: bool = True,
        encoding: str = "utf-8",
        errors: str | None = None,
    ) -> str | bytes:
        """Return the contents of the requested file, either a a bytestring or a unicode
        string depending on whether **text** is True"""
        with self.open_file(path, text=text, encoding=encoding) as fh:
            contents: str | bytes = fh.read()
        return contents

    def delete_file(self, path: PATH_TYPES, dry_run: bool = False) -> int:
        """Delete a file"""
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        log_prefix = "[DRY RUN] " if dry_run else ""
        logger.info(f"{log_prefix}Removing file: {path!s}")
        if not dry_run:
            path.unlink()
        return 0

    def delete(self, path: PATH_TYPES, dry_run: bool = False) -> int:
        """Delete the provided path, recursively if necessary."""
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        log_prefix = "[DRY RUN] " if dry_run else ""
        logger.info(f"{log_prefix}Removing file: {path!s}")
        if not dry_run:
            for p in path.glob("*"):
                p.unlink(missing_ok=True)
        return 0

    def mkdir(
        self, path: PATH_TYPES, exist_ok: bool = False, parents: bool = False
    ) -> None:
        """
        Create the provided directory

        This operation is a no-op on swift.
        """
        logger.warning(
            f"Creating directory in object storage: "
            f"{path} with {self.PATH_BACKEND.keep_file} file"
        )
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        path.joinpath(self.PATH_BACKEND.keep_file).touch()

    def rmdir(
        self,
        path: PATH_TYPES,
        recurse: bool = False,
        force: bool = False,
        ignore_errors: bool = False,
        dry_run: bool = False,
    ) -> int:
        """
        Remove the directory. If recurse is True, allow removing empty children.

        If force is true, remove contents destructively.
        """
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        log_prefix = "[DRY RUN] " if dry_run else ""
        logger.info(f"{log_prefix}Removing file: {path!s}")
        if not dry_run:
            path.rmdir()
        return 0

    def exists(self, path: PATH_TYPES) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        return bool(path.exists())

    def is_dir(self, path: PATH_TYPES) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        return bool(path.is_dir())

    def is_file(self, path: PATH_TYPES) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        return bool(path.is_file())

    def is_symlink(self, path: PATH_TYPES) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        return bool(path.is_symlink())

    def get_hash(self, path: PATH_TYPES, function: str = "sha256") -> str:
        h = getattr(hashlib, function)(self.read_file(path, text=False))
        return str(h.hexdigest())

    def symlink(
        self,
        src: PATH_TYPES,
        dest: PATH_TYPES,
    ) -> None:
        self.copy_file(src, dest)

    def get_file_size(self, path: PATH_TYPES) -> int:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        return int(path.stat().st_size)

    def get_upload_time(self, path: PATH_TYPES) -> datetime.datetime:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        resource, _ = path._accessor.configuration_map.get_configuration(path)
        s3object = resource.Object(path.bucket, str(path.key))
        ts = s3object.metadata.get(self.UPLOAD_TIME_METADATA_KEY, 0)
        if not isinstance(ts, int):
            ts = int(float(ts))
        return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)

    def set_upload_time(self, path: PATH_TYPES, time: datetime.datetime) -> None:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        resource, _ = path._accessor.configuration_map.get_configuration(path)
        s3object = resource.Object(path.bucket, str(path.key))
        s3object.metadata.update({self.UPLOAD_TIME_METADATA_KEY: str(time.timestamp())})
        # s3 does not support editing metadata after upload, it can be done better.
        # by setting metadata before uploading.
        s3object.copy_from(
            CopySource={"Bucket": path.bucket, "Key": str(path.key)},
            Metadata=s3object.metadata,
            MetadataDirective="REPLACE",
        )

from __future__ import annotations

import asyncio
import configparser
import contextlib
import datetime
import hashlib
import logging
import os
import pathlib
import tempfile
from collections.abc import AsyncIterator, Generator, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from fnmatch import fnmatch
from typing import IO, TYPE_CHECKING, Any, cast

import boto3
import filelock
from botocore.client import Config
from botocore.exceptions import ClientError
from s3path import PureS3Path
from s3path import S3Path as _S3Path
from s3path import configuration_map, register_configuration_parameter
from s3path.accessor import _generate_prefix

if TYPE_CHECKING:
    from s3path.accessor import _S3DirEntry

from bandersnatch.storage import PATH_TYPES, FileSpec, ReleaseFileStatus, StoragePlugin

logger = logging.getLogger("bandersnatch")

_THROTTLE_CODES = frozenset(
    {
        "SlowDown",
        "RequestLimitExceeded",
        "Throttling",
        "ThrottlingException",
        "TooManyRequestsException",
    }
)


def _s3_head_object(client: Any, bucket: str, key: str) -> dict[str, Any] | None:
    """Issue a HeadObject, returning the response dict or None on 404.
    Re-raises all other ClientErrors; logs a warning for throttle codes."""
    try:
        return cast(dict[str, Any], client.head_object(Bucket=bucket, Key=key))
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchKey"):
            return None
        if code in _THROTTLE_CODES:
            logger.warning(
                "S3 throttling on HeadObject for %s/%s (%s). "
                "Consider lowering [s3] verify_concurrency.",
                bucket,
                key,
                code,
            )
        raise


def _stream_object_hash(client: Any, bucket: str, key: str, digest_name: str) -> str:
    h = hashlib.new(digest_name)
    body = client.get_object(Bucket=bucket, Key=key)["Body"]
    try:
        for chunk in iter(lambda: body.read(64 * 1024), b""):
            h.update(chunk)
    finally:
        body.close()
    return h.hexdigest()


class S3Path(_S3Path):
    keep_file = ".s3keep"

    def mkdir(
        self, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
    ) -> None:
        self.joinpath(self.keep_file).touch()

    def glob(self, pattern: str) -> Iterator[S3Path]:
        bucket_name = self.bucket
        resource, _ = configuration_map.get_configuration(self)
        bucket = resource.Bucket(bucket_name)

        prefix = _generate_prefix(self)

        kwargs = {
            "Bucket": bucket_name,
            "Prefix": prefix,
            "Delimiter": "",
        }
        continuation_token = None
        while True:
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
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
    BOTO_CONFIG_PREFIX = "config_param_"
    configuration_parameters: dict = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Track whether an explicit config was provided to this instance to
        # avoid leaking global singleton config parameters into unrelated ops.
        self._explicit_config = bool(kwargs.get("config"))
        # Ensure per-instance parameter dict (avoid class-level mutation leaks)
        self.configuration_parameters = {}
        # Run base initializer (calls initialize_plugin only if active backend)
        super().__init__(*args, **kwargs)

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
        self.configuration_parameters = {
            k.removeprefix(self.BOTO_CONFIG_PREFIX): v
            for k, v in self.configuration["s3"].items()
            if k.startswith(self.BOTO_CONFIG_PREFIX)
        }
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
        max_attempts = self.configuration.getint("s3", "max_attempts", fallback=10)
        retry_config = {"mode": "adaptive", "max_attempts": max_attempts}

        # Ensures that the HTTP connection pool was sized to match verify_concurrency.
        verify_concurrency = self.configuration.getint(
            "s3", "verify_concurrency", fallback=50
        )
        config_kwargs: dict[str, Any] = {
            "retries": retry_config,
            "max_pool_connections": max(10, verify_concurrency),
        }
        if signature_version:
            config_kwargs["signature_version"] = signature_version
        s3_args["config"] = Config(**config_kwargs)
        resource = boto3.resource("s3", **s3_args)
        # Register the S3 resource for the configured path, but do not register
        # per-request parameters globally to avoid leaking settings (like SSE)
        # into unrelated paths/tests. Parameters are registered per-path later
        # in create_path_backend when this backend actually operates on a path.
        register_configuration_parameter(
            mirror_base_path,
            resource=resource,
            parameters={},
        )

    def create_path_backend(self, path: PATH_TYPES) -> S3Path:
        path = self.PATH_BACKEND(path)
        # Only register per-path parameters (e.g., SSE) when this backend was
        # constructed with an explicit config. This prevents params from a
        # previously loaded global config from affecting unrelated tests/paths.
        if self._explicit_config and self.configuration_parameters:
            register_configuration_parameter(
                path, parameters=self.configuration_parameters
            )

        return path

    def get_lock(self, path: str | None = None) -> S3FileLock:
        if path is None:
            path = str(self.mirror_base_path / ".lock")
        return S3FileLock(path, backend=self)

    def walk(self, root: PATH_TYPES, dirs: bool = True) -> list[S3Path]:
        if not isinstance(root, self.PATH_BACKEND):
            root = self.create_path_backend(root)

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
        self,
        filepath: PATH_TYPES,
        mode: str = "w",
        file_metadata: dict[str, str] | None = None,
        **kw: Any,
    ) -> Generator[IO]:
        """Rewrite an existing file atomically to avoid programs running in
        parallel to have race conditions while reading."""
        if not isinstance(filepath, self.PATH_BACKEND):
            filepath = self.create_path_backend(filepath)

        registered_metadata = False
        if file_metadata:
            upload_params: dict[str, Any] = {}
            if self._explicit_config and self.configuration_parameters:
                upload_params.update(self.configuration_parameters)
            upload_params["Metadata"] = file_metadata
            register_configuration_parameter(filepath, parameters=upload_params)
            registered_metadata = True

        try:
            with filepath.open(mode=mode, **kw) as fh:
                yield fh
        finally:
            # reset config params for future calls
            if registered_metadata:
                restore_params: dict[str, Any] = {}
                if self._explicit_config and self.configuration_parameters:
                    restore_params.update(self.configuration_parameters)
                register_configuration_parameter(filepath, parameters=restore_params)

    def build_release_file_metadata(
        self,
        digest: str,
        upload_time: datetime.datetime,
        digest_name: str = "sha256",
    ) -> dict[str, str] | None:
        return {
            digest_name: digest,
            self.UPLOAD_TIME_METADATA_KEY: str(upload_time.timestamp()),
        }

    def stamps_metadata_on_write(self) -> bool:
        return True

    def _copy_object_kwargs(self) -> dict[str, Any]:
        if self._explicit_config and self.configuration_parameters:
            return dict(self.configuration_parameters)
        return {}

    def _backfill_release_metadata(
        self,
        client: Any,
        bucket: str,
        key: str,
        head: dict[str, Any],
        *,
        digest_name: str | None = None,
        digest: str | None = None,
        upload_time: datetime.datetime | None = None,
    ) -> None:
        merged = dict(head.get("Metadata", {}))
        if digest_name is not None and digest is not None:
            merged[digest_name] = digest
        if upload_time is not None:
            merged[self.UPLOAD_TIME_METADATA_KEY] = str(upload_time.timestamp())
        client.copy_object(
            Bucket=bucket,
            Key=key,
            CopySource={"Bucket": bucket, "Key": key},
            Metadata=merged,
            MetadataDirective="REPLACE",
            **self._copy_object_kwargs(),
        )

    def _certify_from_head(
        self,
        client: Any,
        bucket: str,
        key: str,
        head: dict[str, Any],
        *,
        size: int,
        upload_time: datetime.datetime,
        digest: str,
        compare_method: str,
        digest_name: str,
        backfill: bool,
        would_backfill_label: str | None = None,
        refresh_stale_metadata: bool = False,
    ) -> ReleaseFileStatus:
        if head["ContentLength"] != size:
            return ReleaseFileStatus.MISMATCH

        stat_upload_stale = False
        if compare_method == "stat":
            head_upload_time = self._upload_time_from_head(head)
            if head_upload_time is not None and head_upload_time == upload_time:
                return ReleaseFileStatus.CURRENT
            if not refresh_stale_metadata:
                return ReleaseFileStatus.MISMATCH
            stat_upload_stale = True

        stored_hash = head.get("Metadata", {}).get(digest_name)
        if stored_hash is not None:
            if stored_hash != digest:
                return ReleaseFileStatus.MISMATCH
            if stat_upload_stale:
                if backfill:
                    logger.info(
                        "Updating upload time metadata for s3://%s/%s.",
                        bucket,
                        key,
                    )
                    self._backfill_release_metadata(
                        client,
                        bucket,
                        key,
                        head,
                        upload_time=upload_time,
                    )
                elif would_backfill_label is not None:
                    logger.debug(
                        "[DRY RUN] would refresh upload time metadata for %s",
                        would_backfill_label,
                    )
            return ReleaseFileStatus.CURRENT

        actual_hash = _stream_object_hash(client, bucket, key, digest_name)
        if actual_hash != digest:
            return ReleaseFileStatus.MISMATCH

        if backfill:
            self._backfill_release_metadata(
                client,
                bucket,
                key,
                head,
                digest_name=digest_name,
                digest=actual_hash,
                upload_time=upload_time if stat_upload_stale else None,
            )
        elif would_backfill_label is not None:
            logger.debug(
                "[DRY RUN] would back-fill %s metadata for %s",
                digest_name,
                would_backfill_label,
            )
        return ReleaseFileStatus.CURRENT

    def _upload_time_from_head(self, head: dict) -> datetime.datetime | None:
        """Parse the stored upload time out of a HeadObject response."""
        raw = head.get("Metadata", {}).get(self.UPLOAD_TIME_METADATA_KEY)
        if raw is None:
            return None
        try:
            ts = int(float(raw))
        except (TypeError, ValueError):
            return None
        return datetime.datetime.fromtimestamp(ts, datetime.UTC)

    def release_file_is_current(
        self,
        path: PATH_TYPES,
        *,
        size: int,
        upload_time: datetime.datetime,
        digest: str,
        compare_method: str = "hash",
        digest_name: str = "sha256",
    ) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        resource, _ = configuration_map.get_configuration(path)
        client = resource.meta.client
        bucket = path.bucket
        key = str(path.key)

        head = _s3_head_object(client, bucket, key)
        if head is None:
            return False

        status = self._certify_from_head(
            client,
            bucket,
            key,
            head,
            size=size,
            upload_time=upload_time,
            digest=digest,
            compare_method=compare_method,
            digest_name=digest_name,
            backfill=True,
            refresh_stale_metadata=True,
        )
        if status is ReleaseFileStatus.CURRENT:
            return True
        if status is ReleaseFileStatus.MISMATCH:
            logger.info(f"File mismatch with local file {path}, will re-download.")
            self.delete_file(path)
        return False

    @contextlib.contextmanager
    def update_safe(self, filename: PATH_TYPES, **kw: Any) -> Generator[IO]:
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
        """Copy the contents of a local file to a destination in S3"""
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
        resource, _ = configuration_map.get_configuration(source)
        client = resource.meta.client
        kwargs: dict[str, Any] = {}
        # Apply request kwargs only for explicitly-configured instances
        if self._explicit_config and self.configuration_parameters:
            kwargs.update(self.configuration_parameters)
        client.copy_object(
            Key=dest.key,
            CopySource={"Bucket": source.bucket, "Key": source.key},
            Bucket=dest.bucket,
            **kwargs,
        )
        return

    def write_file(
        self,
        path: PATH_TYPES,
        contents: str | bytes,
        encoding: str | None = None,
    ) -> None:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
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
    ) -> Generator[IO]:
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
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                for p in path.glob("*"):
                    p.unlink(missing_ok=True)
        return 0

    def mkdir(
        self, path: PATH_TYPES, exist_ok: bool = False, parents: bool = False
    ) -> None:
        """
        Create the provided directory

        This operation is effectively a no-op on S3; we create a keep file to
        emulate directory semantics.
        """
        logger.warning(
            "Creating directory in object storage: "
            f"{path} with {self.PATH_BACKEND.keep_file} file"
        )
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        path.joinpath(self.PATH_BACKEND.keep_file).touch()

    def scandir(self, path: PATH_TYPES) -> Generator[_S3DirEntry]:
        """Read entries from the provided directory"""
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        for p in path.iterdir():
            if p.name == self.PATH_BACKEND.keep_file:
                continue
            yield p

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
            path = self.create_path_backend(path)
        log_prefix = "[DRY RUN] " if dry_run else ""
        logger.info(f"{log_prefix}Removing file: {path!s}")
        if not dry_run:
            path.rmdir()
        return 0

    def exists(self, path: PATH_TYPES) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        return bool(path.exists())

    def is_dir(self, path: PATH_TYPES) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        return bool(path.is_dir())

    def is_file(self, path: PATH_TYPES) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        return bool(path.is_file())

    def is_symlink(self, path: PATH_TYPES) -> bool:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        return bool(path.is_symlink())

    def get_hash(self, path: PATH_TYPES, function: str = "sha256") -> str:
        """
        Get the hash of a given path.
        Returns the stored metadata hash if present (fast path).
        Otherwise streams the object content in chunks of 64kb
        """
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        resource, _ = configuration_map.get_configuration(path)
        s3object = resource.Object(path.bucket, str(path.key))
        s3object.load()

        stored = s3object.metadata.get(function)
        if stored:
            return str(stored)

        client = resource.meta.client
        return _stream_object_hash(client, path.bucket, str(path.key), function)

    def symlink(
        self,
        src: PATH_TYPES,
        dest: PATH_TYPES,
    ) -> None:
        self.copy_file(src, dest)

    def get_file_size(self, path: PATH_TYPES) -> int:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        return int(path.stat().st_size)

    def get_upload_time(self, path: PATH_TYPES) -> datetime.datetime:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        resource, _ = configuration_map.get_configuration(path)
        s3object = resource.Object(path.bucket, str(path.key))
        ts = s3object.metadata.get(self.UPLOAD_TIME_METADATA_KEY, 0)
        if not isinstance(ts, int):
            ts = int(float(ts))
        return datetime.datetime.fromtimestamp(ts, datetime.UTC)

    def set_upload_time(self, path: PATH_TYPES, time: datetime.datetime) -> None:
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        resource, _ = configuration_map.get_configuration(path)
        s3object = resource.Object(path.bucket, str(path.key))
        s3object.metadata.update({self.UPLOAD_TIME_METADATA_KEY: str(time.timestamp())})
        # s3 does not support editing metadata after upload, it can be done better.
        # by setting metadata before uploading.
        s3object.copy_from(
            CopySource={"Bucket": path.bucket, "Key": str(path.key)},
            Metadata=s3object.metadata,
            MetadataDirective="REPLACE",
            **self._copy_object_kwargs(),
        )

    def set_hash(self, path: PATH_TYPES, digest: str, function: str = "sha256") -> None:
        """
        Store the hash/digest of the file directly in metadata for better get_hash()
        """
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        resource, _ = configuration_map.get_configuration(path)
        s3object = resource.Object(path.bucket, str(path.key))
        s3object.load()

        metadata = dict(s3object.metadata)
        metadata[function] = digest

        s3object.copy_from(
            CopySource={"Bucket": path.bucket, "Key": str(path.key)},
            Metadata=metadata,
            MetadataDirective="REPLACE",
            **self._copy_object_kwargs(),
        )

    def stamp_file_metadata(
        self,
        path: PATH_TYPES,
        digest: str,
        upload_time: datetime.datetime,
        function: str = "sha256",
    ) -> None:
        """
        Sets both upload time and hash metadata in one CopyObject call.
        """
        if not isinstance(path, self.PATH_BACKEND):
            path = self.create_path_backend(path)
        resource, _ = configuration_map.get_configuration(path)
        s3object = resource.Object(path.bucket, str(path.key))

        metadata = {
            function: digest,
            self.UPLOAD_TIME_METADATA_KEY: str(upload_time.timestamp()),
        }

        s3object.copy_from(
            CopySource={"Bucket": path.bucket, "Key": str(path.key)},
            Metadata=metadata,
            MetadataDirective="REPLACE",
            **self._copy_object_kwargs(),
        )

    async def verify_files(
        self, expected: Iterable[FileSpec], dry_run: bool = False
    ) -> AsyncIterator[FileSpec]:
        """
        Concurrently verifies files in expected list.
        Uses the digest metadata if set to compare hashes (HEAD call only)
        Sets the digest metadata for future get_hash() calls
        (For legacy objects GET used to happen on get_hash which loaded the whole file)
        verify_concurrency param to limit the number of concurrent calls to s3
        """
        specs = list(expected)
        if not specs:
            return

        compare = self.configuration.get("mirror", "compare-method", fallback="hash")
        digest_name = self.configuration.get("mirror", "digest_name", fallback="sha256")

        first_path = self.PATH_BACKEND(str(specs[0].path))
        resource, _ = configuration_map.get_configuration(first_path)
        client = resource.meta.client
        bucket = first_path.bucket

        if not hasattr(self, "_verify_semaphore") or self._verify_semaphore is None:
            concurrency = self.configuration.getint(
                "s3", "verify_concurrency", fallback=50
            )
            self._verify_semaphore: asyncio.Semaphore = asyncio.Semaphore(concurrency)

            # Thread pool for S3 verify API calls, sized to match verify_concurrency.
            # Not using self.executor as we are not hitting PyPI master and can run much wider
            self._verify_executor: ThreadPoolExecutor = ThreadPoolExecutor(
                max_workers=concurrency, thread_name_prefix="s3-verify"
            )

        semaphore = self._verify_semaphore
        loop = asyncio.get_running_loop()
        executor = self._verify_executor

        async def _check(spec: FileSpec) -> FileSpec | None:
            async with semaphore:
                s3_path = self.PATH_BACKEND(str(spec.path))
                key = str(s3_path.key)

                head = await loop.run_in_executor(
                    executor, _s3_head_object, client, bucket, key
                )
                if head is None:
                    return spec

                expected_hash = spec.digests.get(digest_name, "")

                def _certify() -> ReleaseFileStatus:
                    return self._certify_from_head(
                        client,
                        bucket,
                        key,
                        head,
                        size=spec.size,
                        upload_time=spec.upload_time,
                        digest=expected_hash,
                        compare_method=compare,
                        digest_name=digest_name,
                        backfill=not dry_run,
                        would_backfill_label=spec.filename if dry_run else None,
                        refresh_stale_metadata=False,
                    )

                status = await loop.run_in_executor(executor, _certify)
                if status is ReleaseFileStatus.CURRENT:
                    return None
                return spec

        results = await asyncio.gather(*[_check(s) for s in specs])
        for result in results:
            if result is not None:
                yield result

    def iter_package_files(self, packages_path: PATH_TYPES) -> Iterator[PATH_TYPES]:
        """
        Uses ListObjectsV2 to iterate through all the files in the packages path. (ignores .s3keep files)
        """
        if not isinstance(packages_path, self.PATH_BACKEND):
            packages_path = self.create_path_backend(packages_path)

        if not self.exists(packages_path):
            return

        resource, _ = configuration_map.get_configuration(packages_path)
        client = resource.meta.client
        bucket = packages_path.bucket
        prefix = str(packages_path.key).lstrip("/") + "/"

        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                if key.endswith(f"/{self.PATH_BACKEND.keep_file}"):
                    continue
                yield self.PATH_BACKEND(f"/{bucket}/{key}")

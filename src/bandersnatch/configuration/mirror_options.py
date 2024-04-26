import logging
import sys
from configparser import ConfigParser
from pathlib import PurePath
from typing import TypedDict

from bandersnatch.simple import SimpleDigest, SimpleFormat

from .diff_file_reference import eval_legacy_config_ref, has_legacy_config_ref
from .exceptions import (
    ConfigurationError,
    MissingRequiredOptionError,
    OptionValidationError,
)
from .section_reader import SectionReader

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from .utils import StrEnum

logger = logging.getLogger("bandersnatch")


class FileCompareMethod(StrEnum):
    """Method used for checking freshness of files on disk"""

    HASH = "hash"
    STAT = "stat"


class MirrorOptions(TypedDict):
    """A dictionary containing option values from the 'mirror' section of a Bandersnatch config file.

    When used with the 'get_mirror_options' function, this adds a handful of conveniences
    compared to working directly with the ConfigParser section:

    - Options containing file/directory paths are represented with PurePath. Path options
      that are not required (e.g. log_config) have empty values converted to None.
    - Options corresponding to en enum type are represented with that enum type.
    - TypedDict gives you nice editor completions
    """

    directory: PurePath
    storage_backend: str

    master_url: str
    proxy_url: str
    download_mirror_url: str
    download_mirror_no_fallback: bool

    save_json: bool
    save_release_files: bool
    hash_index: bool

    simple_format: SimpleFormat
    digest_name: SimpleDigest
    compare_method: FileCompareMethod

    root_uri: str
    diff_file: PurePath | None
    diff_append_epoch: bool
    keep_index_versions: int

    stop_on_error: bool
    timeout: float
    global_timeout: float
    workers: int
    verifiers: int

    log_config: PurePath | None

    cleanup: bool


def get_mirror_options(config: ConfigParser) -> MirrorOptions:
    """Reads and validates the options in the '[mirror]' section of the configuration file.

    Returns validated keys & values in a dictionary. (The dict is *not* a view/proxy of the
    underlying configparser Section.) Raises a ConfigurationError or one of its subtypes at
    the first error encountered and does not attempt to continue reading options or otherwise
    recover from errors.

    Options represented by Enums or Paths are type converted; a conversion failure raises
    a validation error. Numeric values are range-checked where applicable. String options
    that should not be blank/empty are checked.

    :param ConfigParser config: ConfigParser instance containing sections read from Bandersnatch config files
    :raises ConfigurationError: the 'mirror' section is missing
    :raises MissingRequiredOptionError: a required option is missing
    :raises OptionValidationError: the value given for an option is invalid
    :return MirrorOptions: dictionary containing validated options from the 'mirror' section
    """
    if not config.has_section("mirror"):
        raise ConfigurationError("Config file missing required section '[mirror]'")

    reader = SectionReader(config, "mirror")

    opts: MirrorOptions = {}  # type: ignore

    # can't be missing
    if "directory" not in reader.section:
        raise MissingRequiredOptionError.for_option("mirror", "directory")

    # this throws if the value is a blank or empty string
    directory = reader.get_str_nonempty("directory")

    # can't really find a string PurePath will reject,
    # so not much point in catching ValueError here.
    opts["directory"] = PurePath(directory)

    # can't be empty - we set a default for this, so if we find an empty
    # string it means it was explicitly set to that
    opts["storage_backend"] = reader.get_str_nonempty("storage-backend")

    # can be empty
    diff_file_path = reader.get_str("diff-file")
    if diff_file_path and has_legacy_config_ref(diff_file_path):
        try:
            diff_file_path = eval_legacy_config_ref(config, diff_file_path)
        except ValueError as err:
            logger.error(
                "Invalid section reference in `diff-file` key: %s. Saving diff files in base mirror directory.",
                str(err),
            )
            diff_file_path = (opts["directory"] / "mirrored-files").as_posix()

    if diff_file_path:
        opts["diff_file"] = PurePath(diff_file_path)
    else:
        opts["diff_file"] = None

    opts["diff_append_epoch"] = reader.get_boolean("diff-append-epoch")

    opts["simple_format"] = reader.get_enum(
        SimpleFormat, "simple-format", "Simple API index format"
    )

    opts["digest_name"] = reader.get_enum(
        SimpleDigest, "digest-name", "Simple API file hash digest"
    )

    opts["compare_method"] = reader.get_enum(
        FileCompareMethod, "compare-method", "file comparison method"
    )

    # We set a default; this shouldn't be empty
    opts["master_url"] = reader.get_str_nonempty("master")

    # Can be blank
    opts["proxy_url"] = reader.get_str("proxy")

    # Can be blank
    opts["download_mirror_url"] = reader.get_str("download-mirror")
    opts["download_mirror_no_fallback"] = reader.get_boolean(
        "download-mirror-no-fallback"
    )

    save_release_files = reader.get_boolean("release-files")
    opts["save_release_files"] = save_release_files
    opts["save_json"] = reader.get_boolean("json")
    opts["hash_index"] = reader.get_boolean("hash-index")
    opts["stop_on_error"] = reader.get_boolean("stop-on-error")

    root_uri = reader.get_str("root-uri")
    if not save_release_files and not root_uri:
        # deprecate? could leave root_uri blank and just issue a warning
        root_uri = "https://files.pythonhosted.org"
        logger.warning(
            f"Option 'root_uri' has been set to '{root_uri}' because 'release-files' is disabled. "
            "Please update your config file to set a value for 'root-uri' in the '[mirror]' section."
        )

    opts["root_uri"] = root_uri

    keep_index_versions = reader.get_int("keep-index-versions")
    if keep_index_versions < 0:
        raise OptionValidationError.for_option(
            "mirror", "keep-index-versions", "must be >= 0"
        )

    opts["keep_index_versions"] = keep_index_versions

    timeout_sec = reader.get_float("timeout")
    if timeout_sec < 0:
        raise OptionValidationError.for_option("mirror", "timeout", "must be >= 0")
    opts["timeout"] = timeout_sec

    coro_timeout_sec = reader.get_float("global-timeout")
    if coro_timeout_sec < 0:
        raise OptionValidationError.for_option(
            "mirror", "global-timeout", "must be >= 0"
        )
    opts["global_timeout"] = coro_timeout_sec

    worker_count = reader.get_int("workers")
    if not (1 <= worker_count <= 10):
        raise OptionValidationError.for_option(
            "mirror", "workers", "must be in range 1-10"
        )
    opts["workers"] = worker_count

    verifier_count = reader.get_int("verifiers")
    # TODO: using same upper limit as workers, but the two control different things
    if not (1 <= verifier_count <= 10):
        raise OptionValidationError.for_option(
            "mirror", "verifiers", "must be in range 1-10"
        )
    opts["verifiers"] = verifier_count

    log_config_file = reader.get_str("log-config")
    if log_config_file:
        opts["log_config"] = PurePath(log_config_file)
    else:
        opts["log_config"] = None

    legacy_folder_cleanup = reader.get_boolean("cleanup")
    opts["cleanup"] = legacy_folder_cleanup

    return opts

import contextlib
import filecmp
import hashlib
import os
import os.path
import platform
import sys
import tempfile
from typing import IO, Any, Generator

from . import __version__


def user_agent(async_version: str = "") -> str:
    template = "bandersnatch/{version} ({python}, {system})"
    if async_version:
        template += f" ({async_version})"
    version = __version__
    python = sys.implementation.name
    python += " {}.{}.{}-{}{}".format(*sys.version_info)
    uname = platform.uname()
    system = " ".join([uname.system, uname.machine])
    return template.format(**locals())


USER_AGENT = user_agent()


def hash(path: str, function: str = "sha256") -> str:
    h = getattr(hashlib, function)()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(128 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find(root: str, dirs: bool = True) -> str:
    """A test helper simulating 'find'.

    Iterates over directories and filenames, given as relative paths to the
    root.

    """
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        names = filenames
        if dirs:
            names += dirnames
        for name in names:
            results.append(os.path.join(dirpath, name))
    results.sort()
    return "\n".join(result.replace(root, "", 1) for result in results)


@contextlib.contextmanager
def rewrite(filepath: str, mode: str = "w", **kw: Any) -> Generator[IO, None, None]:
    """Rewrite an existing file atomically to avoid programs running in
    parallel to have race conditions while reading."""
    base_dir = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    # Change naming format to be more friendly with distributed POSIX
    # filesystems like GlusterFS that hash based on filename
    # GlusterFS ignore '.' at the start of filenames and this avoid rehashing
    with tempfile.NamedTemporaryFile(
        mode=mode, prefix=f".{filename}.", delete=False, dir=base_dir, **kw
    ) as f:
        filepath_tmp = f.name
        yield f

    if not os.path.exists(filepath_tmp):
        # Allow our clients to remove the file in case it doesn't want it to be
        # put in place actually but also doesn't want to error out.
        return
    os.chmod(filepath_tmp, 0o100644)
    os.rename(filepath_tmp, filepath)


@contextlib.contextmanager
def update_safe(filename: str, **kw: Any) -> Generator[IO, None, None]:
    """Rewrite a file atomically.

    Clients are allowed to delete the tmpfile to signal that they don't
    want to have it updated.

    """
    with tempfile.NamedTemporaryFile(
        dir=os.path.dirname(filename),
        delete=False,
        prefix=f"{os.path.basename(filename)}.",
        **kw,
    ) as tf:
        if os.path.exists(filename):
            os.chmod(tf.name, os.stat(filename).st_mode & 0o7777)
        tf.has_changed = False  # type: ignore
        yield tf
        if not os.path.exists(tf.name):
            return
        filename_tmp = tf.name
    if os.path.exists(filename) and filecmp.cmp(filename, filename_tmp, shallow=False):
        os.unlink(filename_tmp)
    else:
        os.rename(filename_tmp, filename)
        tf.has_changed = True  # type: ignore

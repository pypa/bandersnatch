import contextlib
import hashlib
import os
import os.path
import sys
import tempfile

from . import __version__


def user_agent():
    template = 'bandersnatch/{version} ({python}, {system})'
    version = __version__
    python = sys.implementation.name
    python += ' {0}.{1}.{2}-{3}{4}'.format(*sys.version_info)
    system = os.uname()
    system = ' '.join([system[0], system[4]])
    return template.format(**locals())


USER_AGENT = user_agent()


def hash(path, function='md5'):
    h = getattr(hashlib, function)()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(128 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find(root, dirs=True):
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
    return '\n'.join(result.replace(root, '', 1) for result in results)


@contextlib.contextmanager
def rewrite(filepath, mode='w', *args, **kw):
    """Rewrite an existing file atomically to avoid programs running in
    parallel to have race conditions while reading."""
    base_dir = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    # Change naming format to be more friendly with distributed POSIX
    # filesystems like GlusterFS that hash based on filename
    # GlusterFS ignore '.' at the start of filenames and this avoid rehashing
    with tempfile.NamedTemporaryFile(mode=mode, prefix='.{}.'.format(filename),
                                     delete=False, dir=base_dir, **kw) as f:
        filepath_tmp = f.name
        yield f

    if not os.path.exists(filepath_tmp):
        # Allow our clients to remove the file in case it doesn't want it to be
        # put in place actually but also doesn't want to error out.
        return
    os.chmod(filepath_tmp, 0o100644)
    os.rename(filepath_tmp, filepath)

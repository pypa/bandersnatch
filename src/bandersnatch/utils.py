import contextlib
import hashlib
import os
import os.path
import tempfile


def hash(path, function='md5'):
    h = getattr(hashlib, function)()
    for line in open(path):
        h.update(line)
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
def rewrite(filename):
    """Rewrite an existing file atomically to avoid programs running in
    parallel to have race conditions while reading."""
    _, filename_tmp = tempfile.mkstemp(dir=os.path.dirname(filename))
    with open(filename_tmp, 'w') as f:
        yield f
    os.rename(filename_tmp, filename)

import contextlib
import hashlib
import os
import os.path
import pkg_resources
import sys
import tempfile


def user_agent():
    template = 'bandersnatch/{version} ({python}, {system})'
    system = os.uname()
    system = ' '.join([system[0], system[2], system[4]])
    version = pkg_resources.require("bandersnatch")[0].version
    # Support Python 2 + 3 - No sys.subversion in Py3
    try:
        python = sys.subversion[0]
    except AttributeError:
        python = sys.implementation.name
    python += ' {0}.{1}.{2}-{3}{4}'.format(*sys.version_info)
    return template.format(**locals())

USER_AGENT = user_agent()


def hash(path, function='md5'):
    h = getattr(hashlib, function)()
    for line in open(path, 'rb'):
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
def rewrite(filename, bytes_write=False):
    """Rewrite an existing file atomically to avoid programs running in
    parallel to have race conditions while reading."""
    fd, filename_tmp = tempfile.mkstemp(dir=os.path.dirname(filename))
    os.close(fd)

    # Py3 - We may want to write bytes
    # requests lib will sometimes give us raw bytes
    # e.g. for tar.bz2 - 4Suite-XML-1.0rc4.tar.bz2
    open_mode = 'wb' if bytes_write else 'w'

    with open(filename_tmp, open_mode) as f:
        yield f
    if not os.path.exists(filename_tmp):
        # Allow our clients to remove the file in case it doesn't want it to be
        # put in place actually but also doesn't want to error out.
        return
    os.chmod(filename_tmp, 0o100644)
    os.rename(filename_tmp, filename)

# package

from collections import namedtuple

# a namedtuple like that given by sys.version_info
__version_info__ = namedtuple(
    'version_info',
    'major minor micro releaselevel serial')(
        major=2,
        minor=2,
        micro=1,
        releaselevel=None,
        serial=0  # Not currently in use below ...
    )

if __version_info__.releaselevel:
    __version__ = '{v.major}.{v.minor}.{v.micro}{v.releaselevel}'.format(
        v=__version_info__
    )
else:
    __version__ = '{v.major}.{v.minor}.{v.micro}'.format(v=__version_info__)

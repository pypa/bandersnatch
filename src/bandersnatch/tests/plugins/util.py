from configparser import ConfigParser
from pathlib import Path

from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.storage import storage_backend_plugins


def make_test_mirror(
    location: Path | None = None, url: str = "https://foo.bar.com"
) -> BandersnatchMirror:
    location = location or Path(".")
    config = ConfigParser()
    config.read_dict(
        {
            "mirror": {
                "storage-backend": "filesystem",
                "directory": location.as_posix(),
                "workers": 2,
            }
        }
    )
    return BandersnatchMirror(
        location or Path("."),
        Master(url=url),
        next(iter(storage_backend_plugins(config=config))),
    )

from configparser import ConfigParser
from pathlib import Path

from bandersnatch.filter import LoadedFilters
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.storage import storage_backend_plugins


def make_test_mirror(
    location: Path | None = None,
    url: str = "https://foo.bar.com",
    config: ConfigParser | None = None,
) -> BandersnatchMirror:
    location = location or Path(".")
    local_config = config or ConfigParser()
    local_config.read_dict(
        {
            "mirror": {
                "storage-backend": "filesystem",
                "directory": location.as_posix(),
                "workers": 2,
            }
        }
    )
    if config:
        local_config.read_dict(config)
    return BandersnatchMirror(
        location or Path("."),
        Master(url=url),
        next(iter(storage_backend_plugins(config=local_config))),
        LoadedFilters(local_config, load_all=True),
    )

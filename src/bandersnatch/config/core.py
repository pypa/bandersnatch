import sys
from collections.abc import Mapping
from configparser import ConfigParser, ExtendedInterpolation
from pathlib import Path
from typing import Protocol, TypeVar, cast

if sys.version_info >= (3, 11):
    from typing import Self
else:
    Self = TypeVar("Self", bound="ConfigModel")


class ConfigModel(Protocol):

    @classmethod
    def from_config_parser(cls: type[Self], source: ConfigParser) -> Self: ...


_C = TypeVar("_C", bound=ConfigModel)


class BandersnatchConfig(ConfigParser):

    def __init__(self, defaults: Mapping[str, str] | None = None) -> None:
        super().__init__(
            defaults=defaults,
            delimiters=("=",),
            strict=True,
            interpolation=ExtendedInterpolation(),
        )

        self._validate_config_models: dict[str, ConfigModel] = {}

    # This allows writing option names in the config file with either '_' or '-' as word separators
    def optionxform(self, optionstr: str) -> str:
        return optionstr.lower().replace("-", "_")

    def read_path(self, file_path: Path) -> None:
        with file_path.open() as cfg_file:
            self.read_file(cfg_file)

    def get_validated(self, model: type[_C]) -> _C:
        name = model.__qualname__
        if name not in self._validate_config_models:
            self._validate_config_models[name] = model.from_config_parser(self)
        return cast(_C, self._validate_config_models[name])

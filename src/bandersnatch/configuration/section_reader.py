from configparser import ConfigParser
from enum import Enum
from typing import TypeVar

from .exceptions import OptionValidationError

E = TypeVar("E", bound=Enum)


class SectionReader:
    """A convenience wrapper for a ConfigParser section with methods for repetitive
    type conversion and error handling. These methods wrap configparser 'getter' methods
    to convert errors to our internal ConfigurationError types with (hopefully) more
    user-friendly error messages.
    """

    def __init__(self, config: ConfigParser, section_name: str) -> None:
        self._accepted_booleans = list(config.BOOLEAN_STATES.keys())
        self._section_name = section_name
        self.section = config[section_name]

    def get_str(self, key: str) -> str:
        return self.section.get(key, fallback="")

    def get_str_nonempty(self, key: str) -> str:
        value = self.section.get(key, fallback="")

        trimmed = value.strip()
        if not trimmed:
            raise OptionValidationError.must_not_be_empty(self._section_name, key)

        return trimmed

    def get_boolean(self, key: str) -> bool:
        try:
            return self.section.getboolean(key)
        except ValueError:
            bool_likes = self._accepted_booleans
            raise OptionValidationError.must_be_convertible(
                self._section_name, key, f"a boolean; one of {bool_likes}"
            )

    def get_int(self, key: str) -> int:
        try:
            return self.section.getint(key)
        except ValueError:
            raise OptionValidationError.must_be_convertible(
                self._section_name, key, "an integer"
            )

    def get_float(self, key: str) -> float:
        try:
            return self.section.getfloat(key)
        except ValueError:
            raise OptionValidationError.must_be_convertible(
                self._section_name, key, "a floating-point number"
            )

    def get_enum(self, enum_cls: type[E], key: str, desc: str) -> E:
        value = self.section.get(key, fallback="")
        name = value.upper()
        try:
            return enum_cls[name]
        except KeyError:
            valid_names = [member.name for member in enum_cls]
            msg = f"not a valid {desc}; must be one of: {valid_names}"
            raise OptionValidationError.for_option(self._section_name, key, msg)

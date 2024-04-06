from typing_extensions import Self


class ConfigurationError(Exception):

    @classmethod
    def for_section(cls, section: str, message: str) -> Self:
        return cls(f"Configuration error in [{section}] section: {message}")


class MissingOptionError(ConfigurationError):

    @classmethod
    def for_option(cls, section: str, option: str) -> Self:
        return cls.for_section(section, f"missing required option '{option}'")


class InvalidValueError(ConfigurationError):

    @classmethod
    def for_option(cls, section: str, option: str, info: str) -> Self:
        return cls.for_section(section, f"invalid value for option '{option}': {info}")

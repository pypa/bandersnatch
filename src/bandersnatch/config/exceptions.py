"""Exception subclasses for configuration file loading and validation."""


class ConfigError(Exception):
    """Base exception for configuration file exceptions."""

    pass


class ConfigFileNotFound(ConfigError):
    """A specified configuration file is missing or unreadable."""

    pass

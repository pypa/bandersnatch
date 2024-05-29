from bandersnatch.configuration import BandersnatchConfig


def mock_config(contents: str, filename: str = "test.conf") -> BandersnatchConfig:
    """
    Creates a config file with contents and loads them into a BandersnatchConfig instance.
    Because BandersnatchConfig is a singleton, it needs to be cleared before reading any
    new configuration so the configuration from different tests aren't re-used.
    """
    # If this is the first time BandersnatchConfig was initialized during a test run,
    # skip loading defaults in init b/c we're going to do that explicitly instead.
    instance = BandersnatchConfig(load_defaults=False)
    # If this *isn't* the first time BandersnatchConfig was initialized, then we've
    # got to clear any previously loaded configuration from the singleton.
    instance.clear()
    # explicitly load defaults here
    instance._read_defaults_file()
    # load specified config content
    instance.read_string(contents)
    return instance

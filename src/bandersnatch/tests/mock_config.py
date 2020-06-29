from bandersnatch.configuration import BandersnatchConfig


def mock_config(contents: str, filename: str = "test.conf") -> BandersnatchConfig:
    """
    Creates a config file with contents and loads them into a
    BandersnatchConfig instance.
    """
    with open(filename, "w") as fd:
        fd.write(contents)

    instance = BandersnatchConfig()
    instance.config_file = filename
    instance.load_configuration()
    return instance

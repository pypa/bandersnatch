from bandersnatch.config import BandersnatchConfig


def mock_config(contents: str, filename: str = "test.conf") -> BandersnatchConfig:
    """
    Creates a config file with contents and loads them into a
    BandersnatchConfig instance.
    """

    instance = BandersnatchConfig()
    instance.read_string(contents)
    return instance

from pathlib import Path
from unittest import mock

import pytest

from bandersnatch.config import BandersnatchConfig


def cfg_from_str(content: str) -> BandersnatchConfig:
    config = BandersnatchConfig()
    config.read_string(content)
    return config


def test_validated_options_are_reused() -> None:
    # leaking implementation detail: get_validated assumes its argument is a class and caches initialized objects by the class's __qualname__.
    # Mock/MagicMock raise an AttributeError for __qualname__ (and __name__) unless you specifically set the attribute.
    MockOptionsType = mock.Mock(__qualname__="MockOptionsType")

    config = BandersnatchConfig()
    options1 = config.get_validated(MockOptionsType)  # type: ignore
    options2 = config.get_validated(MockOptionsType)  # type: ignore

    # the factory method should only be called once, the first time 'get_validated' is called
    MockOptionsType.from_config_parser.assert_called_once_with(config)
    # both calls to 'get_validated' should return the same object b/c the second call returns the cached object
    assert options1 is options2


def test_validated_option_types_are_distinct() -> None:
    MockOptionsTypeA = mock.Mock(__qualname__="MockOptionsTypeA")
    MockOptionsTypeB = mock.Mock(__qualname__="MockOptionsTypeB")

    config = BandersnatchConfig()
    options_a = config.get_validated(MockOptionsTypeA)  # type: ignore
    options_b = config.get_validated(MockOptionsTypeB)  # type: ignore

    assert options_a is not options_b


@pytest.mark.parametrize(
    "option_name",
    ["test_option_name", "test-option-name", "Test-Option-Name", "TEST_OPTION_NAME"],
)
def test_option_names_are_normalized(option_name: str) -> None:
    content = f"""\
    [test]
    {option_name} = expected value
    """
    config = cfg_from_str(content)
    assert config.get("test", "test_option_name") == "expected value"


def test_supports_extended_interpolation() -> None:
    content = """\
    [paths]
    root = /opt/stuff

    [test]
    option_a = ${paths:root}
    option_b = ${option_a}/example.txt
    """
    config = cfg_from_str(content)
    assert config.get("test", "option_a") == "/opt/stuff"
    assert config.get("test", "option_b") == "/opt/stuff/example.txt"


def test_can_read_from_path(tmp_path: Path) -> None:
    content = """\
    [A]
    one = one fish
    two = two fish
    [B]
    three = red fish, blue fish
    """
    tmp_file = tmp_path / "test.cfg"
    tmp_file.write_text(content)

    config1 = BandersnatchConfig()
    config1.read_path(tmp_file)

    config2 = BandersnatchConfig()
    with tmp_file.open() as cfg_file:
        config2.read_file(cfg_file)

    assert config1.sections() == config2.sections()
    assert config1.items("A") == config2.items("A")


def test_reading_missing_path_raises(tmp_path: Path) -> None:
    no_file = tmp_path / "test.cfg"
    config = BandersnatchConfig()
    with pytest.raises(IOError):
        config.read_path(no_file)

import configparser
import os
import unittest
import warnings
from tempfile import TemporaryDirectory
from unittest import TestCase

from bandersnatch.configuration import (
    BandersnatchConfig,
    SetConfigValues,
    Singleton,
    validate_config_values,
)

try:
    import importlib.resources
except ImportError:  # For 3.6 and lesser
    import importlib
    import importlib_resources

    importlib.resources = importlib_resources


class TestBandersnatchConf(TestCase):
    """
    Tests for the BandersnatchConf singleton class
    """

    tempdir = None
    cwd = None

    def setUp(self) -> None:
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        os.chdir(self.tempdir.name)
        # Hack to ensure each test gets fresh instance if needed
        # We have a dedicated test to ensure we're creating a singleton
        Singleton._instances = {}

    def tearDown(self) -> None:
        if self.tempdir:
            assert self.cwd
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None

    def test_is_singleton(self) -> None:
        instance1 = BandersnatchConfig()
        instance2 = BandersnatchConfig()
        self.assertEqual(id(instance1), id(instance2))

    def test_single_config__default__all_sections_present(self) -> None:
        with importlib.resources.path(  # type: ignore
            "bandersnatch", "unittest.conf"
        ) as config_file:
            instance = BandersnatchConfig(str(config_file))
            # All default values should at least be present and be the write types
            for section in ["mirror", "plugins", "denylist"]:
                self.assertIn(section, instance.config.sections())

    def test_single_config__default__mirror__setting_attributes(self) -> None:
        instance = BandersnatchConfig()
        options = [option for option in instance.config["mirror"]]
        options.sort()
        self.assertListEqual(
            options,
            [
                "cleanup",
                "directory",
                "global-timeout",
                "hash-index",
                "json",
                "master",
                "stop-on-error",
                "storage-backend",
                "timeout",
                "verifiers",
                "workers",
            ],
        )

    def test_single_config__default__mirror__setting__types(self) -> None:
        """
        Make sure all default mirror settings will cast to the correct types
        """
        instance = BandersnatchConfig()
        for option, option_type in [
            ("directory", str),
            ("hash-index", bool),
            ("json", bool),
            ("master", str),
            ("stop-on-error", bool),
            ("storage-backend", str),
            ("timeout", int),
            ("global-timeout", int),
            ("workers", int),
        ]:
            self.assertIsInstance(
                option_type(instance.config["mirror"].get(option)), option_type
            )

    def test_single_config_custom_setting_boolean(self) -> None:
        with open("test.conf", "w") as testconfig_handle:
            testconfig_handle.write("[mirror]\nhash-index=false\n")
        instance = BandersnatchConfig()
        instance.config_file = "test.conf"
        instance.load_configuration()
        self.assertFalse(instance.config["mirror"].getboolean("hash-index"))

    def test_single_config_custom_setting_int(self) -> None:
        with open("test.conf", "w") as testconfig_handle:
            testconfig_handle.write("[mirror]\ntimeout=999\n")
        instance = BandersnatchConfig()
        instance.config_file = "test.conf"
        instance.load_configuration()
        self.assertEqual(int(instance.config["mirror"]["timeout"]), 999)

    def test_single_config_custom_setting_str(self) -> None:
        with open("test.conf", "w") as testconfig_handle:
            testconfig_handle.write("[mirror]\nmaster=https://foo.bar.baz\n")
        instance = BandersnatchConfig()
        instance.config_file = "test.conf"
        instance.load_configuration()
        self.assertEqual(instance.config["mirror"]["master"], "https://foo.bar.baz")

    def test_multiple_instances_custom_setting_str(self) -> None:
        with open("test.conf", "w") as testconfig_handle:
            testconfig_handle.write("[mirror]\nmaster=https://foo.bar.baz\n")
        instance1 = BandersnatchConfig()
        instance1.config_file = "test.conf"
        instance1.load_configuration()

        instance2 = BandersnatchConfig()
        self.assertEqual(instance2.config["mirror"]["master"], "https://foo.bar.baz")

    def test_validate_config_values(self) -> None:
        default_values = SetConfigValues(
            False, "", "", False, "sha256", "filesystem", False
        )
        no_options_configparser = configparser.ConfigParser()
        no_options_configparser["mirror"] = {}
        self.assertEqual(
            default_values, validate_config_values(no_options_configparser)
        )

    def test_deprecation_warning_raised(self) -> None:
        # Remove in 5.0 once we deprecate whitelist/blacklist

        config_file = "test.conf"
        instance = BandersnatchConfig()
        instance.config_file = config_file
        # Test no warning if new plugins used
        with open(config_file, "w") as f:
            f.write("[allowlist]\npackages=foo\n")
        instance.load_configuration()
        with warnings.catch_warnings(record=True) as w:
            instance.check_for_deprecations()
            self.assertEqual(len(w), 0)

        # Test warning if old plugins used
        instance.SHOWN_DEPRECATIONS = False
        with open(config_file, "w") as f:
            f.write("[whitelist]\npackages=foo\n")
        instance.load_configuration()
        with warnings.catch_warnings(record=True) as w:
            instance.check_for_deprecations()
            instance.check_for_deprecations()
            # Assert we only throw 1 warning
            self.assertEqual(len(w), 1)


if __name__ == "__main__":
    unittest.main()

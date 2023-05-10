import configparser
import importlib.resources
import os
import unittest
from tempfile import TemporaryDirectory
from unittest import TestCase

from bandersnatch.configuration import (
    BandersnatchConfig,
    SetConfigValues,
    Singleton,
    validate_config_values,
)
from bandersnatch.simple import SimpleFormat


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
        config_file = str(importlib.resources.files("bandersnatch") / "unittest.conf")
        instance = BandersnatchConfig(str(config_file))
        # All default values should at least be present and be the write types
        for section in ["mirror", "plugins", "blocklist"]:
            self.assertIn(section, instance.config.sections())

    def test_single_config__default__mirror__setting_attributes(self) -> None:
        instance = BandersnatchConfig()
        options = [option for option in instance.config["mirror"]]
        options.sort()
        self.assertListEqual(
            options,
            [
                "cleanup",
                "compare-method",
                "directory",
                "global-timeout",
                "hash-index",
                "json",
                "master",
                "release-files",
                "simple-format",
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
            ("compare-method", str),
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
            False,
            "",
            "",
            False,
            "sha256",
            "filesystem",
            False,
            True,
            "hash",
            "",
            False,
            SimpleFormat.ALL,
        )
        no_options_configparser = configparser.ConfigParser()
        no_options_configparser["mirror"] = {}
        self.assertEqual(
            default_values, validate_config_values(no_options_configparser)
        )

    def test_validate_config_values_release_files_false_sets_root_uri(self) -> None:
        default_values = SetConfigValues(
            False,
            "https://files.pythonhosted.org",
            "",
            False,
            "sha256",
            "filesystem",
            False,
            False,
            "hash",
            "",
            False,
            SimpleFormat.ALL,
        )
        release_files_false_configparser = configparser.ConfigParser()
        release_files_false_configparser["mirror"] = {"release-files": "false"}
        self.assertEqual(
            default_values, validate_config_values(release_files_false_configparser)
        )

    def test_validate_config_values_download_mirror_false_sets_no_fallback(
        self,
    ) -> None:
        default_values = SetConfigValues(
            False,
            "",
            "",
            False,
            "sha256",
            "filesystem",
            False,
            True,
            "hash",
            "",
            False,
            SimpleFormat.ALL,
        )
        release_files_false_configparser = configparser.ConfigParser()
        release_files_false_configparser["mirror"] = {
            "download-mirror-no-fallback": "true",
        }
        self.assertEqual(
            default_values, validate_config_values(release_files_false_configparser)
        )


if __name__ == "__main__":
    unittest.main()

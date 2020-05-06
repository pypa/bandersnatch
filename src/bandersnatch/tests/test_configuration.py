import os
import unittest
from tempfile import TemporaryDirectory
from unittest import TestCase

from bandersnatch.configuration import BandersnatchConfig, Singleton

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

    def setUp(self):
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        os.chdir(self.tempdir.name)
        # Hack to ensure each test gets fresh instance if needed
        # We have a dedicated test to ensure we're creating a singleton
        Singleton._instances = {}

    def tearDown(self):
        if self.tempdir:
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None

    def test_is_singleton(self):
        instance1 = BandersnatchConfig()
        instance2 = BandersnatchConfig()
        self.assertEqual(id(instance1), id(instance2))

    def test_single_config__default__all_sections_present(self):
        with importlib.resources.path("bandersnatch", "unittest.conf") as config_file:
            instance = BandersnatchConfig(str(config_file))
            # All default values should at least be present and be the write types
            for section in ["mirror", "plugins", "blacklist"]:
                self.assertIn(section, instance.config.sections())

    def test_single_config__default__mirror__setting_attributes(self):
        instance = BandersnatchConfig()
        options = [option for option in instance.config["mirror"]]
        options.sort()
        self.assertListEqual(
            options,
            [
                "cleanup",
                "directory",
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

    def test_single_config__default__mirror__setting__types(self):
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
            ("workers", int),
        ]:
            self.assertIsInstance(
                option_type(instance.config["mirror"].get(option)), option_type
            )

    def test_single_config_custom_setting_boolean(self):
        with open("test.conf", "w") as testconfig_handle:
            testconfig_handle.write("[mirror]\nhash-index=false\n")
        instance = BandersnatchConfig()
        instance.config_file = "test.conf"
        instance.load_configuration()
        self.assertFalse(instance.config["mirror"].getboolean("hash-index"))

    def test_single_config_custom_setting_int(self):
        with open("test.conf", "w") as testconfig_handle:
            testconfig_handle.write("[mirror]\ntimeout=999\n")
        instance = BandersnatchConfig()
        instance.config_file = "test.conf"
        instance.load_configuration()
        self.assertEqual(int(instance.config["mirror"]["timeout"]), 999)

    def test_single_config_custom_setting_str(self):
        with open("test.conf", "w") as testconfig_handle:
            testconfig_handle.write("[mirror]\nmaster=https://foo.bar.baz\n")
        instance = BandersnatchConfig()
        instance.config_file = "test.conf"
        instance.load_configuration()
        self.assertEqual(instance.config["mirror"]["master"], "https://foo.bar.baz")

    def test_multiple_instances_custom_setting_str(self):
        with open("test.conf", "w") as testconfig_handle:
            testconfig_handle.write("[mirror]\nmaster=https://foo.bar.baz\n")
        instance1 = BandersnatchConfig()
        instance1.config_file = "test.conf"
        instance1.load_configuration()

        instance2 = BandersnatchConfig()
        self.assertEqual(instance2.config["mirror"]["master"], "https://foo.bar.baz")


if __name__ == "__main__":
    unittest.main()

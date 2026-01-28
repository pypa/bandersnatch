import configparser
import importlib.resources
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from bandersnatch.config.diff_file_reference import eval_config_reference
from bandersnatch.configuration import (
    BandersnatchConfig,
    SetConfigValues,
    Singleton,
    validate_config_values,
)
from bandersnatch.simple import SimpleDigest, SimpleFormat


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
        config_file = Path(
            str(importlib.resources.files("bandersnatch") / "unittest.conf")
        )
        instance = BandersnatchConfig(config_file)
        # All default values should at least be present and be the write types
        for section in ["mirror", "plugins", "blocklist"]:
            self.assertIn(section, instance.sections())

    def test_single_config__default__mirror__setting_attributes(self) -> None:
        instance = BandersnatchConfig()
        options = {option for option in instance["mirror"]}
        self.assertSetEqual(
            options,
            {
                "allow-non-https",
                "api-method",
                "cleanup",
                "compare-method",
                "diff-append-epoch",
                "diff-file",
                "digest_name",
                "download-mirror",
                "download-mirror-no-fallback",
                "global-timeout",
                "hash-index",
                "json",
                "keep-index-versions",
                "log-config",
                "master",
                "proxy",
                "release-files",
                "root_uri",
                "simple-format",
                "stop-on-error",
                "storage-backend",
                "storage-filesystem-manage-permissions",
                "timeout",
                "verifiers",
                "workers",
            },
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
            ("api-method", str),
        ]:
            self.assertIsInstance(
                option_type(instance["mirror"].get(option)), option_type
            )

    def test_single_config_custom_setting_boolean(self) -> None:
        instance = BandersnatchConfig()
        instance.read_string("[mirror]\nhash-index=false\n")

        self.assertFalse(instance["mirror"].getboolean("hash-index"))

    def test_single_config_custom_setting_int(self) -> None:
        instance = BandersnatchConfig()
        instance.read_string("[mirror]\ntimeout=999\n")

        self.assertEqual(int(instance["mirror"]["timeout"]), 999)

    def test_single_config_custom_setting_str(self) -> None:
        instance = BandersnatchConfig()
        instance.read_string("[mirror]\nmaster=https://foo.bar.baz\n")

        self.assertEqual(instance["mirror"]["master"], "https://foo.bar.baz")

    def test_multiple_instances_custom_setting_str(self) -> None:
        instance1 = BandersnatchConfig()
        instance1.read_string("[mirror]\nmaster=https://foo.bar.baz\n")

        instance2 = BandersnatchConfig()

        self.assertEqual(instance2["mirror"]["master"], "https://foo.bar.baz")

    def test_validate_config_values(self) -> None:
        default_values = SetConfigValues(
            False,
            "",
            "",
            False,
            SimpleDigest.SHA256,
            "filesystem",
            False,
            True,
            "hash",
            "",
            False,
            SimpleFormat.ALL,
            "simple",
        )
        no_options_configparser = BandersnatchConfig(load_defaults=True)
        self.assertEqual(
            default_values, validate_config_values(no_options_configparser)
        )

    def test_validate_config_values_release_files_false_sets_root_uri(self) -> None:
        default_values = SetConfigValues(
            False,
            "https://files.pythonhosted.org",
            "",
            False,
            SimpleDigest.SHA256,
            "filesystem",
            False,
            False,
            "hash",
            "",
            False,
            SimpleFormat.ALL,
            "simple",
        )
        release_files_false_configparser = BandersnatchConfig(load_defaults=True)
        release_files_false_configparser["mirror"].update({"release-files": "false"})
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
            SimpleDigest.SHA256,
            "filesystem",
            False,
            True,
            "hash",
            "",
            False,
            SimpleFormat.ALL,
            "simple",
        )
        release_files_false_configparser = BandersnatchConfig(load_defaults=True)
        release_files_false_configparser["mirror"].update(
            {
                "download-mirror-no-fallback": "true",
            }
        )
        self.assertEqual(
            default_values, validate_config_values(release_files_false_configparser)
        )

    def test_validate_config_values_api_method_simple(self) -> None:
        """Test that api_method='simple' is accepted and validated."""
        simple_api_values = SetConfigValues(
            False,
            "",
            "",
            False,
            SimpleDigest.SHA256,
            "filesystem",
            False,
            True,
            "hash",
            "",
            False,
            SimpleFormat.ALL,
            "simple",
        )
        simple_api_config = BandersnatchConfig(load_defaults=True)
        simple_api_config["mirror"].update({"api-method": "simple"})
        self.assertEqual(simple_api_values, validate_config_values(simple_api_config))

    def test_validate_config_values_api_method_xmlrpc(self) -> None:
        """Test that api_method='xmlrpc' is accepted and validated."""
        xmlrpc_api_values = SetConfigValues(
            False,
            "",
            "",
            False,
            SimpleDigest.SHA256,
            "filesystem",
            False,
            True,
            "hash",
            "",
            False,
            SimpleFormat.ALL,
            "xmlrpc",
        )
        xmlrpc_api_config = BandersnatchConfig(load_defaults=True)
        xmlrpc_api_config["mirror"].update({"api-method": "xmlrpc"})
        self.assertEqual(xmlrpc_api_values, validate_config_values(xmlrpc_api_config))

    def test_validate_config_values_api_method_invalid(self) -> None:
        """Test that invalid api_method raises ValueError."""
        invalid_api_config = BandersnatchConfig(load_defaults=True)
        invalid_api_config["mirror"].update({"api-method": "invalid"})
        with self.assertRaises(ValueError) as context:
            validate_config_values(invalid_api_config)
        self.assertIn("api-method invalid is not supported", str(context.exception))
        self.assertIn("('simple', 'xmlrpc')", str(context.exception))

    def test_validate_config_values_api_method_defaults_to_simple(self) -> None:
        """Test that api_method defaults to 'simple' when not specified."""
        config = BandersnatchConfig(load_defaults=True)
        # Remove the api-method config if it exists
        if config.has_option("mirror", "api-method"):
            config.remove_option("mirror", "api-method")
        result = validate_config_values(config)
        self.assertEqual(result.api_method, "simple")

    def test_validate_config_diff_file_reference(self) -> None:
        diff_file_test_cases = [
            (
                {
                    "mirror": {
                        "directory": "/test",
                        "diff-file": r"{{mirror_directory}}",
                    }
                },
                "/test",
            ),
            (
                {
                    "mirror": {
                        "directory": "/test",
                        "diff-file": r"{{ mirror_directory }}",
                    }
                },
                "/test",
            ),
            (
                {
                    "mirror": {
                        "directory": "/test",
                        "diff-file": r"{{ mirror_directory }}/diffs/new-files",
                    }
                },
                "/test/diffs/new-files",
            ),
            (
                {
                    "strings": {"test": "TESTING"},
                    "mirror": {"diff-file": r"/var/log/{{ strings_test }}"},
                },
                "/var/log/TESTING",
            ),
            (
                {
                    "strings": {"test": "TESTING"},
                    "mirror": {"diff-file": r"/var/log/{{ strings_test }}/diffs"},
                },
                "/var/log/TESTING/diffs",
            ),
        ]

        for cfg_data, expected in diff_file_test_cases:
            with self.subTest(
                diff_file=cfg_data["mirror"]["diff-file"],
                expected=expected,
                cfg_data=cfg_data,
            ):
                cfg = BandersnatchConfig(load_defaults=True)
                cfg.read_dict(cfg_data)
                config_values = validate_config_values(cfg)
                self.assertIsInstance(config_values.diff_file_path, str)
                self.assertEqual(config_values.diff_file_path, expected)

    def test_invalid_diff_file_reference_throws_exception(self) -> None:
        invalid_diff_file_cases = [
            (
                r"{{ missing.underscore }}/foo",
                "Unable to parse config option reference",
            ),
            (r"/var/{{ mirror_woops }}/foo", "No option 'woops' in section: 'mirror'"),
        ]

        for diff_file_val, expected_error in invalid_diff_file_cases:
            with self.subTest(diff_file=diff_file_val, expected_error=expected_error):
                cfg = configparser.ConfigParser()
                cfg.read_dict({"mirror": {"diff-file": diff_file_val}})
                self.assertRaisesRegex(
                    ValueError,
                    expected_error,
                    eval_config_reference,
                    cfg,
                    diff_file_val,
                )


if __name__ == "__main__":
    unittest.main()

import os
from tempfile import TemporaryDirectory
from unittest import TestCase

from bandersnatch.configuration import BandersnatchConfig


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

    def tearDown(self):
        if self.tempdir:
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None

    def test__is_singleton(self):
        instance1 = BandersnatchConfig()
        instance2 = BandersnatchConfig()
        self.assertEqual(id(instance1), id(instance2))

    def test__single_config__default__all_sections_present(self):
        instance = BandersnatchConfig()
        # All default values should at least be present and be the write types
        for section in ['mirror', 'blacklist']:
            self.assertIn(section, instance.config.sections())

    def test__single_config__default__mirror__setting_attributes(self):
        instance = BandersnatchConfig()
        options = [option for option in instance.config['mirror']]
        options.sort()
        self.assertListEqual(
            options,
            [
                'delete-packages', 'directory', 'hash-index', 'json', 'master',
                'stop-on-error', 'timeout', 'workers'
            ]
        )

    def test__single_config__default__mirror__setting__types(self):
        """
        Make sure all default mirror settings will cast to the correct types
        """
        instance = BandersnatchConfig()
        for option, option_type in [
            ('delete-packages', bool),
            ('directory', str),
            ('hash-index', bool),
            ('json', bool),
            ('master', str),
            ('stop-on-error', bool),
            ('timeout', int),
            ('workers', int)
        ]:
            self.assertIsInstance(
                option_type(instance.config['mirror'].get(option)), option_type
            )

    def test__single_config__custom__setting__boolean(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("[mirror]\ndelete-packages=false\n")
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()
        self.assertFalse(
            instance.config['mirror'].getboolean('delete-packages')
        )

    def test__single_config__custom__setting__int(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("[mirror]\ntimeout=999\n")
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()
        self.assertEqual(int(instance.config['mirror']['timeout']), 999)

    def test__single_config__custom__setting__str(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("[mirror]\nmaster=https://foo.bar.baz\n")
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()
        self.assertEqual(
            instance.config['mirror']['master'], 'https://foo.bar.baz'
        )

import os
from collections import defaultdict
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror


class TestWhitelistProject(TestCase):
    """
    Tests for the bandersnatch filtering classes
    """
    tempdir = None
    cwd = None

    def setUp(self):
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        bandersnatch.filter.loaded_filter_plugins = defaultdict(list)
        os.chdir(self.tempdir.name)

    def tearDown(self):
        if self.tempdir:
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None

    def test__plugin__loads__explicitly_enabled(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("""\
[blacklist]
plugins =
    whitelist_project
""")
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()

        plugins = bandersnatch.filter.filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertListEqual(names, ['whitelist_project'])
        self.assertEqual(len(plugins), 1)

    def test__plugin__loads__default(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("""\
[blacklist]
""")
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()

        plugins = bandersnatch.filter.filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertIn('whitelist_project', names)

    def test__filter__matches__package(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("""\
[blacklist]
plugins =
    whitelist_project

[whitelist]
packages =
    foo
""")
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()

        mirror = Mirror('.', Master(url='https://foo.bar.com'))
        mirror.packages_to_sync = {'foo': {}}
        mirror._filter_packages()

        self.assertIn('foo', mirror.packages_to_sync.keys())

    def test__filter__nomatch_package(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("""\
[blacklist]
plugins =
    whitelist_project

[whitelist]
packages =
    foo
""")
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()

        mirror = Mirror('.', Master(url='https://foo.bar.com'))
        mirror.packages_to_sync = {'foo': {}, 'foo2': {}}
        mirror._filter_packages()

        self.assertIn('foo', mirror.packages_to_sync.keys())
        self.assertNotIn('foo2', mirror.packages_to_sync.keys())

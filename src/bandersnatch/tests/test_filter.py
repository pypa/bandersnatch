import os
from collections import defaultdict
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.filter import filter_project_plugins, filter_release_plugins


class TestBandersnatchFilter(TestCase):
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

    def test__filter_project_plugins__default__loads(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("""\
[blacklist]
""")
        builtin_plugin_names = ['blacklist_project', 'whitelist_project']
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()

        plugins = filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        for name in builtin_plugin_names:
            self.assertIn(name, names)

    def test__filter_release_plugins__default__loads(self):
        with open('test.conf', 'w') as testconfig_handle:
            testconfig_handle.write("""\
[blacklist]
""")
        builtin_plugin_names = ['blacklist_release']
        instance = BandersnatchConfig()
        instance.config_file = 'test.conf'
        instance.load_configuration()

        plugins = filter_release_plugins()
        names = [plugin.name for plugin in plugins]
        for name in builtin_plugin_names:
            self.assertIn(name, names)

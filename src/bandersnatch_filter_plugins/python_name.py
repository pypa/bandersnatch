import logging
import re
from typing import List, Pattern
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from bandersnatch.filter import FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class RequiresPythonReleaseFilter(FilterReleasePlugin):
    """
    Plugin to download only package version compatible with the listed python versions.
    """

    name = "requires_python_release"
    specifier = SpecifierSet()
    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config = self.configuration["python"]["requires_python"]
        except KeyError:
            return
        else:
            if not self.specifier:
                self.specifier=SpecifierSet(config)

                logger.info(f"Initialized requires_python release plugin with {self.specifier}")

    def filter(self, info, releases):
        """
        Remove all release versions that don't match any of the specificed python version patterns.
        """
        for version in list(releases.keys()):
            release = releases[version]
            if "requires_python" in release and release["requires_python"] is not None:
                if self.specifier.__and__(SpecifierSet(release["requires_python"])) is not None:
                    continue
                else:
                    del releases[version]

class PythonVersionReleaseFilter(FilterReleasePlugin):
    """
    Plugin to download only package version compatible with the listed python versions.
    """

    name = "python_version_release"
    specifier = SpecifierSet()
    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config = self.configuration["python"]["python_version"]
        except KeyError:
            return
        else:
            if not self.specifier:
                self.specifier=SpecifierSet(config)

                logger.info(f"Initialized python_version release plugin with {self.specifier}")

    def filter(self, info, releases):
        """
        Remove all release versions that don't match any of the specificed python version patterns.
        """
        for version in list(releases.keys()):
            release = releases[version]
            if "python_version" in release and release["python_version"] is not None:
                if release["python_version"] is "source":
                    continue
                elif self.specifier.contains(release["python_version"]) is not None:
                    continue
                else:
                    del releases[version]




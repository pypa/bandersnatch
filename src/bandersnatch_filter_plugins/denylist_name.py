import logging
from typing import Any, Dict, List, Set

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

from bandersnatch.filter import FilterProjectPlugin, FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class DenyListProject(FilterProjectPlugin):
    name = "denylist_project"
    deprecated_name = "blacklist_project"
    # Requires iterable default
    denylist_package_names: List[str] = []

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin
        """
        # Generate a list of denylisted packages from the configuration and
        # store it into self.denylist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        if not self.denylist_package_names:
            self.denylist_package_names = self._determine_filtered_package_names()
            logger.info(
                f"Initialized project plugin {self.name}, filtering "
                + f"{self.denylist_package_names}"
            )

    def _determine_filtered_package_names(self) -> List[str]:
        """
        Return a list of package names to be filtered base on the configuration
        file.
        """
        # This plugin only processes packages, if the line in the packages
        # configuration contains a PEP440 specifier it will be processed by the
        # denylist release filter.  So we need to remove any packages that
        # are not applicable for this plugin.
        filtered_packages: Set[str] = set()
        try:
            lines = self.denylist["packages"]
            package_lines = lines.split("\n")
        except KeyError:
            package_lines = []
        for package_line in package_lines:
            package_line = package_line.strip()
            if not package_line or package_line.startswith("#"):
                continue
            package_requirement = Requirement(package_line)
            if package_requirement.specifier:
                continue
            if package_requirement.name != package_line:
                logger.debug(
                    "Package line %r does not requirement name %r",
                    package_line,
                    package_requirement.name,
                )
                continue
            filtered_packages.add(package_line)
        logger.debug("Project denylist is %r", list(filtered_packages))
        return list(filtered_packages)

    def filter(self, metadata: Dict) -> bool:
        return not self.check_match(name=metadata["info"]["name"])

    def check_match(self, **kwargs: Any) -> bool:
        """
        Check if the package name matches against a project that is denylisted
        in the configuration.

        Parameters
        ==========
        name: str
            The normalized package name of the package/project to check against
            the denylist.

        Returns
        =======
        bool:
            True if it matches, False otherwise.
        """
        name = kwargs.get("name", None)
        if not name:
            return False

        if name in self.denylist_package_names:
            logger.info(f"Package {name!r} is denylisted")
            return True
        return False


class DenyListRelease(FilterReleasePlugin):
    name = "denylist_release"
    deprecated_name = "blacklist_release"
    # Requires iterable default
    denylist_package_names: List[Requirement] = []

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin
        """
        # Generate a list of denylisted packages from the configuration and
        # store it into self.denylist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        if not self.denylist_package_names:
            self.denylist_release_requirements = (
                self._determine_filtered_package_requirements()
            )
            logger.info(
                f"Initialized release plugin {self.name}, filtering "
                + f"{self.denylist_release_requirements}"
            )

    def _determine_filtered_package_requirements(self) -> List[Requirement]:
        """
        Parse the configuration file for [denylist]packages

        Returns
        -------
        list of packaging.requirements.Requirement
            For all PEP440 package specifiers
        """
        filtered_requirements: Set[Requirement] = set()
        try:
            lines = self.denylist["packages"]
            package_lines = lines.split("\n")
        except KeyError:
            package_lines = []
        for package_line in package_lines:
            package_line = package_line.strip()
            if not package_line or package_line.startswith("#"):
                continue
            filtered_requirements.add(Requirement(package_line))
        return list(filtered_requirements)

    def filter(self, metadata: Dict) -> bool:
        """
        Returns False if version fails the filter,
        i.e. matches a blocklist version specifier
        """
        name = metadata["info"]["name"]
        version = metadata["version"]
        return not self._check_match(name, version)

    def _check_match(self, name: str, version_string: str) -> bool:
        """
        Check if the package name and version matches against a denylisted
        package version specifier.

        Parameters
        ==========
        name: str
            Package name

        version: str
            Package version

        Returns
        =======
        bool:
            True if it matches, False otherwise.
        """
        if not name or not version_string:
            return False

        try:
            version = Version(version_string)
        except InvalidVersion:
            logger.debug(f"Package {name}=={version_string} has an invalid version")
            return False
        for requirement in self.denylist_release_requirements:
            if name != requirement.name:
                continue
            if version in requirement.specifier:
                logger.debug(
                    f"MATCH: Release {name}=={version} matches specifier "
                    f"{requirement.specifier}"
                )
                return True
        return False

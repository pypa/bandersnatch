import logging
from typing import Any, Dict, List, Set

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from bandersnatch.filter import FilterProjectPlugin, FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class BlockListProject(FilterProjectPlugin):
    name = "blocklist_project"
    # Requires iterable default
    blocklist_package_names: List[str] = []

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin
        """
        # Generate a list of blocklisted packages from the configuration and
        # store it into self.blocklist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        if not self.blocklist_package_names:
            self.blocklist_package_names = self._determine_filtered_package_names()
            logger.info(
                f"Initialized project plugin {self.name}, filtering "
                + f"{self.blocklist_package_names}"
            )

    def _determine_filtered_package_names(self) -> List[str]:
        """
        Return a list of package names to be filtered base on the configuration
        file.
        """
        # This plugin only processes packages, if the line in the packages
        # configuration contains a PEP440 specifier it will be processed by the
        # blocklist release filter.  So we need to remove any packages that
        # are not applicable for this plugin.
        filtered_packages: Set[str] = set()
        try:
            lines = self.blocklist["packages"]
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
                    "Package line %r does not match requirement name %r",
                    package_line,
                    package_requirement.name,
                )
                continue
            filtered_packages.add(canonicalize_name(package_requirement.name))
        logger.debug("Project blocklist is %r", list(filtered_packages))
        return list(filtered_packages)

    def filter(self, metadata: Dict) -> bool:
        return not self.check_match(name=metadata["info"]["name"])

    def check_match(self, **kwargs: Any) -> bool:
        """
        Check if the package name matches against a project that is blocklisted
        in the configuration.

        Parameters
        ==========
        name: str
            The normalized package name of the package/project to check against
            the blocklist.

        Returns
        =======
        bool:
            True if it matches, False otherwise.
        """
        name = kwargs.get("name", None)
        if not name:
            return False

        if canonicalize_name(name) in self.blocklist_package_names:
            logger.info(f"Package {name!r} is blocklisted")
            return True
        return False


class BlockListRelease(FilterReleasePlugin):
    name = "blocklist_release"
    # Requires iterable default
    blocklist_package_names: List[Requirement] = []

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin
        """
        # Generate a list of blocklisted packages from the configuration and
        # store it into self.blocklist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        if not self.blocklist_package_names:
            self.blocklist_release_requirements = (
                self._determine_filtered_package_requirements()
            )
            logger.info(
                f"Initialized release plugin {self.name}, filtering "
                + f"{self.blocklist_release_requirements}"
            )

    def _determine_filtered_package_requirements(self) -> List[Requirement]:
        """
        Parse the configuration file for [blocklist]packages

        Returns
        -------
        list of packaging.requirements.Requirement
            For all PEP440 package specifiers
        """
        filtered_requirements: Set[Requirement] = set()
        try:
            lines = self.blocklist["packages"]
            package_lines = lines.split("\n")
        except KeyError:
            package_lines = []
        for package_line in package_lines:
            package_line = package_line.strip()
            if not package_line or package_line.startswith("#"):
                continue
            requirement = Requirement(package_line)
            requirement.name = canonicalize_name(requirement.name)
            requirement.specifier.prereleases = True
            filtered_requirements.add(requirement)
        return list(filtered_requirements)

    def filter(self, metadata: Dict) -> bool:
        """
        Returns False if version fails the filter,
        i.e. matches a blocklist version specifier
        """
        name = metadata["info"]["name"]
        version = metadata["version"]
        return not self._check_match(canonicalize_name(name), version)

    def _check_match(self, name: str, version_string: str) -> bool:
        """
        Check if the package name and version matches against a blocklisted
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
        for requirement in self.blocklist_release_requirements:
            if name != requirement.name:
                continue
            if version in requirement.specifier:
                logger.debug(
                    f"MATCH: Release {name}=={version} matches specifier "
                    f"{requirement.specifier}"
                )
                return True
        return False

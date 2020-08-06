import logging
from typing import Any, Dict, List, Set

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from bandersnatch.filter import FilterProjectPlugin, FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class AllowListProject(FilterProjectPlugin):
    name = "allowlist_project"
    deprecated_name = "whitelist_project"
    # Requires iterable default
    allowlist_package_names: List[str] = []

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin
        """
        # Generate a list of allowlisted packages from the configuration and
        # store it into self.allowlist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        if not self.allowlist_package_names:
            self.allowlist_package_names = self._determine_unfiltered_package_names()
            logger.info(
                f"Initialized project plugin {self.name}, filtering "
                + f"{self.allowlist_package_names}"
            )

    def _determine_unfiltered_package_names(self) -> List[str]:
        """
        Return a list of package names to be filtered base on the configuration
        file.
        """
        # This plugin only processes packages, if the line in the packages
        # configuration contains a PEP440 specifier it will be processed by the
        # allowlist release filter.  So we need to remove any packages that
        # are not applicable for this plugin.
        unfiltered_packages: Set[str] = set()
        try:
            lines = self.allowlist["packages"]
            package_lines = lines.split("\n")
        except KeyError:
            package_lines = []
        for package_line in package_lines:
            package_line = canonicalize_name(package_line.strip())
            if not package_line or package_line.startswith("#"):
                continue
            unfiltered_packages.add(Requirement(package_line).name)
        return list(unfiltered_packages)

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
        if not self.allowlist_package_names:
            return False

        name = kwargs.get("name", None)
        if not name:
            return False

        if canonicalize_name(name) in self.allowlist_package_names:
            logger.info(f"Package {name!r} is allowlisted")
            return False
        return True


class AllowListRelease(FilterReleasePlugin):
    name = "allowlist_release"
    deprecated_name = "whitelist_release"
    # Requires iterable default
    allowlist_package_names: List[Requirement] = []

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin
        """
        # Generate a list of allowlisted packages from the configuration and
        # store it into self.allowlist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        if not self.allowlist_package_names:
            self.allowlist_release_requirements = (
                self._determine_filtered_package_requirements()
            )
            logger.info(
                f"Initialized release plugin {self.name}, filtering "
                + f"{self.allowlist_release_requirements}"
            )

    def _determine_filtered_package_requirements(self) -> List[Requirement]:
        """
        Parse the configuration file for [allowlist]packages

        Returns
        -------
        list of packaging.requirements.Requirement
            For all PEP440 package specifiers
        """
        filtered_requirements: Set[Requirement] = set()
        try:
            lines = self.allowlist["packages"]
            package_lines = lines.split("\n")
        except KeyError:
            package_lines = []
        for package_line in package_lines:
            package_line = package_line.strip()
            if not package_line or package_line.startswith("#"):
                continue
            requirement = Requirement(package_line)
            requirement.specifier.prereleases = True
            filtered_requirements.add(requirement)
        return list(filtered_requirements)

    def filter(self, metadata: Dict) -> bool:
        """
        Returns False if version fails the filter,
        i.e. doesn't matches an allowlist version specifier
        """
        name = metadata["info"]["name"]
        version = metadata["version"]
        return self._check_match(name, version)

    def _check_match(self, name: str, version_string: str) -> bool:
        """
        Check if the package name and version matches against an allowlisted
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
        for requirement in self.allowlist_release_requirements:
            if name != requirement.name:
                continue
            if version in requirement.specifier:
                logger.debug(
                    f"MATCH: Release {name}=={version} matches specifier "
                    f"{requirement.specifier}"
                )
                return True
        return False

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Set

if TYPE_CHECKING:
    from configparser import SectionProxy

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from bandersnatch.filter import FilterProjectPlugin, FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class AllowListProject(FilterProjectPlugin):
    name = "allowlist_project"
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
            package_line = package_line.strip()
            if not package_line or package_line.startswith("#"):
                continue
            package_line, *_ = package_line.split("#", maxsplit=1)
            unfiltered_packages.add(
                canonicalize_name(Requirement(package_line.strip()).name)
            )
        return list(unfiltered_packages)

    def filter(self, metadata: Dict) -> bool:
        return not self.check_match(name=metadata["info"]["name"])

    def check_match(self, **kwargs: Any) -> bool:
        """
        Check if the package name matches against a project that is allowlisted
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


def get_requirement_files(allowlist: "SectionProxy") -> Iterator[Path]:
    try:
        requirements_path = Path(allowlist["requirements_path"])
    except KeyError:
        requirements_path = Path()

    try:
        lines = allowlist["requirements"]
        requirements_lines = lines.split("\n")
    except KeyError:
        requirements_lines = []

    for requirement_line in requirements_lines:
        requirement_line = requirement_line.strip()
        if not requirement_line or requirement_line.startswith("#"):
            continue
        requirement_line, *_ = requirement_line.split("#", maxsplit=1)
        requirement = requirement_line.strip()
        logger.info("considering %s", requirements_path / requirement)
        yield requirements_path / requirement


def _parse_package_lines(package_lines: List[str]) -> Set[Requirement]:
    """Parse a requirement line

    ignores commented line
    and inline comments
    """
    filtered_requirements: Set[Requirement] = set()
    for package_line in package_lines:
        package_line = package_line.strip()
        if not package_line or package_line.startswith("#"):
            continue
        package_line, *_ = package_line.split("#", maxsplit=1)
        requirement = Requirement(package_line.strip())
        requirement.name = canonicalize_name(requirement.name)
        requirement.specifier.prereleases = True
        filtered_requirements.add(requirement)
    return filtered_requirements


class AllowListRequirements(AllowListProject):
    name = "project_requirements"

    def _determine_unfiltered_package_names(self) -> List[str]:
        """
        Return a list of package names to be filtered base on the configuration
        file.
        """
        filtered_requirements: Set[Requirement] = set()
        try:
            filepaths = get_requirement_files(self.allowlist)
        except KeyError:
            return []

        for filepath in filepaths:
            with open(filepath) as req_fh:
                filtered_requirements |= _parse_package_lines(req_fh.readlines())
        return list(req.name for req in filtered_requirements)


class AllowListRelease(FilterReleasePlugin):
    name = "allowlist_release"
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
        Parse the configuration file for

        [allowlist]
        packages

        Returns
        -------
        list of packaging.requirements.Requirement
            For all PEP440 package specifiers
        """
        try:
            lines = self.allowlist["packages"]
            package_lines = lines.split("\n")
        except KeyError:
            package_lines = []
        return list(_parse_package_lines(package_lines))

    def filter(self, metadata: Dict) -> bool:
        """
        Returns False if version fails the filter,
        i.e. doesn't matches an allowlist version specifier
        """
        name = metadata["info"]["name"]
        version = metadata["version"]
        return self._check_match(canonicalize_name(name), version)

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


class AllowListRequirementsPinned(AllowListRelease):
    name = "project_requirements_pinned"

    def _determine_filtered_package_requirements(self) -> List[Requirement]:
        """
        Parse the configuration file for
        [allowlist]
        requirements_path = /where_they_are
        requirements =
            requirements.txt

        Returns
        -------
        list of packaging.requirements.Requirement
            For all PEP440 package specifiers
        """
        filtered_requirements: Set[Requirement] = set()

        try:
            filepaths = get_requirement_files(self.allowlist)
        except KeyError:
            return []
        for filepath in filepaths:
            with open(filepath) as req_fh:
                filtered_requirements |= _parse_package_lines(req_fh.readlines())
        return list(filtered_requirements)

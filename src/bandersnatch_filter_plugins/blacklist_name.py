import logging

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

from bandersnatch.filter import FilterProjectPlugin, FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class BlacklistProject(FilterProjectPlugin):
    name = "blacklist_project"

    def initialize_plugin(self):
        """
        Initialize the plugin
        """
        # Generate a list of blacklisted packages from the configuration and
        # store it into self.blacklist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        self.blacklist_package_names = self._determine_filtered_package_names()
        logger.debug(
            f"Initialized project plugin {self.name!r}, filtering "
            f"{self.blacklist_package_names!r}"
        )

    def _determine_filtered_package_names(self):
        """
        Return a list of package names to be filtered base on the configuration
        file.
        """
        # This plugin only processes packages, if the line in the packages
        # configuration contains a PEP440 specifier it will be processed by the
        # blacklist release filter.  So we need to remove any packages that
        # are not applicable for this plugin.
        filtered_packages = set()
        try:
            lines = self.configuration["blacklist"]["packages"]
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
        logger.debug("Project blacklist is %r", list(filtered_packages))
        return list(filtered_packages)

    def check_match(self, **kwargs):
        """
        Check if the package name matches against a project that is blacklisted
        in the configuration.

        Parameters
        ==========
        name: str
            The normalized package name of the package/project to check against
            the blacklist.

        Returns
        =======
        bool:
            True if it matches, False otherwise.
        """
        name = kwargs.get("name", None)
        if not name:
            return False

        if name in self.blacklist_package_names:
            logger.info(f"Package {name!r} is blacklisted")
            return True
        return False


class BlacklistRelease(FilterReleasePlugin):
    name = "blacklist_release"

    def initialize_plugin(self):
        """
        Initialize the plugin
        """
        # Generate a list of blacklisted packages from the configuration and
        # store it into self.blacklist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        self.blacklist_release_requirements = (
            self._determine_filtered_package_requirements()
        )
        logger.debug(
            f"Initialized release plugin {self.name!r}, filtering "
            f"{self.blacklist_release_requirements!r}"
        )

    def _determine_filtered_package_requirements(self):
        """
        Parse the configuration file for [blacklist]packages

        Returns
        -------
        list of packaging.requirements.Requirement
            For all PEP440 package specifiers
        """
        filtered_requirements = set()
        try:
            lines = self.configuration["blacklist"]["packages"]
            package_lines = lines.split("\n")
        except KeyError:
            package_lines = []
        for package_line in package_lines:
            package_line = package_line.strip()
            if not package_line or package_line.startswith("#"):
                continue
            filtered_requirements.add(Requirement(package_line))
        return list(filtered_requirements)

    def check_match(self, **kwargs):
        """
        Check if the package name and version matches against a blacklisted
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
        name = kwargs.get("name", None)
        version_string = kwargs.get("version", None)

        if not name or not version_string:
            return False

        try:
            version = Version(version_string)
        except InvalidVersion:
            logger.debug(f"Package {name}=={version_string} has an invalid version")
            return False
        for requirement in self.blacklist_release_requirements:
            if name != requirement.name:
                continue
            if version in requirement.specifier:
                logger.debug(
                    f"MATCH: Release {name}=={version} matches specifier "
                    f"{requirement.specifier}"
                )
                return True
        return False

import logging

from bandersnatch.filter import FilterProjectPlugin

logger = logging.getLogger("bandersnatch")


class WhitelistProject(FilterProjectPlugin):
    name = "whitelist_project"

    def initialize_plugin(self):
        """
        Initialize the plugin
        """
        # Generate a list of blacklisted packages from the configuration and
        # store it into self.blacklist_package_names attribute so this
        # operation doesn't end up in the fastpath.
        self.whitelist_package_names = self._determine_unfiltered_package_names()
        logger.info(
            f"Initialized project plugin {self.name!r}, filtering "
            f"{self.whitelist_package_names!r}"
        )

    def _determine_unfiltered_package_names(self):
        """
        Return a list of package names to be filtered base on the configuration
        file.
        """
        # This plugin only processes packages, if the line in the packages
        # configuration contains a PEP440 specifier it will be processed by the
        # blacklist release filter.  So we need to remove any packages that
        # are not applicable for this plugin.
        unfiltered_packages = set()
        try:
            lines = self.configuration["whitelist"]["packages"]
            package_lines = lines.split("\n")
        except KeyError:
            package_lines = []
        for package_line in package_lines:
            package_line = package_line.strip()
            if not package_line or package_line.startswith("#"):
                continue
            unfiltered_packages.add(package_line)
        logger.debug("Project whitelist is %r", list(unfiltered_packages))
        return list(unfiltered_packages)

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
        if not self.whitelist_package_names:
            return False

        name = kwargs.get("name", None)
        if not name:
            return False

        if name in self.whitelist_package_names:
            logger.info(f"Package {name!r} is whitelisted")
            return False
        return True

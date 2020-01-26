import logging
from typing import List

from bandersnatch.filter import FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class ExcludePlatformFilter(FilterReleasePlugin):
    """
    Filters releases based on regex patters defined by the user.
    """

    name = "exclude_platform"

    _patterns: List[str] = []
    _packagetypes: List[str] = []

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        if self._patterns or self._packagetypes:
            logger.debug(
                "Skipping initalization of Exclude Platform plugin. "
                + "Already initialized"
            )
            return

        try:
            tags = self.configuration["blacklist"]["platforms"].split()
        except KeyError:
            logger.error(f"Plugin {self.name}: missing platforms= setting")
            return

        for platform in tags:
            lplatform = platform.lower()

            if lplatform in ("windows", "win"):
                # PEP 425
                # see also setuptools/package_index.py
                self._patterns.extend([".win32", "-win32", "win_amd64", "win-amd64"])
                # PEP 527
                self._packagetypes.extend(["bdist_msi", "bdist_wininst"])

            elif lplatform in ("macos", "macosx"):
                self._patterns.extend(["macosx_", "macosx-"])
                self._packagetypes.extend(["bdist_dmg"])

            elif lplatform in ("freebsd"):
                # concerns only very few files
                self._patterns.extend([".freebsd", "-freebsd"])

            elif lplatform in ("linux"):
                self._patterns.extend(
                    [
                        "linux-i686",  # PEP 425
                        "linux-x86_64",  # PEP 425
                        "linux_armv7l",  # https://github.com/pypa/warehouse/pull/2010
                        "linux_armv6l",  # https://github.com/pypa/warehouse/pull/2012
                        "manylinux1_",  # PEP 513
                        "manylinux2010_",  # PEP 571
                    ]
                )
                self._packagetypes.extend(["bdist_rpm"])

        logger.info(f"Initialized {self.name} plugin with {self._patterns!r}")

    def filter(self, metadata):
        releases = metadata["releases"]
        """
        Remove files from `releases` that match any pattern.
        """

        # Make a copy of releases keys
        # as we may delete packages during iteration
        removed = 0
        versions = list(releases.keys())
        for version in versions:
            new_files = []
            for file_desc in releases[version]:
                if self._check_match(file_desc):
                    removed += 1
                else:
                    new_files.append(file_desc)
            if len(new_files) == 0:
                del releases[version]
            else:
                releases[version] = new_files
        logger.debug(f"{self.name}: filenames removed: {removed}")
        if not releases:
            return False
        else:
            return True

    def _check_match(self, file_desc) -> bool:
        """
        Check if a release version matches any of the specified patterns.

        Parameters
        ==========
        name: file_desc
            file description entry

        Returns
        =======
        bool:
            True if it matches, False otherwise.
        """

        # source dist: never filter out
        pt = file_desc.get("packagetype")
        if pt == "sdist":
            return False

        # Windows installer
        if pt in self._packagetypes:
            return True

        fn = file_desc["filename"]
        for i in self._patterns:
            if i in fn:
                return True

        return False

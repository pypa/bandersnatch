import logging
from typing import List

from bandersnatch.filter import FilterFilenamePlugin

logger = logging.getLogger("bandersnatch")


class ExcludePlatformFilter(FilterFilenamePlugin):
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

        try:
            tags = self.configuration["blacklist"]["platforms"].split("\n")
        except KeyError:
            logger.info(f"Plugin {self.name}: missing platforms= setting")
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

    def check_match(self, file_desc):
        """
        Check if a release version matches any of the specificed patterns.

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
        pt = file_desc["packagetype"]
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

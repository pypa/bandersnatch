import logging
from typing import Dict, List

from bandersnatch.filter import FilterReleaseFilePlugin

logger = logging.getLogger("bandersnatch")


class ExcludePlatformFilter(FilterReleaseFilePlugin):
    """
    Filters releases based on regex patters defined by the user.
    """

    name = "exclude_platform"

    _patterns: List[str] = []
    _packagetypes: List[str] = []

    _windowsPlatformTypes = [".win32", "-win32", "win_amd64", "win-amd64"]

    _linuxPlatformTypes = [
        "linux-i686",  # PEP 425
        "linux-x86_64",  # PEP 425
        "linux_armv7l",  # https://github.com/pypa/warehouse/pull/2010
        "linux_armv6l",  # https://github.com/pypa/warehouse/pull/2012
        "manylinux1_i686",  # PEP 513
        "manylinux1_x86_64",  # PEP 513
        "manylinux2010_i686",  # PEP 571
        "manylinux2010_x86_64",  # PEP 571
    ]

    def initialize_plugin(self) -> None:
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
            tags = self.blocklist["platforms"].split()
        except KeyError:
            logger.error(f"Plugin {self.name}: missing platforms= setting")
            return

        for platform in tags:
            lplatform = platform.lower()

            if lplatform in ("windows", "win"):
                # PEP 425
                # see also setuptools/package_index.py
                self._patterns.extend(self._windowsPlatformTypes)
                # PEP 527
                self._packagetypes.extend(["bdist_msi", "bdist_wininst"])

            elif lplatform in ("macos", "macosx"):
                self._patterns.extend(["macosx_", "macosx-"])
                self._packagetypes.extend(["bdist_dmg"])

            elif lplatform in ("freebsd"):
                # concerns only very few files
                self._patterns.extend([".freebsd", "-freebsd"])

            elif lplatform in ("linux"):
                self._patterns.extend(self._linuxPlatformTypes)
                self._packagetypes.extend(["bdist_rpm"])

            # check for platform specific architectures
            elif lplatform in self._windowsPlatformTypes:
                self._patterns.extend([lplatform])

            elif lplatform in self._linuxPlatformTypes:
                self._patterns.extend([lplatform])

        logger.info(f"Initialized {self.name} plugin with {self._patterns!r}")

    def filter(self, metadata: Dict) -> bool:
        """
        Returns False if file matches any of the filename patterns
        """
        file = metadata["release_file"]
        return not self._check_match(file)

    def _check_match(self, file_desc: Dict) -> bool:
        """
        Check if a release version matches any of the specified patterns.

        Parameters
        ==========
        file_desc: Dict
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

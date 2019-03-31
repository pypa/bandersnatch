import logging
from typing import List

from bandersnatch.filter import FilterFilenamePlugin

logger = logging.getLogger("bandersnatch")

_plugin_initialized: bool = False
_patterns: List[str] = []
_packagetypes: List[str] = []


def _init_once(self):
    global _plugin_initialized

    if _plugin_initialized:
        return

    try:
        for platform in self.configuration["blacklist"]["platforms"].split("\n"):

            if platform.lower() in ("windows", "win"):
                _patterns.extend([".win32", "-win32", "win_amd64", "win-amd64"])
                _packagetypes.extend(["bdist_msi", "bdist_wininst"])

            elif platform.lower() in ("macos", "macosx"):
                _patterns.extend(["macosx_", "macosx-"])
                _packagetypes.extend(["bdist_dmg"])

            elif platform.lower() in ("freebsd"):
                _patterns.extend(["freebsd"])

            elif platform.lower() in ("linux"):
                _patterns.extend(
                    [
                        "linux-i686",
                        "linux-x86_64",
                        "linux_armv7l",
                        "linux-armv7l",
                        "manylinux1_",
                    ]
                )
                _packagetypes.extend(["bdist_rpm"])

    except KeyError:
        pass

    _plugin_initialized = True
    logger.info(f"Initialized {self.name} plugin with {_patterns!r}")


class ExcludePlatformFilter(FilterFilenamePlugin):
    """
    Filters releases based on regex patters defined by the user.
    """

    name = "exclude_platform"

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        _init_once(self)

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
        if pt in _packagetypes:
            return True

        fn = file_desc["filename"]
        for i in _patterns:
            if i in fn:
                return True

        return False

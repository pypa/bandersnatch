import logging
from typing import Dict, List

from bandersnatch.filter import FilterReleaseFilePlugin

logger = logging.getLogger("bandersnatch")


class ExcludePlatformFilter(FilterReleaseFilePlugin):
    """
    Filters releases based on regex patterns defined by the user.
    """

    name = "exclude_platform"

    _patterns: List[str] = []
    _packagetypes: List[str] = []

    # Python tags https://peps.python.org/pep-0425/#python-tag
    _python24versions  = ['-cp24-' , '-ip24-' , '-jy24-' , '-pp24-' , '-py2.4.' , '-py2.4-' ]
    _python25versions  = ['-cp25-' , '-ip25-' , '-jy25-' , '-pp25-' , '-py2.5.' , '-py2.5-' ]
    _python26versions  = ['-cp26-' , '-ip26-' , '-jy26-' , '-pp26-' , '-py2.6.' , '-py2.6-' ]
    _python27versions  = ['-cp27-' , '-ip27-' , '-jy27-' , '-pp27-' , '-py2.7.' , '-py2.7-' ]
    _python31versions  = ['-cp31-' , '-ip31-' , '-jy31-' , '-pp31-' , '-py3.1.' , '-py3.1-' ]
    _python32versions  = ['-cp32-' , '-ip32-' , '-jy32-' , '-pp32-' , '-py3.2.' , '-py3.2-' ]
    _python33versions  = ['-cp33-' , '-ip33-' , '-jy33-' , '-pp33-' , '-py3.3.' , '-py3.3-' ]
    _python34versions  = ['-cp34-' , '-ip34-' , '-jy34-' , '-pp34-' , '-py3.4.' , '-py3.4-' ]
    _python35versions  = ['-cp35-' , '-ip35-' , '-jy35-' , '-pp35-' , '-py3.5.' , '-py3.5-' ]
    _python36versions  = ['-cp36-' , '-ip36-' , '-jy36-' , '-pp36-' , '-py3.6.' , '-py3.6-' ]
    _python37versions  = ['-cp37-' , '-ip37-' , '-jy37-' , '-pp37-' , '-py3.7.' , '-py3.7-' ]
    _python38versions  = ['-cp38-' , '-ip38-' , '-jy38-' , '-pp38-' , '-py3.8.' , '-py3.8-' ]
    _python39versions  = ['-cp39-' , '-ip39-' , '-jy39-' , '-pp39-' , '-py3.9.' , '-py3.9-' ]
    _python310versions = ['-cp310-', '-ip310-', '-jy310-', '-pp310-', '-py3.10.', '-py3.10-']

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
        "manylinux2014_x86_64",  # PEP 599
        "manylinux2014_i686",  # PEP 599
        "manylinux2014_aarch64",  # PEP 599
        "manylinux2014_armv7l",  # PEP 599
        "manylinux2014_ppc64",  # PEP 599
        "manylinux2014_ppc64le",  # PEP 599
        "manylinux2014_s390x",  # PEP 599
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

            elif lplatform in ("py2.4"):
                self._patterns.extend(self._python24versions)

            elif lplatform in ("py2.5"):
                self._patterns.extend(self._python25versions)

            elif lplatform in ("py2.6"):
                self._patterns.extend(self._python26versions)

            elif lplatform in ("py2.7"):
                self._patterns.extend(self._python27versions)

            elif lplatform in ("py3.1"):
                self._patterns.extend(self._python31versions)

            elif lplatform in ("py3.2"):
                self._patterns.extend(self._python32versions)

            elif lplatform in ("py3.3"):
                self._patterns.extend(self._python33versions)

            elif lplatform in ("py3.4"):
                self._patterns.extend(self._python34versions)

            elif lplatform in ("py3.5"):
                self._patterns.extend(self._python35versions)

            elif lplatform in ("py3.6"):
                self._patterns.extend(self._python36versions)

            elif lplatform in ("py3.7"):
                self._patterns.extend(self._python37versions)

            elif lplatform in ("py3.8"):
                self._patterns.extend(self._python38versions)

            elif lplatform in ("py3.9"):
                self._patterns.extend(self._python39versions)

            elif lplatform in ("py3.10"):
                self._patterns.extend(self._python310versions)

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

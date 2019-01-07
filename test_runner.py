#!/usr/bin/env python

"""
bandersnatch CI run script - Will either drive `tox` or run an Integration Test
- Rewritten in Python for easier dev contributions + Windows support

Integration Tests will go off and hit PyPI + pull whiteliested packages
then check for expected outputs to exist
"""

from configparser import ConfigParser
from os import environ
from pathlib import Path
from platform import system
from shutil import rmtree
from subprocess import run
from sys import exit
from tempfile import gettempdir

from src.bandersnatch.utils import hash


BANDERSNATCH_EXE = Path("/usr/bin/bandersnatch")
CI_CONFIG = Path("src/bandersnatch/tests/ci.conf")
MIRROR_ROOT = Path(f"{gettempdir()}/pypi")
MIRROR_BASE = MIRROR_ROOT / "web"
TGZ_SHA256 = "bc9430dae93f8bc53728773545cbb646a6b5327f98de31bdd6e1a2b2c6e805a9"


def do_ci_verify():
    peerme_index = MIRROR_BASE / "simple/p/peerme/index.html"
    peerme_json = MIRROR_BASE / "json/peerme"
    peerme_tgz = (
        MIRROR_BASE
        / "packages/8f/1a/"
        / "1aa000db9c5a799b676227e845d2b64fe725328e05e3d3b30036f50eb316"
        / "peerme-1.0.0-py36-none-any.whl"
    )

    if not peerme_index.exists():
        print(f"No peerme simple API index exists @ {peerme_index}")
        return 69

    if not peerme_json.exists():
        print(f"No peerme JSON API file exists @ {peerme_json}")
        return 70

    if not peerme_tgz.exists():
        print(f"No peerme tgz file exists @ {peerme_tgz}")
        return 71

    peerme_tgz_sha256 = hash(str(peerme_tgz))
    if peerme_tgz_sha256 != TGZ_SHA256:
        print(f"Bad peerme 1.0.0 sha256: {peerme_tgz_sha256} != {TGZ_SHA256}")
        return 72

    rmtree(MIRROR_ROOT)

    print("Bandersnatch PyPI CI finished successfully!")
    return 0


def do_ci(conf: Path) -> int:
    if not conf.exists():
        print(f"CI config {conf} does not exist for bandersnatch run")
        return 2

    print("Starting CI bandersnatch mirror ...")
    cmds = (str(BANDERSNATCH_EXE), "--config", str(conf), "--debug", "mirror")
    print(f"bandersnatch cmd: {' '.join(cmds)}")
    run(cmds, check=True)

    return do_ci_verify()


def platform_config() -> Path:
    """Ensure the CI_CONFIG is correct for the platform we're running on"""
    global BANDERSNATCH_EXE
    platform_ci_conf = MIRROR_ROOT / "ci.conf"
    cp = ConfigParser()
    cp.read(str(CI_CONFIG))

    print(f"Setting CI directory={MIRROR_ROOT}")
    cp["mirror"]["directory"] = str(MIRROR_ROOT)

    with platform_ci_conf.open("w") as pccfp:
        cp.write(pccfp)

    # TODO: Correct path + see if this actually works
    if system() == "Windows":
        BANDERSNATCH_EXE = Path(r"C:\pip\bin\bandersnatch.exe")

    return platform_ci_conf


def main() -> int:
    if "TOXENV" not in environ:
        print("No TOXENV set. Exiting!")
        return 1

    if environ["TOXENV"] != "INTEGRATION":
        run(("/usr/bin/which", "tox"))  # COOPER
        return run(("/usr/bin/tox",)).returncode
    else:
        print("Running Ingtegration tests due to TOXENV set to INTEGRATION")

        print("Running which to find out where bandersnatch executable is:") # COOPER
        run(("/usr/bin/which", "bandersnatch"))  # COOPER

        MIRROR_ROOT.mkdir(exist_ok=True)
        return do_ci(platform_config())


if __name__ == "__main__":
    exit(main())

#!/usr/bin/env python

"""
bandersnatch CI run script - Will either drive `tox` or run an Integration Test
- Rewritten in Python for easier dev contributions + Windows support

Integration Tests will go off and hit PyPI + pull allowlisted packages
then check for expected outputs to exist
"""

from configparser import ConfigParser
from os import environ
from pathlib import Path
from shutil import rmtree, which
from subprocess import run
from sys import exit
from tempfile import gettempdir

from src.bandersnatch.utils import hash

BANDERSNATCH_EXE = Path(
    which("bandersnatch") or which("bandersnatch.exe") or "bandersnatch"
)
CI_CONFIG = Path("src/bandersnatch/tests/ci.conf")
EOP = "[CI ERROR]:"
MIRROR_ROOT = Path(f"{gettempdir()}/pypi")
MIRROR_BASE = MIRROR_ROOT / "web"
TGZ_SHA256 = "bc9430dae93f8bc53728773545cbb646a6b5327f98de31bdd6e1a2b2c6e805a9"
TOX_EXE = Path(which("tox") or "tox")

# Make Global so we can check exists before delete
A_BLACK_WHL = (
    MIRROR_BASE
    / "packages"
    / "30"
    / "62"
    / "cf549544a5fe990bbaeca21e9c419501b2de7a701ab0afb377bc81676600"
    / "black-19.3b0-py36-none-any.whl"
)


def check_ci(suppress_errors: bool = False) -> int:
    black_index = MIRROR_BASE / "simple/b/black/index.html"
    peerme_index = MIRROR_BASE / "simple/p/peerme/index.html"
    peerme_json = MIRROR_BASE / "json/peerme"
    peerme_tgz = (
        MIRROR_BASE
        / "packages"
        / "8f"
        / "1a"
        / "1aa000db9c5a799b676227e845d2b64fe725328e05e3d3b30036f50eb316"
        / "peerme-1.0.0-py36-none-any.whl"
    )

    if not suppress_errors and not peerme_index.exists():
        print(f"{EOP} No peerme simple API index exists @ {peerme_index}")
        return 69

    if not suppress_errors and not peerme_json.exists():
        print(f"{EOP} No peerme JSON API file exists @ {peerme_json}")
        return 70

    if not suppress_errors and not peerme_tgz.exists():
        print(f"{EOP} No peerme tgz file exists @ {peerme_tgz}")
        return 71

    peerme_tgz_sha256 = hash(str(peerme_tgz))
    if not suppress_errors and peerme_tgz_sha256 != TGZ_SHA256:
        print(f"{EOP} Bad peerme 1.0.0 sha256: {peerme_tgz_sha256} != {TGZ_SHA256}")
        return 72

    if not suppress_errors and black_index.exists():
        print(f"{EOP} {black_index} exists ... delete failed?")
        return 73

    if not suppress_errors and A_BLACK_WHL.exists():
        print(f"{EOP} {A_BLACK_WHL} exists ... delete failed?")
        return 74

    rmtree(MIRROR_ROOT)

    print("Bandersnatch PyPI CI finished successfully!")
    return 0


def do_ci(conf: Path, suppress_errors: bool = False) -> int:
    if not conf.exists():
        print(f"CI config {conf} does not exist for bandersnatch run")
        return 2

    print("Starting CI bandersnatch mirror ...")
    cmds = (str(BANDERSNATCH_EXE), "--config", str(conf), "--debug", "mirror")
    print(f"bandersnatch cmd: {' '.join(cmds)}")
    run(cmds, check=not suppress_errors)

    print(f"Checking if {A_BLACK_WHL} exists")
    if not A_BLACK_WHL.exists():
        print(f"{EOP} {A_BLACK_WHL} does not exist after mirroring ...")
        if not suppress_errors:
            return 68

    print("Starting to deleting black from mirror ...")
    del_cmds = (
        str(BANDERSNATCH_EXE),
        "--config",
        str(conf),
        "--debug",
        "delete",
        "black",
    )
    print(f"bandersnatch delete cmd: {' '.join(cmds)}")
    run(del_cmds, check=not suppress_errors)

    return check_ci(suppress_errors)


def platform_config() -> Path:
    """Ensure the CI_CONFIG is correct for the platform we're running on"""
    platform_ci_conf = MIRROR_ROOT / "ci.conf"
    cp = ConfigParser()
    cp.read(str(CI_CONFIG))

    print(f"Setting CI directory={MIRROR_ROOT}")
    cp["mirror"]["directory"] = str(MIRROR_ROOT)

    with platform_ci_conf.open("w") as pccfp:
        cp.write(pccfp)

    return platform_ci_conf


def main() -> int:
    if "TOXENV" not in environ:
        print("No TOXENV set. Exiting!")
        return 1

    # GitHub Actions does not have a nice way to ignore failures
    # like TravisCI has. So will start with ignoring all 3.10-dev failures
    # and maybe remove this once we get everything to pass
    suppress_errors = bool(environ.get("SUPPRESS_ERRORS", False))

    if environ["TOXENV"] != "INTEGRATION":
        returncode = run((str(TOX_EXE),)).returncode
        if not suppress_errors:
            return returncode
        return 0
    else:
        print("Running Ingtegration tests due to TOXENV set to INTEGRATION")
        MIRROR_ROOT.mkdir(exist_ok=True)
        return do_ci(platform_config(), suppress_errors)


if __name__ == "__main__":
    exit(main())

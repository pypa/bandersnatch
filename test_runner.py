#!/usr/bin/env python

"""
bandersnatch CI run script - Will either drive `tox` or run an Integration Test
- Rewritten in Python for easier dev contributions + Windows support

Integration Tests will go off and hit PyPI + pull allowlisted packages
then check for expected outputs to exist
"""

import json
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
TGZ_SHA256 = "b6114554fb312f9b0bdeaf6a7498f7da05fc17b9250c0449ed796fac9ab663e2"
TOX_EXE = Path(which("tox") or "tox")

# Make Global so we can check exists before delete
A_BLACK_WHL = (
    MIRROR_BASE
    / "packages"
    / "20"
    / "de"
    / "eff8e3ccc22b5c2be1265a9e61f1006d03e194519a3ca2e83dd8483dbbb5"
    / "black-23.1.0-cp38-cp38-macosx_10_16_x86_64.whl"
)


def check_ci(suppress_errors: bool = False) -> int:
    black_index = MIRROR_BASE / "simple/b/black/index.html"
    pyaib_index = MIRROR_BASE / "simple/p/pyaib/index.html"
    pyaib_json_index = MIRROR_BASE / "simple/p/pyaib/index.v1_json"
    pyaib_json = MIRROR_BASE / "json/pyaib"
    pyaib_tgz = (
        MIRROR_BASE
        / "packages"
        / "0c"
        / "af"
        / "0389466685844d95c6f1f857008d4931d14c7937ac8dba689639ccf0cc54"
        / "pyaib-2.1.0.tar.gz"
    )

    if not suppress_errors and not pyaib_index.exists():
        print(f"{EOP} No pyaib simple API index exists @ {pyaib_index}")
        return 69

    if not suppress_errors and not pyaib_json.exists():
        print(f"{EOP} No pyaib JSON API file exists @ {pyaib_json}")
        return 70

    if not suppress_errors and not pyaib_tgz.exists():
        print(f"{EOP} No pyaib tgz file exists @ {pyaib_tgz}")
        return 71

    pyaib_tgz_sha256 = hash(pyaib_tgz)
    if not suppress_errors and pyaib_tgz_sha256 != TGZ_SHA256:
        print(f"{EOP} Bad pyaib 1.0.0 sha256: {pyaib_tgz_sha256} != {TGZ_SHA256}")
        return 72

    if not suppress_errors and black_index.exists():
        print(f"{EOP} {black_index} exists ... delete failed?")
        return 73

    if not suppress_errors and A_BLACK_WHL.exists():
        print(f"{EOP} {A_BLACK_WHL} exists ... delete failed?")
        return 74

    if not suppress_errors and not pyaib_json_index.exists():
        print(f"{EOP} {pyaib_json_index} does not exist ...")
        return 75
    else:
        with pyaib_json_index.open("r") as fp:
            json.load(fp)  # Check it's valid JSON

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

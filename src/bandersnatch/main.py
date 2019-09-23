import argparse
import asyncio
import logging
import logging.config
import shutil
import sys
from pathlib import Path
from tempfile import gettempdir

import bandersnatch.log
import bandersnatch.mirror
import bandersnatch.verify

from .configuration import BandersnatchConfig

logger = logging.getLogger(__name__)  # pylint: disable=C0103


def main() -> int:
    parser = argparse.ArgumentParser(description="PyPI PEP 381 mirroring client.")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {bandersnatch.__version__}"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="/etc/bandersnatch.conf",
        help="use configuration file (default: %(default)s)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Turn on extra logging (DEBUG level)",
    )
    subparsers = parser.add_subparsers()

    # `mirror` command
    m = subparsers.add_parser(
        "mirror",
        help="Performs a one-time synchronization with the PyPI master server.",
    )
    m.add_argument(
        "--force-check",
        action="store_true",
        default=False,
        help="Force bandersnatch to reset the PyPI serial (move serial file to /tmp) to \
                perform a full sync",
    )
    m.set_defaults(op="mirror")

    # `verify` command
    v = subparsers.add_parser(
        "verify", help="Read in Metadata and check package file validity"
    )
    v.add_argument(
        "--delete",
        action="store_true",
        default=False,
        help="Enable deletion of packages not active",
    )
    v.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Do not download or delete files",
    )
    v.add_argument(
        "--json-update",
        action="store_true",
        default=False,
        help="Enable updating JSON from PyPI",
    )
    v.add_argument(
        "--workers",
        type=int,
        default=0,
        help="# of parallel iops [Defaults to bandersnatch.conf]",
    )
    v.set_defaults(op="verify")

    if len(sys.argv) < 2:
        parser.print_help()
        parser.exit()

    args = parser.parse_args()

    bandersnatch.log.setup_logging(args)

    # Prepare default config file if needed.
    config_path = Path(args.config)
    if not config_path.exists():
        logger.warning(f"Config file '{args.config}' missing, creating default config.")
        logger.warning("Please review the config file, then run 'bandersnatch' again.")

        default_config_path = Path(__file__).parent / "default.conf"
        try:
            shutil.copy(default_config_path, args.config)
        except IOError as e:
            logger.error(f"Could not create config file: {e}")
        return 1

    config = BandersnatchConfig(config_file=args.config).config

    if config.has_option("mirror", "log-config"):
        logging.config.fileConfig(str(Path(config.get("mirror", "log-config"))))

    if args.op == "verify":
        loop = asyncio.get_event_loop()
        try:
            return loop.run_until_complete(
                bandersnatch.verify.metadata_verify(config, args)
            )
        finally:
            loop.close()
    else:
        if args.force_check:
            status_file = Path(config.get("mirror", "directory")) / "status"
            if status_file.exists():
                tmp_status_file = Path(gettempdir()) / "status"
                try:
                    shutil.move(status_file, tmp_status_file)
                    logger.debug(
                        "Force bandersnatch to check everything against the master PyPI"
                        + f" - status file moved to {tmp_status_file}"
                    )
                except OSError as e:
                    logger.error(
                        f"Could not move status file ({status_file} to "
                        + f" {tmp_status_file}): {e}"
                    )
            else:
                logger.info(
                    f"No status file to move ({status_file}) - Full sync will occur"
                )

        return bandersnatch.mirror.mirror(config)


if __name__ == "__main__":
    exit(main())

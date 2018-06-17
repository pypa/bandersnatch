import logging
import os
from typing import Dict

from zest.releaser.utils import execute_command

logger = logging.getLogger(__name__)


def update_requirements(data: Dict[str, str]) -> None:
    os.chdir(data["workingdir"])
    logger.info("Running buildout to update requirements.txt.")
    execute_command("bin/buildout")
    logger.info("Committing requirements.txt.")
    execute_command('hg commit -v -m "Update requirements.txt"')


def update_stable_tag(data: Dict[str, str]) -> None:
    os.chdir(data["workingdir"])
    logger.info("Updating stable tag.")
    execute_command("hg tag -f -r %s stable" % data["version"])

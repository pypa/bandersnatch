from zest.releaser.utils import execute_command
import logging
import os

logger = logging.getLogger(__name__)


def update_requirements(data):
    os.chdir(data['workingdir'])
    logger.info('Running buildout to update requirements.txt.')
    execute_command('bin/buildout')
    logger.info('Committing requirements.txt.')
    execute_command('hg commit -v -m "Update requirements.txt"')


def update_stable_tag(data):
    os.chdir(data['workingdir'])
    logger.info('Updating stable tag.')
    execute_command('hg tag -f -r %s stable' % data['version'])

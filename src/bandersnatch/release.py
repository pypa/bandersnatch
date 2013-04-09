from zest.releaser.utils import system
import logging
import os

logger = logging.getLogger(__name__)


def update_requirements(data):
    os.chdir(data['workingdir'])
    logging.info('Running buildout to update requirements.txt.')
    system('bin/buildout')
    logging.info('Committing requirements.txt.')
    system('hg commit -v -m "Update requirements.txt"')


def update_stable_tag(data):
    os.chdir(data['workingdir'])
    logging.info('Updating stable tag.')
    system('hg tag -f -r %s stable' % data['version'])

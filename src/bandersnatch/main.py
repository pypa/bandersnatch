import ConfigParser
import argparse
import bandersnatch.apache_stats
import bandersnatch.log
import bandersnatch.master
import bandersnatch.mirror
import bandersnatch.utils
import glob
import logging
import os.path
import shutil
import sys

logger = logging.getLogger(__name__)


def mirror(config):
    # Always reference those classes here with the fully qualified name to
    # allow them being patched by mock libraries!
    master = bandersnatch.master.Master(
        config.get('mirror', 'master'),
        float(config.get('mirror', 'timeout')))
    mirror = bandersnatch.mirror.Mirror(
        config.get('mirror', 'directory'), master,
        stop_on_error=config.getboolean('mirror', 'stop-on-error'),
        workers=config.getint('mirror', 'workers'),
        delete_packages=config.getboolean('mirror', 'delete-packages'))
    mirror.synchronize()


def update_stats(config):
    # Ensure the mirror directory exists
    targetdir = config.get('mirror', 'directory')
    if not os.path.exists(targetdir):
        logger.error(
            'Mirror directory {} does not exist. '
            'Please run `bandersnatch mirror` first.'.format(targetdir))
        sys.exit(1)

    # Ensure the mirror's web directory exists
    targetdir = os.path.join(targetdir, 'web')
    if not os.path.exists(targetdir):
        logger.error('Directory {} does not exist. '
                     'Is this a mirror?'.format(targetdir))
        sys.exit(1)

    # Ensure the mirror's statistics directory exists
    targetdir = os.path.join(targetdir, 'local-stats')
    if not os.path.exists(targetdir,):
        logger.info('Creating statistics directory {}.'.format(targetdir))
        os.mkdir(targetdir)
        os.mkdir(os.path.join(targetdir, 'days'))

    logs = config.get('statistics', 'access-log-pattern')
    logs = glob.glob(logs)
    # Keep as dotted name to support mocking.
    bandersnatch.apache_stats.update_stats(targetdir, logs)


def main():
    bandersnatch.log.setup_logging()

    parser = argparse.ArgumentParser(
        description='PyPI PEP 381 mirroring client.')
    parser.add_argument('-c', '--config', default='/etc/bandersnatch.conf',
                        help='use configuration file (default: %(default)s)')
    subparsers = parser.add_subparsers()

    # `mirror` command
    p = subparsers.add_parser(
        'mirror',
        help='Performs a one-time synchronization with '
             'the PyPI master server.')
    p.set_defaults(func=mirror)

    # `update-stats` command
    p = subparsers.add_parser(
        'update-stats',
        help='Process the access log files and package up access statistics '
             'for aggregation on the PyPI master.')
    p.set_defaults(func=update_stats)

    args = parser.parse_args()

    # Prepare default config file if needed.
    default_config = os.path.join(os.path.dirname(__file__), 'default.conf')
    if not os.path.exists(args.config):
        logger.warning('Config file \'{}\' missing, creating default config.'.
                       format(args.config))
        logger.warning(
            'Please review the config file, then run \'bandersnatch\' again.')
        try:
            shutil.copy(default_config, args.config)
        except IOError, e:
            logger.error('Could not create config file: {}'.format(str(e)))
        sys.exit(1)

    config = ConfigParser.ConfigParser()
    config.read([default_config, args.config])

    args.func(config)

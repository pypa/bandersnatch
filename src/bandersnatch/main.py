import ConfigParser
import argparse
import bandersnatch.master
import bandersnatch.mirror
import logging
import os.path
import shutil
import sys


logger = logging.getLogger(__name__)


def setup_logging():
    ch = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    logger = logging.getLogger('bandersnatch')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)
    return ch


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description='Sync PyPI mirror with master server.')
    parser.add_argument('-c', '--config', default='/etc/bandersnatch.conf',
                        help='use configuration file (default: %(default)s)')
    args = parser.parse_args()

    default_config = os.path.join(os.path.dirname(__file__), 'default.conf')
    if not os.path.exists(args.config):
        logger.warning('Config file \'{}\' missing, creating default config.'.
                       format(args.config))
        logger.warning(
            'Please review the config file, then run \'bsn-mirror\' again.')
        try:
            shutil.copy(default_config, args.config)
        except IOError, e:
            logger.error('Could not create config file: {}'.format(str(e)))
        sys.exit(1)

    config = ConfigParser.ConfigParser()
    config.read([default_config, args.config])

    # Always reference those classes here with the fully qualified name to
    # allow them being patched by mock libraries!
    master = bandersnatch.master.Master(config.get('mirror', 'master'))
    mirror = bandersnatch.mirror.Mirror(
        config.get('mirror', 'directory'), master,
        stop_on_error=config.getboolean('mirror', 'stop-on-error'),
        workers=config.getint('mirror', 'workers'),
        delete_packages=config.getboolean('mirror', 'delete-packages'))
    mirror.synchronize()

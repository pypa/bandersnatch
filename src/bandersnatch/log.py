# This is mainly factored out into a separate module so I can ignore it in
# coverage analysis. Unfortunately this is really hard to test as the Python
# logging module won't allow reasonable teardown. :(
import logging
import os


def setup_logging(config):
    if config.has_option('mirror', 'log-config'):
        logging.config.fileConfig(
            os.path.expanduser(config.get('mirror', 'log-config')))
    else:
        ch = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s')
        ch.setFormatter(formatter)
        logger = logging.getLogger('bandersnatch')
        level = getattr(logging, config.get('mirror', 'log-level', 'DEBUG'))
        logger.setLevel(level)
        logger.addHandler(ch)
        return ch

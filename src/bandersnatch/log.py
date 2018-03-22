# This is mainly factored out into a separate module so I can ignore it in
# coverage analysis. Unfortunately this is really hard to test as the Python
# logging module won't allow reasonable teardown. :(
import logging


def setup_logging():
    ch = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    logger = logging.getLogger('bandersnatch')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)
    return ch

# This is mainly factored out into a separate module so I can ignore it in
# coverage analysis. Unfortunately this is really hard to test as the Python
# logging module won't allow reasonable teardown. :(
import logging


def setup_logging(args):
    ch = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    logger = logging.getLogger('bandersnatch')
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
    logger.addHandler(ch)
    return ch

"""
Blacklist management
"""
from .configuration import BandersnatchConfig


blacklist_project_plugins = []
blacklist_release_plugins = []
ENTRYPOINT_GROUP_BASE = 'bandersnatch_filter_plugins'


class Filter(object):
    """
    Base Filter class
    """
    def __init__(self):
        self.configuration = BandersnatchConfig()


class FilterProjectPlugin(Filter):
    """
    Plugin that blocks sync operations for an entire project
    """
    pass


class FilterReleasePlugin(Filter):
    """
    Plugin that blocks the download of specific release files
    """
    pass


def load_filter_plugins(entrypoint_group):
    """
    Load all blacklist plugins that are registered with pkg_resources

    Parameters
    ==========
    entrypoint_group: str
        The entrypoint group name to load plugins from

    Returns
    =======
    List of Blacklist:
        A list of objects derived from the Blacklist class
    """

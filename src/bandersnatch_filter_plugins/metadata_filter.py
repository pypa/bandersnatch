import logging
import re
from typing import List, Pattern
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from bandersnatch.filter import FilterMetadataPlugin

logger = logging.getLogger("bandersnatch")



class RegexMetadataFilter(FilterMetadataPlugin):
    """
    Plugin to download only packages having metadata matching at least one of the  specified patterns.
    """

    name = "regex_metadata"
    #patterns: List[Pattern] = [] # by default, keep 'em all
    initilized = False
    patterns = {}

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config = self.configuration["regex_metadata"]
        except KeyError:
            return
        else:
            logger.info(f"Initializing regex_metadata plugin")
            if not self.initilized:
                for k in config:
                    pattern_strings = [pattern for pattern in config[k].split("\n") if pattern]
                    self.patterns[k] = [
                        re.compile(pattern_string) for pattern_string in pattern_strings
                    ]
                logger.info(f"Initialized regex_metadata plugin with {self.patterns}")
                self.initilized = True

    def filter(self, metadata):
        """
        Remove all release versions that don't match any of the specificed metadata patterns.
        """
        # If no patterns set, always return true
        if not self.patterns:
            return True

        # Walk through keys by dotted path
        for k in self.patterns:
            path=k.split('.')
            node=metadata
            for p in path:
                if p in node and node[p] is not None:
                    node=node[p]
                else:
                    return False
            if not isinstance(node,list): node = [ node ]
            for d in node:
                if any(pattern.match(d) for pattern in self.patterns[k]):
                    return True
        return False


        #for version in list(releases.keys()):
        #release = releases[version]
        #    if "requires_python" in release and release["requires_python"] is not None:
        #        if any(pattern.match(release["requires_python"]) for pattern in self.patterns):
        #            continue
        #        else:
        #            del releases[version]


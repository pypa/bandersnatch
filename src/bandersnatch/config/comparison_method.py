"""Enumeration of supported file comparison strategies"""

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from bandersnatch.utils import StrEnum


class ComparisonMethod(StrEnum):
    HASH = "hash"
    STAT = "stat"


class InvalidComparisonMethod(ValueError):
    """We don't have a valid comparison method choice from configuration"""

    pass


def get_comparison_value(method: str) -> ComparisonMethod:
    try:
        return ComparisonMethod(method)
    except ValueError:
        valid_methods = sorted(v.value for v in ComparisonMethod)
        raise InvalidComparisonMethod(
            f"{method} is not a valid file comparison method. "
            + f"Valid options are: {valid_methods}"
        )

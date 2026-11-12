import argparse

import pytest

from runner import parseHourList


def test_parseHourList_ascending_range() -> None:
    """Start time less than end time."""
    assert parseHourList("10-18") == [10, 11, 12, 13, 14, 15, 16, 17, 18]


def test_parseHourList_same_start_end() -> None:
    """Start and end match, expressed as a range."""
    assert parseHourList("18-18") == [18]


def test_parseHourList_crosses_midnight() -> None:
    """Time range crosses the day boundary."""
    assert parseHourList("23-5") == [23, 0, 1, 2, 3, 4, 5]


def test_parseHourList_single_number() -> None:
    """Single number, not a range."""
    assert parseHourList("23") == [23]


def test_parseHourList_invalid_raises() -> None:
    """Non-numeric input raises ArgumentTypeError containing the input string."""
    with pytest.raises(argparse.ArgumentTypeError, match="foo"):
        parseHourList("foo")

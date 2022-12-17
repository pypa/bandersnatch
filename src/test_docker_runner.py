import argparse
from unittest import TestCase

from runner import parseHourList


class TestRunner(TestCase):
    """
    Tests for the bandersnatch runner script
    """

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test__parseHourList__function(self) -> None:
        # Case where start time is less than end time
        input_time_range = "10-18"
        expected_hours_list = [10, 11, 12, 13, 14, 15, 16, 17, 18]
        hours_list = parseHourList(input_time_range)
        self.assertEqual(hours_list, expected_hours_list)

        # Case where start and end time match, but they are expressed as a range
        input_time_range = "18-18"
        expected_hours_list = [18]
        hours_list = parseHourList(input_time_range)
        self.assertEqual(hours_list, expected_hours_list)

        # Case where time range crosses the day
        input_time_range = "23-5"
        expected_hours_list = [23, 0, 1, 2, 3, 4, 5]
        hours_list = parseHourList(input_time_range)
        self.assertEqual(hours_list, expected_hours_list)

        # Case where the string is a single number and not a range
        input_time_range = "23"
        expected_hours_list = [23]
        hours_list = parseHourList(input_time_range)
        self.assertEqual(hours_list, expected_hours_list)

        # Case where the string is a text, should raise ArgumentTypeError
        input_time_range = "foo"
        with self.assertRaises(argparse.ArgumentTypeError) as context:
            parseHourList(input_time_range)
        # Assert that the error message contains the user input string
        self.assertIn(input_time_range, str(context.exception))

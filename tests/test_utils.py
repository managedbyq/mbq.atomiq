from django.test import TestCase

import arrow
from mbq.atomiq import utils


class UtilsTest(TestCase):

    def test_time_difference_ms(self):
        start_time = arrow.get(2018, 3, 1, 0, 0, 1).datetime
        end_time = arrow.get(2018, 3, 1, 0, 0, 2).datetime
        time_diff_ms = utils.time_difference_ms(start_time, end_time)
        self.assertEquals(time_diff_ms, 1000)

        start_time = arrow.get(2018, 3, 1, 0, 0, 0, 0).datetime
        end_time = arrow.get(2018, 3, 1, 0, 0, 0, 123000).datetime
        time_diff_ms = utils.time_difference_ms(start_time, end_time)
        self.assertEquals(time_diff_ms, 123)

        start_time = arrow.get(2018, 3, 1, 0, 0, 0, 0).datetime
        end_time = arrow.get(2018, 3, 1, 0, 0, 0, 123800).datetime
        time_diff_ms = utils.time_difference_ms(start_time, end_time)
        self.assertEquals(time_diff_ms, 124)

        start_time = arrow.get(2018, 3, 1, 0, 0, 0, 123800).datetime
        end_time = arrow.get(2018, 3, 1, 0, 0, 0, 0).datetime
        time_diff_ms = utils.time_difference_ms(start_time, end_time)
        self.assertEquals(time_diff_ms, -124)

from unittest import mock

from django.test import TestCase

import arrow
from mbq.atomiq import utils

import freezegun


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

    def test_debounce_decorator(self):
        with freezegun.freeze_time() as frozen_time:
            mock_fn = mock.Mock()
            mock_fn.__name__ = 'mock_fn'
            decorated_fn = utils.debounce(minutes=10)(mock_fn)

            decorated_fn()
            self.assertEquals(mock_fn.call_count, 0)

            frozen_time.tick()
            decorated_fn()
            self.assertEquals(mock_fn.call_count, 0)

            five_minutes = arrow.utcnow().shift(minutes=5) - arrow.utcnow()
            frozen_time.tick(delta=five_minutes)
            decorated_fn()
            self.assertEquals(mock_fn.call_count, 0)

            frozen_time.tick(delta=five_minutes)
            decorated_fn()
            self.assertEquals(mock_fn.call_count, 1)

            frozen_time.tick()
            decorated_fn()
            self.assertEquals(mock_fn.call_count, 1)

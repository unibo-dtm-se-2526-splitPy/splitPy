from datetime import date

import pytest

from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.errors import InvalidDateRange

JAN_1 = date(2026, 1, 1)
JAN_15 = date(2026, 1, 15)
JAN_31 = date(2026, 1, 31)


class TestDateRange:
    def test_start_after_end_raises_invalid_date_range(self):
        with pytest.raises(InvalidDateRange):
            DateRange(JAN_31, JAN_1)

    def test_single_day_range_is_valid(self):
        assert DateRange(JAN_1, JAN_1).contains(JAN_1)

    def test_contains_a_day_inside_the_range(self):
        assert DateRange(JAN_1, JAN_31).contains(JAN_15)

    def test_contains_both_extremes(self):
        period = DateRange(JAN_1, JAN_31)
        assert period.contains(JAN_1)
        assert period.contains(JAN_31)

    def test_does_not_contain_days_outside_the_range(self):
        period = DateRange(JAN_1, JAN_15)
        assert not period.contains(date(2025, 12, 31))
        assert not period.contains(JAN_31)

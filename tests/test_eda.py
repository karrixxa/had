"""Tests for interval arithmetic and temporal eligibility, not plot appearance."""
import unittest
import numpy as np
import pandas as pd
from analysis.run_eda import union_intervals, allocate_days, interval_mask, horizon_valid, gaps_between


class IntervalTests(unittest.TestCase):
    def frame(self, starts, ends):
        return pd.DataFrame({"fra": "a", "name": "A", "start": pd.to_datetime(starts),
                             "end": pd.to_datetime(ends)})

    def test_nested_intervals_and_explicit_gap_bridging(self):
        frame = self.frame(["2025-01-01 00:00", "2025-01-01 00:02", "2025-01-01 00:09", "2025-01-01 00:13"],
                           ["2025-01-01 00:10", "2025-01-01 00:03", "2025-01-01 00:11", "2025-01-01 00:14"])
        union = union_intervals(frame)
        self.assertEqual(union.duration_min.tolist(), [11, 1])
        merged = union_intervals(frame, 2)
        self.assertEqual(merged.duration_min.tolist(), [14])
        self.assertEqual(merged.fragments.tolist(), [4])

    def test_allocate_cross_midnight_without_double_counting(self):
        frame = self.frame(["2025-01-01 23:59:30"], ["2025-01-02 00:01:30"])
        result = allocate_days(frame, pd.date_range("2025-01-01", periods=2))
        np.testing.assert_allclose(result, [.5, 1.5])

    def test_minute_ticks_do_not_round_event_start_backwards(self):
        frame = self.frame(["2025-01-01 00:00:30"], ["2025-01-01 00:02:00"])
        np.testing.assert_array_equal(interval_mask(frame, pd.Timestamp("2025-01-01"), 4),
                                      [False, True, False, False])

    def test_horizon_rejects_missing_interior_even_if_endpoints_observed(self):
        observed = np.array([True, False, True, True, True])
        np.testing.assert_array_equal(horizon_valid(observed, 2), [False, False, True])

    def test_gaps_use_union_end_not_independently_sorted_ends(self):
        frame = self.frame(["2025-01-01 00:00", "2025-01-01 01:00", "2025-01-04 00:00"],
                           ["2025-01-02 00:00", "2025-01-01 02:00", "2025-01-04 01:00"])
        gaps = gaps_between(union_intervals(frame), 24)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps.iloc[0].start, pd.Timestamp("2025-01-02"))
        self.assertEqual(gaps.iloc[0].end, pd.Timestamp("2025-01-04"))


if __name__ == "__main__":
    unittest.main()

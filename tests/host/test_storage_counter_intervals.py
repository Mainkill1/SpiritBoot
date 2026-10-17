"""Exact arithmetic against hand-derived and exhaustive invented examples."""
import importlib.util
import itertools
import pathlib
import sys
import unittest
from fractions import Fraction

TOOL = pathlib.Path(__file__).resolve().parents[2] / "tools/storage_counter_intervals.py"
RATE = 733333333


class CounterIntervalTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TOOL.is_file(), "bounded counter interval helper is not implemented")
        spec = importlib.util.spec_from_file_location("counter_interval_subject", TOOL)
        self.m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.m
        spec.loader.exec_module(self.m)

    def metrics(self, ticks=20000, **kwargs):
        return self.m.counter_intervals([ticks], ticks, 512, **kwargs)

    def test_deck_retains_order_and_ranks_all_1024_samples(self):
        original = list(range(3023, 1999, -1))
        result = self.m.counter_intervals(original, 20000, 524288)
        original[0] = 1
        self.assertEqual(result.raw_operation_ticks, tuple(range(3023, 1999, -1)))
        self.assertEqual(result.raw_batch_ticks, 20000)
        self.assertEqual(len(result.operation_durations), 1024)
        self.assertEqual(result.error_seconds, Fraction(1, RATE))
        self.assertEqual(result.latency.center, Fraction(20000, RATE))
        self.assertEqual(result.latency.lower, Fraction(19999, RATE))
        self.assertEqual(result.latency.upper, Fraction(20001, RATE))
        self.assertEqual(result.p95.center, Fraction(2972, RATE))
        self.assertEqual(result.p95.lower, Fraction(2971, RATE))
        self.assertEqual(result.p99.center, Fraction(3013, RATE))
        self.assertEqual(result.p99.upper, Fraction(3014, RATE))

    def test_windows_frequency_selects_its_own_integer_or_fallback_bound(self):
        integer = self.metrics(platform="windows", qpf_hz=10000000)
        self.assertEqual(integer.error_seconds, Fraction(1, RATE))
        fallback = self.metrics(platform="windows", qpf_hz=12345679)
        self.assertEqual(fallback.error_seconds, Fraction(1733333333, 733333333000000000))
        self.assertGreater(fallback.error_seconds, integer.error_seconds)
        maximum = self.metrics(platform="windows", qpf_hz=4294967295)
        self.assertEqual(maximum.error_seconds, fallback.error_seconds)

    def test_one_tick_is_retained_with_zero_lower_bound_and_unbounded_throughput(self):
        result = self.metrics(1)
        self.assertEqual(result.raw_operation_ticks, (1,))
        self.assertEqual(result.latency.lower, 0)
        self.assertEqual(result.latency.upper, Fraction(2, RATE))
        self.assertEqual(result.throughput.center, 512 * RATE)
        self.assertEqual(result.throughput.lower, 256 * RATE)
        self.assertIsNone(result.throughput.upper)
        for metric in (result.latency, result.throughput, result.p95, result.p99):
            pair = self.m.paired_interval(metric, metric)
            self.assertEqual(pair.status, "INCONCLUSIVE")
            self.assertIs(pair.baseline, metric)

    def test_small_samples_are_not_removed_before_tail_ranking(self):
        result = self.m.counter_intervals([1] + list(range(10002, 10021)), 100000, 10240)
        self.assertEqual(len(result.operation_durations), 20)
        self.assertEqual(result.operation_durations[0].lower, 0)
        self.assertEqual(result.p95.center, Fraction(10019, RATE))
        self.assertEqual(result.p99.center, Fraction(10020, RATE))

    def test_throughput_inverts_batch_endpoints(self):
        result = self.metrics()
        self.assertEqual(result.throughput.center, Fraction(512 * RATE, 20000))
        self.assertEqual(result.throughput.lower, Fraction(512 * RATE, 20001))
        self.assertEqual(result.throughput.upper, Fraction(512 * RATE, 19999))

    def test_ranked_interval_encloses_every_small_permutation(self):
        values = [self.m.Interval(5, 2, 7), self.m.Interval(1, 0, 6), self.m.Interval(9, 8, 12)]
        ranked = self.m.ranked_interval(values, Fraction(2, 3))
        self.assertEqual((ranked.center, ranked.lower, ranked.upper), (5, 2, 7))
        possible = [sorted(example)[1] for example in itertools.product(range(2, 8), range(7), range(8, 13))]
        self.assertEqual((min(possible), max(possible)), (2, 7))
        self.assertTrue(all(ranked.lower <= value <= ranked.upper for value in possible))
        for ordering in itertools.permutations(values):
            self.assertEqual(self.m.ranked_interval(ordering, Fraction(2, 3)), ranked)

    def test_ranked_unbounded_endpoint_is_not_replaced_by_a_number(self):
        ranked = self.m.ranked_interval([self.m.Interval(1, 1, 1), self.m.Interval(2, 1, None)], Fraction(99, 100))
        self.assertEqual(ranked.center, 2)
        self.assertIsNone(ranked.upper)

    def test_ratio_divides_opposite_endpoints_and_preserves_inputs(self):
        baseline = self.m.Interval(100, 90, 110)
        candidate = self.m.Interval(200, 180, 220)
        result = self.m.paired_interval(baseline, candidate)
        self.assertEqual((result.center, result.lower, result.upper), (2, Fraction(18, 11), Fraction(22, 9)))
        self.assertEqual(result.lower_relative_deviation, Fraction(2, 11))
        self.assertEqual(result.upper_relative_deviation, Fraction(2, 9))
        self.assertEqual(result.status, "INCONCLUSIVE")
        self.assertIs(result.baseline, baseline)
        self.assertIs(result.candidate, candidate)

    def test_exact_budget_boundary_passes_but_arbitrarily_small_excess_does_not(self):
        baseline = self.m.Interval(100000, 100000, 100000)
        exact = self.m.paired_interval(baseline, self.m.Interval(100000, 99900, 100100))
        self.assertEqual(exact.status, "WITHIN_BUDGET")
        self.assertEqual(exact.upper_relative_deviation, Fraction(1, 1000))
        above = self.m.paired_interval(baseline, self.m.Interval(100000, 99900, 100100 + Fraction(1, 10 ** 100)))
        self.assertEqual(above.status, "INCONCLUSIVE")
        self.assertGreater(above.upper_relative_deviation, Fraction(1, 1000))

    def test_deck_pair_threshold_uses_ratio_budget_rather_than_per_duration_budget(self):
        short = self.metrics(2000).latency
        boundary = self.metrics(2001).latency
        self.assertEqual(self.m.paired_interval(short, short).status, "INCONCLUSIVE")
        accepted = self.m.paired_interval(boundary, boundary)
        self.assertEqual(accepted.status, "WITHIN_BUDGET")
        self.assertEqual(accepted.upper_relative_deviation, Fraction(1, 1000))

    def test_windows_fallback_pair_threshold_keeps_nanosecond_rounding(self):
        short = self.metrics(3468, platform="windows", qpf_hz=12345679).latency
        long = self.metrics(3469, platform="windows", qpf_hz=12345679).latency
        self.assertEqual(self.m.paired_interval(short, short).status, "INCONCLUSIVE")
        self.assertEqual(self.m.paired_interval(long, long).status, "WITHIN_BUDGET")

    def test_zero_candidate_lower_endpoint_invalidates_entire_paired_metric(self):
        result = self.m.paired_interval(self.m.Interval(2, 2, 2), self.m.Interval(1, 0, 2))
        self.assertEqual(result.status, "INCONCLUSIVE")
        self.assertEqual((result.center, result.lower, result.upper), (Fraction(1, 2), 0, 1))

    def test_zero_baseline_lower_endpoint_retains_unbounded_ratio(self):
        result = self.m.paired_interval(self.m.Interval(1, 0, 2), self.m.Interval(2, 2, 2))
        self.assertEqual(result.status, "INCONCLUSIVE")
        self.assertEqual(result.lower, 1)
        self.assertIsNone(result.upper)

    def test_throughput_ratio_orientation_matches_independent_byte_time_algebra(self):
        a = self.m.counter_intervals([20000], 20000, 512).throughput
        b = self.m.counter_intervals([40000], 40000, 768).throughput
        result = self.m.paired_interval(a, b)
        self.assertEqual(result.center, Fraction(3, 4))
        self.assertEqual(result.lower, Fraction(59997, 80002))
        self.assertEqual(result.upper, Fraction(60003, 79998))
        self.assertEqual(result.status, "WITHIN_BUDGET")

    def test_huge_raw_ticks_never_round_through_float(self):
        ticks = 10 ** 100 + 1
        result = self.m.counter_intervals([ticks, ticks - 1], ticks * 2, 1024)
        self.assertEqual(result.latency.center, Fraction(ticks * 2, RATE))
        self.assertEqual(result.operation_durations[0].center - result.operation_durations[1].center, Fraction(1, RATE))
        self.assertEqual(result.raw_operation_ticks, (ticks, ticks - 1))

    def test_malformed_or_zero_measurements_reject_the_entire_input(self):
        for raw in ([], [0], [-1], [True], [1.5], ["1"], [20001], "20000", {20000}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.m.counter_intervals(raw, 20000, 512)
        for batch in (None, False, 0, -1, 20000.0, "20000"):
            with self.subTest(batch=batch), self.assertRaises(ValueError):
                self.m.counter_intervals([1], batch, 512)
        for count in (None, True, 0, -1, 512.0):
            with self.subTest(bytes_completed=count), self.assertRaises(ValueError):
                self.m.counter_intervals([1], 20000, count)

    def test_windows_unknown_or_out_of_domain_frequency_is_not_inferred(self):
        for frequency in (None, False, 0, -1, 10000000.0, "10000000", 4294967296):
            with self.subTest(frequency=frequency), self.assertRaises(ValueError):
                self.metrics(platform="windows", qpf_hz=frequency)
        with self.assertRaises(ValueError):
            self.metrics(platform="deck", qpf_hz=10000000)
        with self.assertRaises(ValueError):
            self.metrics(platform="unknown")

    def test_inexact_or_reversed_intervals_and_invalid_ranks_reject(self):
        for arguments in ((1.0, 0, 2), (True, 0, 2), (1, -1, 2), (1, 2, 3), (1, 0, 0), (0, 0, 1)):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.m.Interval(*arguments)
        for percentile in (0, 2, True, .95, Fraction(-1, 2)):
            with self.subTest(percentile=percentile), self.assertRaises(ValueError):
                self.m.ranked_interval([self.m.Interval(1, 1, 1)], percentile)
        with self.assertRaises(ValueError):
            self.m.ranked_interval([], Fraction(95, 100))
        with self.assertRaises(ValueError):
            self.m.paired_interval(None, self.m.Interval(1, 1, 1))

    def test_compiled_floor_models_are_enclosed_by_counter_bounds(self):
        # Independent integer models of the accepted compiled equations, not helper formulas.
        for platform, frequency in (("deck", 1000000000), ("windows", 10000000), ("windows", 12345679), ("windows", 4294967295)):
            for start, delta, offset in itertools.product(range(1, 9), range(1, 10), (0, 1, 9)):
                ns0 = start * 1000000000 // frequency
                ns1 = (start + delta) * 1000000000 // frequency
                before = (ns0 + offset) * 733333333 // 1000000000
                after = (ns1 + offset) * 733333333 // 1000000000
                raw = after - before
                kwargs = {"platform": platform, **({"qpf_hz": frequency} if platform == "windows" else {})}
                if raw == 0:
                    with self.assertRaises(ValueError):
                        self.metrics(raw, **kwargs)
                else:
                    interval = self.metrics(raw, **kwargs).latency
                    actual = Fraction(delta, frequency)
                    self.assertLessEqual(interval.lower, actual)
                    self.assertGreaterEqual(interval.upper, actual)


if __name__ == "__main__":
    unittest.main()

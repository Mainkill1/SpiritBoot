"""Conditional counter-conversion arithmetic only; no runtime qualification.

All values are exact rationals. ``None`` is an unbounded upper endpoint, never
an inferred finite value. The caller must separately qualify clock provenance,
host context, operation completeness, and statistical/acceptance policy.
"""
from dataclasses import dataclass
from fractions import Fraction

RDTSC_HZ = 733333333
CONVERSION_BUDGET = Fraction(1, 1000)


def _exact(value, name):
    if type(value) is int or isinstance(value, Fraction):
        return Fraction(value)
    raise ValueError(f"{name} must be an exact integer or Fraction")


@dataclass(frozen=True)
class Interval:
    center: Fraction
    lower: Fraction
    upper: Fraction | None

    def __post_init__(self):
        center, lower = _exact(self.center, "center"), _exact(self.lower, "lower")
        upper = None if self.upper is None else _exact(self.upper, "upper")
        if center <= 0 or lower < 0 or lower > center or (upper is not None and upper < center):
            raise ValueError("interval must have positive center and ordered nonnegative bounds")
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


@dataclass(frozen=True)
class CounterIntervals:
    raw_operation_ticks: tuple[int, ...]
    raw_batch_ticks: int
    bytes_completed: int
    platform: str
    qpf_hz: int | None
    counter_hz: int
    error_seconds: Fraction
    operation_durations: tuple[Interval, ...]
    latency: Interval
    throughput: Interval
    p95: Interval
    p99: Interval


@dataclass(frozen=True)
class PairedInterval:
    baseline: Interval
    candidate: Interval
    center: Fraction
    lower: Fraction
    upper: Fraction | None
    lower_relative_deviation: Fraction
    upper_relative_deviation: Fraction | None
    status: str
    reason: str | None


def ranked_interval(values, percentile):
    """Nearest-rank quantile of centers and, separately, each endpoint."""
    if not isinstance(values, (list, tuple)) or not values or any(not isinstance(v, Interval) for v in values):
        raise ValueError("rank requires a nonempty ordered collection of intervals")
    percentile = _exact(percentile, "percentile")
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    index = (len(values) * percentile.numerator + percentile.denominator - 1) // percentile.denominator - 1
    uppers = sorted((v.upper for v in values), key=lambda v: (v is None, Fraction(0) if v is None else v))
    return Interval(sorted(v.center for v in values)[index], sorted(v.lower for v in values)[index], uppers[index])


def counter_intervals(raw_operation_ticks, raw_batch_ticks, bytes_completed, *, platform="deck", qpf_hz=None):
    """Preserve all raw ticks and derive conditional latency/throughput bounds.

    Windows frequency is explicit input, not an observation made by this helper.
    Missing, malformed or zero deltas reject the entire input. Small positive
    deltas remain present, including bounds that overlap zero.
    """
    if (not isinstance(raw_operation_ticks, (list, tuple)) or not raw_operation_ticks
            or any(type(t) is not int or t <= 0 for t in raw_operation_ticks)
            or type(raw_batch_ticks) is not int or raw_batch_ticks <= 0
            or type(bytes_completed) is not int or bytes_completed <= 0):
        raise ValueError("requires positive integer operation ticks, batch ticks and completed bytes")
    if max(raw_operation_ticks) > raw_batch_ticks:
        raise ValueError("an operation duration exceeds the enclosing batch")
    error = Fraction(1, RDTSC_HZ)
    if platform == "deck":
        if qpf_hz is not None:
            raise ValueError("Deck cannot inherit Windows frequency context")
    elif platform == "windows":
        if type(qpf_hz) is not int or not 1 <= qpf_hz <= 4294967295:
            raise ValueError("Windows requires explicit positive QPF within the reviewed uint32 domain")
        if 1000000000 % qpf_hz:
            error += Fraction(1, 1000000000)
    else:
        raise ValueError("unsupported counter platform")

    def duration(ticks):
        center = Fraction(ticks, RDTSC_HZ)
        return Interval(center, max(Fraction(0), center - error), center + error)

    raw = tuple(raw_operation_ticks)
    operations = tuple(duration(ticks) for ticks in raw)
    latency = duration(raw_batch_ticks)
    throughput = Interval(bytes_completed / latency.center, bytes_completed / latency.upper,
                          None if latency.lower == 0 else bytes_completed / latency.lower)
    return CounterIntervals(raw, raw_batch_ticks, bytes_completed, platform, qpf_hz, RDTSC_HZ, error,
                            operations, latency, throughput, ranked_interval(operations, Fraction(95, 100)),
                            ranked_interval(operations, Fraction(99, 100)))


def paired_interval(baseline, candidate):
    """Bound candidate/baseline and grade only the fixed 0.1% arithmetic budget.

    No endpoint or observation is discarded. A zero lower endpoint, unbounded
    endpoint or excessive conversion uncertainty makes this entire paired metric
    INCONCLUSIVE. WITHIN_BUDGET supplies no clock or performance acceptance.
    """
    if not isinstance(baseline, Interval) or not isinstance(candidate, Interval):
        raise ValueError("pair requires baseline and candidate intervals")
    center = candidate.center / baseline.center
    lower = Fraction(0) if baseline.upper is None else candidate.lower / baseline.upper
    upper = None if candidate.upper is None or baseline.lower == 0 else candidate.upper / baseline.lower
    lower_deviation = (center - lower) / center
    upper_deviation = None if upper is None else (upper - center) / center
    if baseline.lower == 0 or candidate.lower == 0:
        reason = "zero lower endpoint"
    elif baseline.upper is None or candidate.upper is None:
        reason = "unbounded endpoint"
    elif lower_deviation > CONVERSION_BUDGET or upper_deviation > CONVERSION_BUDGET:
        reason = "conversion uncertainty exceeds paired 0.1% budget"
    else:
        reason = None
    return PairedInterval(baseline, candidate, center, lower, upper, lower_deviation, upper_deviation,
                          "WITHIN_BUDGET" if reason is None else "INCONCLUSIVE", reason)

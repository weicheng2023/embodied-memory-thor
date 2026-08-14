"""Pure statistics for paired support-query mutation attribution."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def paired_mean_interval(
    query_values: Sequence[float],
    control_values: Sequence[float],
    *,
    t_critical: float,
) -> dict[str, Any]:
    """Return a fixed-design paired mean difference interval."""

    if len(query_values) != len(control_values) or len(query_values) < 2:
        raise ValueError("paired samples must have equal length of at least two")
    if not math.isfinite(t_critical) or t_critical <= 0:
        raise ValueError("t_critical must be finite and positive")
    query = [float(value) for value in query_values]
    control = [float(value) for value in control_values]
    if not all(math.isfinite(value) for value in (*query, *control)):
        raise ValueError("paired samples must be finite")
    differences = [left - right for left, right in zip(query, control)]
    count = len(differences)
    mean = sum(differences) / count
    sample_variance = sum((value - mean) ** 2 for value in differences) / (
        count - 1
    )
    standard_error = math.sqrt(sample_variance / count)
    half_width = t_critical * standard_error
    ordered = sorted(differences)
    midpoint = count // 2
    median = (
        ordered[midpoint]
        if count % 2
        else (ordered[midpoint - 1] + ordered[midpoint]) / 2.0
    )
    return {
        "pair_count": count,
        "query_mean": sum(query) / count,
        "control_mean": sum(control) / count,
        "mean_paired_difference": mean,
        "median_paired_difference": median,
        "minimum_paired_difference": ordered[0],
        "maximum_paired_difference": ordered[-1],
        "positive_difference_count": sum(value > 0 for value in differences),
        "sample_standard_deviation_of_differences": math.sqrt(sample_variance),
        "standard_error": standard_error,
        "lower_bound": mean - half_width,
        "upper_bound": mean + half_width,
        "t_critical": t_critical,
    }


def classify_paired_attribution(
    *,
    endpoint_intervals: Mapping[str, Mapping[str, Any]],
    practical_margins: Mapping[str, float],
    control_logical_change_count: int,
    control_identity_change_count: int,
    query_logical_change_count: int,
    query_identity_change_count: int,
    failed_query_count: int,
) -> dict[str, Any]:
    """Classify a frozen paired design without outcome-dependent thresholds."""

    if set(endpoint_intervals) != set(practical_margins):
        raise ValueError("endpoint intervals and practical margins must align")
    if any(float(margin) <= 0 for margin in practical_margins.values()):
        raise ValueError("practical margins must be positive")
    if failed_query_count:
        return {
            "classification": "incomplete_failed_query",
            "effect_endpoints": [],
            "below_margin_endpoints": [],
        }
    if control_logical_change_count or control_identity_change_count:
        return {
            "classification": "background_state_integrity_change_inconclusive",
            "effect_endpoints": [],
            "below_margin_endpoints": [],
        }
    if query_logical_change_count or query_identity_change_count:
        return {
            "classification": "query_specific_material_effect_supported",
            "effect_endpoints": ["logical_or_identity_state"],
            "below_margin_endpoints": [],
        }
    effect_endpoints = sorted(
        endpoint
        for endpoint, interval in endpoint_intervals.items()
        if float(interval["lower_bound"]) > float(practical_margins[endpoint])
    )
    below_margin = sorted(
        endpoint
        for endpoint, interval in endpoint_intervals.items()
        if float(interval["upper_bound"]) < float(practical_margins[endpoint])
    )
    if effect_endpoints:
        classification = "query_specific_material_effect_supported"
    elif len(below_margin) == len(endpoint_intervals):
        classification = "no_material_query_effect_supported"
    else:
        classification = "paired_attribution_inconclusive"
    return {
        "classification": classification,
        "effect_endpoints": effect_endpoints,
        "below_margin_endpoints": below_margin,
    }

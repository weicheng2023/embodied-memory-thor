"""Deterministic, panel-separated descriptive analysis for formal Phase 5 v5."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class FormalAnalysisError(ValueError):
    """Raised when frozen inputs or the matched matrix violate the contract."""


MECHANISM_COUNT_FIELDS = (
    "memory_guided_action_count",
    "old_viewpoint_miss_count",
    "stale_record_recovery_count",
    "shared_search_coverage_action_count",
    "shared_search_entry_alignment_action_count",
    "shared_search_entry_recovery_action_count",
    "shared_route_action_recovery_attempt_count",
    "shared_route_action_recovery_action_count",
    "shared_route_action_recovered_failure_count",
    "shared_route_action_recovery_terminal_failure_count",
    "target_lock_interaction_recovery_action_count",
    "invalid_action_count",
    "invalid_planner_decision_count",
    "target_lock_terminal_failure_count",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_digest(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _number(value: Any, *, field: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FormalAnalysisError(f"{field} must be numeric")
    if value < 0:
        raise FormalAnalysisError(f"{field} must be non-negative")
    return value


def _clean_number(value: float | int) -> float | int:
    if isinstance(value, int):
        return value
    rounded = round(float(value), 6)
    return int(rounded) if rounded.is_integer() else rounded


def _summary(values: Sequence[float | int]) -> dict[str, float | int]:
    if not values:
        raise FormalAnalysisError("cannot summarize an empty sequence")
    return {
        "n": len(values),
        "mean": _clean_number(statistics.fmean(values)),
        "median": _clean_number(statistics.median(values)),
        "minimum": _clean_number(min(values)),
        "maximum": _clean_number(max(values)),
        "total": _clean_number(sum(values)),
    }


def validate_analysis_config(config: Mapping[str, Any]) -> None:
    if config.get("analysis_version") != (
        "phase5-real-thor-formal-descriptive-analysis-v1"
    ):
        raise FormalAnalysisError("unexpected analysis_version")
    if config.get("expected_episode_count") != 54:
        raise FormalAnalysisError("expected_episode_count must be 54")
    panels = tuple(config.get("panel_order", ()))
    if panels != ("r1_stable", "r2_stable", "r1_stale"):
        raise FormalAnalysisError("panel order changed")
    variants = tuple(config.get("variant_order", ()))
    if variants != ("no_memory", "short_memory_k2", "object_memory"):
        raise FormalAnalysisError("variant order changed")
    configuration_order = config.get("configuration_order")
    if not isinstance(configuration_order, Mapping):
        raise FormalAnalysisError("configuration_order is missing")
    if any(len(configuration_order.get(panel, ())) != 6 for panel in panels):
        raise FormalAnalysisError("each panel must have six configurations")
    metrics = tuple(config.get("performance_metrics", ()))
    if metrics != (
        "steps",
        "target_reacquisition_action_count",
        "translation_action_count",
        "translation_distance_meters",
        "search_rotation_count",
        "repeated_viewpoint_visit_count",
    ):
        raise FormalAnalysisError("performance metric contract changed")
    comparisons = tuple(tuple(item) for item in config.get("paired_comparisons", ()))
    if comparisons != (
        ("object_memory", "no_memory"),
        ("object_memory", "short_memory_k2"),
        ("short_memory_k2", "no_memory"),
    ):
        raise FormalAnalysisError("paired comparison contract changed")
    if config.get("difference_definition") != "first_variant_minus_second_variant":
        raise FormalAnalysisError("difference definition changed")
    if config.get("performance_direction") != "lower_is_better":
        raise FormalAnalysisError("performance direction changed")
    if config.get("panel_pooling_allowed") is not False:
        raise FormalAnalysisError("panel pooling must remain disabled")
    if config.get("significance_testing_allowed") is not False:
        raise FormalAnalysisError("significance testing must remain disabled")


def validate_completion_evidence(
    evidence: Mapping[str, Any], config: Mapping[str, Any]
) -> None:
    expected = {
        "code_revision": config["source_code_revision"],
        "matrix_complete": True,
        "integrity_valid": True,
        "included_in_formal_aggregate": True,
        "completed_episode_count": 54,
        "task_success_count": 54,
        "integrity_error_count": 0,
        "manifest_digest": config["expected_manifest_digest"],
        "result_digest": config["expected_result_digest"],
        "analysis_computed_in_this_record": False,
    }
    errors = [key for key, value in expected.items() if evidence.get(key) != value]
    if evidence.get("artifact_sha256", {}).get("formal_summary.json") != config.get(
        "source_summary_sha256"
    ):
        errors.append("artifact_sha256.formal_summary.json")
    if errors:
        raise FormalAnalysisError(
            "completion evidence does not match frozen analysis input: "
            + ",".join(errors)
        )


def _validated_rows(
    summary: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    expected_top = {
        "code_revision": config["source_code_revision"],
        "executor_version": config["source_executor_version"],
        "expected_episode_count": 54,
        "completed_episode_count": 54,
        "matrix_complete": True,
        "integrity_valid": True,
        "included_in_formal_aggregate": True,
        "task_success_count": 54,
        "task_failure_count": 0,
        "manifest_digest": config["expected_manifest_digest"],
        "result_digest": config["expected_result_digest"],
    }
    errors = [key for key, value in expected_top.items() if summary.get(key) != value]
    rows = summary.get("rows")
    if not isinstance(rows, list) or len(rows) != 54:
        errors.append("rows")
    if errors:
        raise FormalAnalysisError("invalid formal summary: " + ",".join(errors))

    lookup: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    panels = tuple(config["panel_order"])
    variants = tuple(config["variant_order"])
    configurations = config["configuration_order"]
    expected_order: list[tuple[str, str, str]] = []
    for panel in panels:
        for configuration_id in configurations[panel]:
            for variant in variants:
                expected_order.append((panel, configuration_id, variant))

    actual_order: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise FormalAnalysisError("formal row must be an object")
        key = (
            str(row.get("panel", "")),
            str(row.get("configuration_id", "")),
            str(row.get("memory", "")),
        )
        if key in lookup:
            raise FormalAnalysisError(f"duplicate formal row: {key}")
        if row.get("success") is not True:
            raise FormalAnalysisError(f"formal task failure: {key}")
        if row.get("information_boundary_passed") is not True:
            raise FormalAnalysisError(f"information boundary failure: {key}")
        if row.get("integrity_errors") != []:
            raise FormalAnalysisError(f"integrity error: {key}")
        for metric in config["performance_metrics"]:
            _number(row.get(metric), field=f"{key}:{metric}")
        for field in MECHANISM_COUNT_FIELDS:
            _number(row.get(field), field=f"{key}:{field}")
        lookup[key] = row
        actual_order.append(key)
    if actual_order != expected_order:
        raise FormalAnalysisError("formal row order or matched matrix changed")
    return lookup


def _paired_metric(
    *,
    configurations: Sequence[str],
    lookup: Mapping[tuple[str, str, str], Mapping[str, Any]],
    panel: str,
    first: str,
    second: str,
    metric: str,
) -> dict[str, Any]:
    differences: list[float | int] = []
    paired_rows: list[dict[str, Any]] = []
    for configuration_id in configurations:
        first_value = _number(
            lookup[(panel, configuration_id, first)][metric], field=metric
        )
        second_value = _number(
            lookup[(panel, configuration_id, second)][metric], field=metric
        )
        difference = _clean_number(first_value - second_value)
        differences.append(difference)
        paired_rows.append(
            {
                "configuration_id": configuration_id,
                "first_value": _clean_number(first_value),
                "second_value": _clean_number(second_value),
                "difference": difference,
            }
        )
    return {
        "difference_summary": _summary(differences),
        "improvement_count": sum(value < 0 for value in differences),
        "tie_count": sum(value == 0 for value in differences),
        "regression_count": sum(value > 0 for value in differences),
        "paired_rows": paired_rows,
    }


def build_descriptive_analysis(
    summary: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[str, Any]:
    validate_analysis_config(config)
    lookup = _validated_rows(summary, config)
    variants = tuple(config["variant_order"])
    metrics = tuple(config["performance_metrics"])
    result_panels: list[dict[str, Any]] = []

    for panel in config["panel_order"]:
        configurations = tuple(config["configuration_order"][panel])
        variant_summaries: dict[str, Any] = {}
        for variant in variants:
            rows = [lookup[(panel, configuration_id, variant)] for configuration_id in configurations]
            variant_summaries[variant] = {
                "episode_count": len(rows),
                "success_count": sum(row["success"] is True for row in rows),
                "success_rate": _clean_number(
                    sum(row["success"] is True for row in rows) / len(rows)
                ),
                "performance": {
                    metric: _summary(
                        [_number(row[metric], field=metric) for row in rows]
                    )
                    for metric in metrics
                },
                "mechanism_totals": {
                    field: _clean_number(
                        sum(_number(row[field], field=field) for row in rows)
                    )
                    for field in MECHANISM_COUNT_FIELDS
                },
                "k2_eviction_observed_count": sum(
                    row.get("short_memory_evicted_before_reacquisition") is True
                    for row in rows
                ),
                "information_boundary_pass_count": sum(
                    row.get("information_boundary_passed") is True for row in rows
                ),
            }

        paired_comparisons: list[dict[str, Any]] = []
        for first, second in config["paired_comparisons"]:
            paired_comparisons.append(
                {
                    "comparison": f"{first}_vs_{second}",
                    "difference_definition": "first_variant_minus_second_variant",
                    "performance_direction": "lower_is_better",
                    "metrics": {
                        metric: _paired_metric(
                            configurations=configurations,
                            lookup=lookup,
                            panel=panel,
                            first=first,
                            second=second,
                            metric=metric,
                        )
                        for metric in metrics
                    },
                }
            )
        result_panels.append(
            {
                "panel": panel,
                "configuration_count": len(configurations),
                "episode_count": len(configurations) * len(variants),
                "configuration_order": list(configurations),
                "variant_summaries": variant_summaries,
                "paired_comparisons": paired_comparisons,
            }
        )

    result: dict[str, Any] = {
        "analysis_version": config["analysis_version"],
        "source_code_revision": summary["code_revision"],
        "source_summary_sha256": config["source_summary_sha256"],
        "source_manifest_digest": summary["manifest_digest"],
        "source_result_digest": summary["result_digest"],
        "matrix_complete": True,
        "integrity_valid": True,
        "included_episode_count": 54,
        "panel_pooling_used": False,
        "significance_test_used": False,
        "claim_boundary": config["claim_boundary"],
        "panels": result_panels,
    }
    result["analysis_digest"] = stable_digest(result)
    return result


def render_markdown(analysis: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 5 Formal-v5 Descriptive Results",
        "",
        f"Analysis digest: `{analysis['analysis_digest']}`",
        "",
        "The fixed matrix contains 54/54 integrity-valid real AI2-THOR episodes. "
        "Results below keep the three panels separate and are descriptive only.",
        "",
    ]
    label = {
        "steps": "Evaluated steps",
        "target_reacquisition_action_count": "Reacquisition actions",
        "translation_action_count": "Translation actions",
        "translation_distance_meters": "Translation distance (m)",
        "search_rotation_count": "Search rotations",
        "repeated_viewpoint_visit_count": "Repeated viewpoints",
    }
    for panel in analysis["panels"]:
        lines.extend(
            [
                f"## {panel['panel']}",
                "",
                "All variants succeeded in 6/6 matched configurations.",
                "",
                "| Metric | No memory mean/median [range] | K=2 mean/median [range] | Object mean/median [range] | Object−No mean diff (better/tie/worse) | Object−K2 mean diff (better/tie/worse) |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        summaries = panel["variant_summaries"]
        comparisons = {item["comparison"]: item for item in panel["paired_comparisons"]}
        for metric, title in label.items():
            cells: list[str] = []
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                stats = summaries[variant]["performance"][metric]
                cells.append(
                    f"{stats['mean']}/{stats['median']} [{stats['minimum']}, {stats['maximum']}]"
                )
            comparison_cells: list[str] = []
            for comparison in (
                "object_memory_vs_no_memory",
                "object_memory_vs_short_memory_k2",
            ):
                item = comparisons[comparison]["metrics"][metric]
                comparison_cells.append(
                    f"{item['difference_summary']['mean']} "
                    f"({item['improvement_count']}/{item['tie_count']}/{item['regression_count']})"
                )
            lines.append(
                f"| {title} | {cells[0]} | {cells[1]} | {cells[2]} | "
                f"{comparison_cells[0]} | {comparison_cells[1]} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "Differences are first variant minus second variant; for all performance "
            "metrics, lower is better. Each comparison has only six deterministic "
            "matched configurations. No significance test, panel pooling, or broad "
            "generalization is used. Exact per-configuration paired rows and mechanism "
            "totals are retained in the machine-readable result.",
            "",
        ]
    )
    return "\n".join(lines)

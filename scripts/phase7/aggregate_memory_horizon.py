#!/usr/bin/env python3
"""Validate and descriptively aggregate a frozen Phase-7B matrix summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase7.holdout import validate_public_artifact  # noqa: E402
from embodied_memory_thor.phase7.recent_memory import (  # noqa: E402
    PHASE7B_RECENT_CAPACITIES,
    PHASE7B_VARIANTS,
)


METRICS = (
    "steps",
    "target_reacquisition_action_count",
    "translation_action_count",
    "translation_distance_meters",
    "search_rotation_count",
    "repeated_viewpoint_visit_count",
    "memory_guided_action_count",
    "memory_retrieval_count",
    "target_record_age_actions_at_reacquisition",
    "shared_search_entry_recovery_action_count",
    "shared_search_coverage_action_count",
    "shared_route_action_recovery_action_count",
)
SUCCESS_BUDGETS = (18, 72, 2048)
COMPARISONS = (
    ("recent_memory_k2", "no_memory"),
    ("recent_memory_k4", "no_memory"),
    ("recent_memory_k8", "no_memory"),
    ("object_memory", "no_memory"),
    ("object_memory", "recent_memory_k8"),
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _summary(values: Sequence[float | int]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "range": None}
    return {
        "count": len(values),
        "mean": round(float(statistics.mean(values)), 6),
        "median": round(float(statistics.median(values)), 6),
        "range": [min(values), max(values)],
    }


def _paired(
    by_variant: Mapping[str, Mapping[str, Mapping[str, Any]]],
    configuration_order: Sequence[str],
    metric: str,
    variant: str,
    reference: str,
) -> dict[str, Any]:
    differences: list[float | int] = []
    available: list[str] = []
    for configuration_id in configuration_order:
        variant_value = _number(by_variant[configuration_id][variant].get(metric))
        reference_value = _number(
            by_variant[configuration_id][reference].get(metric)
        )
        if variant_value is None or reference_value is None:
            continue
        differences.append(variant_value - reference_value)
        available.append(configuration_id)
    return {
        "definition": f"{variant}_minus_{reference}; lower cost is better",
        "available_configuration_ids": available,
        "differences": differences,
        "summary": _summary(differences),
        "better_tie_worse": [
            sum(value < 0 for value in differences),
            sum(value == 0 for value in differences),
            sum(value > 0 for value in differences),
        ],
    }


def aggregate(summary: Mapping[str, Any]) -> dict[str, Any]:
    digest_payload = dict(summary)
    expected_result_digest = str(digest_payload.pop("result_digest", ""))
    if stable_digest(digest_payload) != expected_result_digest:
        raise ValueError("Phase7B source result digest mismatch")
    if summary.get("matrix_complete") is not True:
        raise ValueError("Phase7B aggregation requires a complete matrix")
    if summary.get("integrity_valid") is not True:
        raise ValueError("Phase7B aggregation requires an integrity-valid matrix")
    rows = summary.get("rows", [])
    if not isinstance(rows, list) or len(rows) != 30:
        raise ValueError("Phase7B aggregation requires exactly 30 rows")

    configuration_order: list[str] = []
    by_variant: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("Phase7B result row must be an object")
        configuration_id = str(row.get("configuration_id", ""))
        variant = str(row.get("memory", ""))
        if configuration_id not in by_variant:
            configuration_order.append(configuration_id)
            by_variant[configuration_id] = {}
        if variant in by_variant[configuration_id]:
            raise ValueError("duplicate Phase7B configuration/variant row")
        by_variant[configuration_id][variant] = row
    if len(configuration_order) != 6 or any(
        tuple(by_variant[configuration_id]) != PHASE7B_VARIANTS
        for configuration_id in configuration_order
    ):
        raise ValueError("Phase7B rows do not form six ordered variant quintets")
    if any(row.get("integrity_errors") for row in rows):
        raise ValueError("Phase7B row contains an integrity error")

    success = {
        variant: {
            "eventual": sum(
                by_variant[configuration_id][variant].get("success") is True
                for configuration_id in configuration_order
            ),
            **{
                f"at_{budget}": sum(
                    by_variant[configuration_id][variant].get(
                        f"success_at_{budget}"
                    )
                    is True
                    for configuration_id in configuration_order
                )
                for budget in SUCCESS_BUDGETS
            },
        }
        for variant in PHASE7B_VARIANTS
    }
    retention = {
        variant: {
            "present": sum(
                by_variant[configuration_id][variant].get(
                    "target_record_present_at_reacquisition"
                )
                is True
                for configuration_id in configuration_order
            ),
            "absent": sum(
                by_variant[configuration_id][variant].get(
                    "target_record_present_at_reacquisition"
                )
                is False
                for configuration_id in configuration_order
            ),
            "unknown": sum(
                by_variant[configuration_id][variant].get(
                    "target_record_present_at_reacquisition"
                )
                not in {True, False}
                for configuration_id in configuration_order
            ),
        }
        for variant in PHASE7B_VARIANTS
    }

    metrics: dict[str, Any] = {}
    for metric in METRICS:
        values = {
            variant: [
                value
                for configuration_id in configuration_order
                if (
                    value := _number(
                        by_variant[configuration_id][variant].get(metric)
                    )
                )
                is not None
            ]
            for variant in PHASE7B_VARIANTS
        }
        metrics[metric] = {
            "by_variant": {
                variant: _summary(values[variant]) for variant in PHASE7B_VARIANTS
            },
            "paired_differences": {
                f"{variant}_minus_{reference}": _paired(
                    by_variant,
                    configuration_order,
                    metric,
                    variant,
                    reference,
                )
                for variant, reference in COMPARISONS
            },
        }

    capacity_curve = [
        {
            "variant": variant,
            "k": PHASE7B_RECENT_CAPACITIES[variant],
            "target_retained_count": retention[variant]["present"],
            "mean_steps": metrics["steps"]["by_variant"][variant]["mean"],
            "mean_reacquisition_actions": metrics[
                "target_reacquisition_action_count"
            ]["by_variant"][variant]["mean"],
            "mean_target_record_age_actions": metrics[
                "target_record_age_actions_at_reacquisition"
            ]["by_variant"][variant]["mean"],
        }
        for variant in PHASE7B_RECENT_CAPACITIES
    ]
    result = {
        "analysis_version": "phase7b-memory-horizon-descriptive-analysis-v1",
        "source_code_revision": summary.get("code_revision"),
        "source_matrix_manifest_digest": summary.get("matrix_manifest_digest"),
        "source_result_digest": summary.get("result_digest"),
        "configuration_order": configuration_order,
        "variant_order": list(PHASE7B_VARIANTS),
        "success_counts": success,
        "target_retention_counts": retention,
        "capacity_curve": capacity_curve,
        "metrics": metrics,
        "panel_pooling_used": False,
        "significance_test_used": False,
        "claim_boundary": "paired descriptive Phase7B mechanism analysis over six configurations; recent capacity is controlled within one provider, while object-memory representation and retrieval remain confounded",
    }
    validate_public_artifact(result)
    result["analysis_digest"] = stable_digest(result)
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 7B Memory-Horizon Descriptive Result",
        "",
        "All values are descriptive over six paired R1-stable configurations.",
        "",
        "| Variant | Target retained | Success@18 | Eventual success | Mean steps | Mean reacquisition actions |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant in PHASE7B_VARIANTS:
        success = result["success_counts"][variant]
        retention = result["target_retention_counts"][variant]
        steps = result["metrics"]["steps"]["by_variant"][variant]["mean"]
        reacquisition = result["metrics"]["target_reacquisition_action_count"][
            "by_variant"
        ][variant]["mean"]
        lines.append(
            f"| `{variant}` | {retention['present']}/6 | "
            f"{success['at_18']}/6 | {success['eventual']}/6 | "
            f"{steps} | {reacquisition} |"
        )
    lines.extend(
        [
            "",
            "This mechanism table is separate from Phase 5 and Phase 7A. It does not claim complete causal isolation between recent and object memory.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary_path = args.summary.resolve()
    output_dir = args.output_dir.resolve()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    result = aggregate(summary)
    result["source_summary_sha256"] = _sha256(summary_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "memory_horizon_descriptive_results.json", result)
    (output_dir / "memory_horizon_descriptive_results.md").write_text(
        render_markdown(result), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

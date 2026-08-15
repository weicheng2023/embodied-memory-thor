#!/usr/bin/env python3
"""Validate and descriptively aggregate a frozen Phase-7A holdout summary."""

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
from embodied_memory_thor.phase7.holdout import PHASE7A_VARIANTS  # noqa: E402


METRICS = (
    "steps",
    "target_reacquisition_action_count",
    "translation_action_count",
    "translation_distance_meters",
    "search_rotation_count",
    "repeated_viewpoint_visit_count",
    "shared_search_entry_recovery_action_count",
    "shared_search_coverage_action_count",
    "shared_route_action_recovery_action_count",
)
SUCCESS_BUDGETS = (18, 72, 2048)


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
) -> dict[str, Any]:
    differences: list[float | int] = []
    available: list[str] = []
    for configuration_id in configuration_order:
        no_value = _number(by_variant[configuration_id]["no_memory"].get(metric))
        object_value = _number(
            by_variant[configuration_id]["object_memory"].get(metric)
        )
        if no_value is None or object_value is None:
            continue
        differences.append(object_value - no_value)
        available.append(configuration_id)
    return {
        "definition": "object_memory_minus_no_memory; lower cost is better",
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
        raise ValueError("Phase7A source result digest mismatch")
    if summary.get("matrix_complete") is not True:
        raise ValueError("Phase7A aggregation requires a complete matrix")
    if summary.get("integrity_valid") is not True:
        raise ValueError("Phase7A aggregation requires an integrity-valid matrix")
    rows = summary.get("rows", [])
    if not isinstance(rows, list) or len(rows) != 18:
        raise ValueError("Phase7A aggregation requires exactly 18 rows")
    configuration_order: list[str] = []
    by_variant: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("Phase7A result row must be an object")
        configuration_id = str(row.get("configuration_id", ""))
        variant = str(row.get("memory", ""))
        if configuration_id not in by_variant:
            configuration_order.append(configuration_id)
            by_variant[configuration_id] = {}
        if variant in by_variant[configuration_id]:
            raise ValueError("duplicate Phase7A configuration/variant row")
        by_variant[configuration_id][variant] = row
    if len(configuration_order) != 6 or any(
        tuple(by_variant[configuration_id]) != PHASE7A_VARIANTS
        for configuration_id in configuration_order
    ):
        raise ValueError("Phase7A rows do not form six ordered variant triplets")
    if any(row.get("integrity_errors") for row in rows):
        raise ValueError("Phase7A row contains an integrity error")

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
        for variant in PHASE7A_VARIANTS
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
            for variant in PHASE7A_VARIANTS
        }
        metrics[metric] = {
            "by_variant": {
                variant: _summary(values[variant]) for variant in PHASE7A_VARIANTS
            },
            "object_minus_no": _paired(
                by_variant, configuration_order, metric
            ),
        }
    result = {
        "analysis_version": "phase7a-holdout-descriptive-analysis-v1",
        "source_code_revision": summary.get("code_revision"),
        "source_matrix_manifest_digest": summary.get("matrix_manifest_digest"),
        "source_result_digest": summary.get("result_digest"),
        "configuration_order": configuration_order,
        "variant_order": list(PHASE7A_VARIANTS),
        "success_counts": success,
        "metrics": metrics,
        "panel_pooling_used": False,
        "significance_test_used": False,
        "claim_boundary": "paired descriptive Phase7A holdout analysis over six configurations; no significance or broad-generalization claim",
    }
    result["analysis_digest"] = stable_digest(result)
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    success = result["success_counts"]
    lines = [
        "# Phase 7A Holdout Descriptive Result",
        "",
        "All values are descriptive over six paired holdout configurations.",
        "",
        "| Variant | Success@18 | Success@72 | Eventual success | Mean steps | Mean reacquisition actions |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant in PHASE7A_VARIANTS:
        steps = result["metrics"]["steps"]["by_variant"][variant]["mean"]
        reacquisition = result["metrics"]["target_reacquisition_action_count"][
            "by_variant"
        ][variant]["mean"]
        lines.append(
            f"| `{variant}` | {success[variant]['at_18']}/6 | "
            f"{success[variant]['at_72']}/6 | {success[variant]['eventual']}/6 | "
            f"{steps} | {reacquisition} |"
        )
    step_pair = result["metrics"]["steps"]["object_minus_no"]
    reacq_pair = result["metrics"]["target_reacquisition_action_count"][
        "object_minus_no"
    ]
    lines.extend(
        [
            "",
            "Object-minus-no-memory paired step differences: "
            + str(step_pair["differences"]),
            "",
            "Object-minus-no-memory paired reacquisition differences: "
            + str(reacq_pair["differences"]),
            "",
            "This table does not modify or extend the Phase-5 result.",
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
    _write_json(output_dir / "holdout_descriptive_results.json", result)
    (output_dir / "holdout_descriptive_results.md").write_text(
        render_markdown(result), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

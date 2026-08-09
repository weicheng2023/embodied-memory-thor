"""Frozen Phase 3 pilot constants, aggregation, and acceptance checks."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Iterable, Mapping


PROTOCOL_VERSION = "phase3-v2"
SHORT_TERM_CAPACITY = 2
SEARCH_ORDER = ("Kitchen", "DiningArea", "SinkArea")
LAYOUT_SEEDS = (0, 1, 4, 5, 6, 7)
LAYOUT_SIGNATURES = {
    0: ("Kitchen", "SinkArea", "DiningArea"),
    1: ("DiningArea", "SinkArea", "Kitchen"),
    4: ("SinkArea", "DiningArea", "Kitchen"),
    5: ("Kitchen", "DiningArea", "SinkArea"),
    6: ("DiningArea", "Kitchen", "SinkArea"),
    7: ("SinkArea", "Kitchen", "DiningArea"),
}
VARIANT_PLANNERS = {
    "no_memory": "rule_based_no_memory",
    "short_memory": "short_memory",
    "object_memory": "object_memory",
}
CONDITIONS = {
    "t1_stable": {
        "task": "po_slice_apple_put_plate",
        "max_steps": 14,
        "stale_intervention": False,
    },
    "t2_stable": {
        "task": "po_find_book_after_distraction",
        "max_steps": 10,
        "stale_intervention": False,
    },
    "t1_stale": {
        "task": "po_slice_apple_put_plate",
        "max_steps": 18,
        "stale_intervention": True,
    },
}
METRICS = (
    "success",
    "steps",
    "invalid_action_count",
    "search_move_count",
    "repeated_region_visit_count",
    "memory_retrieval_count",
    "memory_hint_count",
    "memory_guided_action_count",
    "last_seen_hit_count",
    "stale_memory_miss_count",
    "stale_record_recovery_count",
    "recovery_search_move_count",
    "average_planning_latency_seconds",
    "total_episode_latency_seconds",
)


def build_protocol_manifest(
    *, code_revision: str, working_tree_dirty: bool, command: list[str]
) -> dict[str, Any]:
    """Create the immutable pre-run protocol payload."""

    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_status": "development_only" if working_tree_dirty else "formal_pilot",
        "code_revision": code_revision,
        "working_tree_dirty": working_tree_dirty,
        "command": list(command),
        "ordinary_episode_count": len(VARIANT_PLANNERS) * len(CONDITIONS) * len(LAYOUT_SEEDS),
        "variants": dict(VARIANT_PLANNERS),
        "conditions": CONDITIONS,
        "layout_seeds": list(LAYOUT_SEEDS),
        "layout_signatures": {
            str(seed): {
                "Apple": signature[0],
                "Knife": signature[1],
                "Plate": signature[2],
                "Book": signature[0],
                "DeskLamp": signature[1],
            }
            for seed, signature in LAYOUT_SIGNATURES.items()
        },
        "short_term_capacity": SHORT_TERM_CAPACITY,
        "fallback_search_order": list(SEARCH_ORDER),
        "stale_intervention": {
            "id": "phase3_v2_stale_apple_after_knife_departure",
            "trigger": "first departure from Knife region after successful Knife pickup",
            "destination": "Knife pre-intervention region just vacated by the agent",
            "planner_accessible": False,
        },
        "metric_fields": list(METRICS),
        "oracle_in_ordinary_aggregates": False,
        "interpretation_boundary": (
            "Descriptive controlled-mock E1 evidence only; no statistical significance "
            "or real AI2-THOR memory-performance claim."
        ),
    }


def add_matched_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add stale-minus-stable deltas for matched variant and layout."""

    stable = {
        (str(row["memory_variant"]), int(row["layout_seed"])): row
        for row in rows
        if row["condition"] == "t1_stable"
    }
    enriched: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        row["extra_steps_vs_stable"] = None
        row["extra_moves_vs_stable"] = None
        if row["condition"] == "t1_stale":
            reference = stable.get((str(row["memory_variant"]), int(row["layout_seed"])))
            if reference is not None:
                row["extra_steps_vs_stable"] = int(row["steps"]) - int(reference["steps"])
                row["extra_moves_vs_stable"] = int(row["search_move_count"]) - int(
                    reference["search_move_count"]
                )
        enriched.append(row)
    return enriched


def aggregate_results(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Compute descriptive counts, means, and ranges by condition and variant."""

    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["condition"]), str(row["memory_variant"]))].append(row)

    aggregates: list[dict[str, Any]] = []
    numeric_fields = (
        "steps",
        "search_move_count",
        "repeated_region_visit_count",
        "memory_guided_action_count",
        "last_seen_hit_count",
        "stale_memory_miss_count",
        "stale_record_recovery_count",
        "recovery_search_move_count",
    )
    for (condition, variant), group in sorted(groups.items()):
        result: dict[str, Any] = {
            "condition": condition,
            "memory_variant": variant,
            "episodes": len(group),
            "success_count": sum(bool(row["success"]) for row in group),
            "success_rate": mean(bool(row["success"]) for row in group),
            "information_leak_audit_count": sum(
                row.get("information_leak_audit_passed") is True for row in group
            ),
        }
        for field in numeric_fields:
            values = [float(row[field]) for row in group]
            result[f"mean_{field}"] = mean(values)
            result[f"min_{field}"] = min(values)
            result[f"max_{field}"] = max(values)
        aggregates.append(result)
    return aggregates


def evaluate_acceptance(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Evaluate the frozen Phase 3 behavioral acceptance conditions."""

    expected_keys = {
        (condition, variant, seed)
        for condition in CONDITIONS
        for variant in VARIANT_PLANNERS
        for seed in LAYOUT_SEEDS
    }
    actual_keys = {
        (str(row["condition"]), str(row["memory_variant"]), int(row["layout_seed"]))
        for row in rows
    }
    t2_rows = [row for row in rows if row["condition"] == "t2_stable"]
    no_memory_rows = [row for row in rows if row["memory_variant"] == "no_memory"]
    stale_rows = [row for row in rows if row["condition"] == "t1_stale"]
    stale_object_rows = [
        row
        for row in stale_rows
        if row["memory_variant"] == "object_memory"
    ]
    checks = {
        "complete_54_episode_matrix": actual_keys == expected_keys and len(rows) == 54,
        "all_ordinary_information_leak_audits_pass": all(
            row.get("information_leak_audit_passed") is True for row in rows
        ),
        "all_t2_ordered_subgoal_audits_pass": bool(t2_rows)
        and all(row.get("ordered_subgoal_passed") is True for row in t2_rows),
        "no_memory_systematic_search_completes": bool(no_memory_rows)
        and all(bool(row["success"]) for row in no_memory_rows)
        and all(int(row["search_move_count"]) > 0 for row in no_memory_rows),
        "all_stale_interventions_are_matched": len(stale_rows) == 18
        and all(int(row["intervention_count"]) == 1 for row in stale_rows),
        "object_memory_guides_both_stable_tasks": all(
            any(
                row["condition"] == condition
                and row["memory_variant"] == "object_memory"
                and int(row["memory_guided_action_count"]) > 0
                for row in rows
            )
            for condition in ("t1_stable", "t2_stable")
        ),
        "stale_miss_recovery_and_correction_observed": bool(stale_object_rows)
        and any(
            int(row["stale_memory_miss_count"]) > 0
            and int(row["stale_record_recovery_count"]) > 0
            and bool(row["success"])
            for row in stale_object_rows
        ),
    }
    return {"passed": all(checks.values()), "checks": checks}

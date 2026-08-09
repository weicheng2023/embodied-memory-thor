"""Tests for the frozen Phase 3 manifest, aggregation, and acceptance."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.evaluation.phase3_protocol import (  # noqa: E402
    CONDITIONS,
    LAYOUT_SEEDS,
    VARIANT_PLANNERS,
    add_matched_deltas,
    aggregate_results,
    build_protocol_manifest,
    evaluate_acceptance,
)


def _synthetic_rows() -> list[dict]:
    rows = []
    for condition in CONDITIONS:
        for variant in VARIANT_PLANNERS:
            for seed in LAYOUT_SEEDS:
                stale_object = condition == "t1_stale" and variant == "object_memory"
                rows.append(
                    {
                        "condition": condition,
                        "memory_variant": variant,
                        "layout_seed": seed,
                        "success": True,
                        "steps": 8,
                        "invalid_action_count": 0,
                        "search_move_count": 3,
                        "repeated_region_visit_count": 1,
                        "memory_retrieval_count": 1,
                        "memory_hint_count": int(variant == "object_memory"),
                        "memory_guided_action_count": int(variant == "object_memory"),
                        "last_seen_hit_count": int(
                            variant == "object_memory" and condition != "t1_stale"
                        ),
                        "stale_memory_miss_count": int(stale_object),
                        "stale_record_recovery_count": int(stale_object),
                        "recovery_search_move_count": int(stale_object),
                        "average_planning_latency_seconds": 0.001,
                        "total_episode_latency_seconds": 0.01,
                        "intervention_count": int(condition == "t1_stale"),
                        "information_leak_audit_passed": True,
                        "ordered_subgoal_passed": True if condition == "t2_stable" else None,
                    }
                )
    return rows


class Phase3ProtocolTests(unittest.TestCase):
    def test_manifest_freezes_six_unique_layouts_and_54_episodes(self) -> None:
        manifest = build_protocol_manifest(
            code_revision="abc123", working_tree_dirty=False, command=["python", "pilot"]
        )
        signatures = {
            (item["Apple"], item["Knife"], item["Plate"])
            for item in manifest["layout_signatures"].values()
        }
        self.assertEqual(54, manifest["ordinary_episode_count"])
        self.assertEqual(6, len(signatures))
        self.assertEqual(2, manifest["short_term_capacity"])
        self.assertEqual("phase3-v2", manifest["protocol_version"])
        self.assertIn("Knife", manifest["stale_intervention"]["destination"])

    def test_matched_deltas_and_aggregates_are_deterministic(self) -> None:
        rows = _synthetic_rows()
        stale = next(
            row
            for row in rows
            if row["condition"] == "t1_stale"
            and row["memory_variant"] == "object_memory"
            and row["layout_seed"] == 0
        )
        stale["steps"] = 10
        enriched = add_matched_deltas(rows)
        enriched_stale = next(
            row
            for row in enriched
            if row["condition"] == "t1_stale"
            and row["memory_variant"] == "object_memory"
            and row["layout_seed"] == 0
        )
        self.assertEqual(2, enriched_stale["extra_steps_vs_stable"])
        self.assertEqual(9, len(aggregate_results(enriched)))

    def test_acceptance_requires_complete_fair_matrix_and_stale_recovery(self) -> None:
        rows = _synthetic_rows()
        self.assertTrue(evaluate_acceptance(rows)["passed"])
        rows[0]["information_leak_audit_passed"] = False
        result = evaluate_acceptance(rows)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["all_ordinary_information_leak_audits_pass"])


if __name__ == "__main__":
    unittest.main()

"""Offline acceptance tests for the frozen Phase 5A4 protocol machinery."""

from __future__ import annotations

import unittest
from copy import deepcopy

from embodied_memory_thor.phase5.protocol import (
    FORMAL_EPISODE_COUNT,
    PHASE5_REQUIRED_METRICS,
    QualificationRecord,
    build_formal_manifest,
    select_first_passing,
    validate_formal_manifest,
)
from embodied_memory_thor.phase5.qualification import (
    assess_relocation_probe,
    place_object_at_point_action,
    spawn_coordinate_query,
)


def _records(task: str) -> list[QualificationRecord]:
    records: list[QualificationRecord] = []
    for order in range(1, 9):
        passed = order not in {2, 5}
        records.append(
            QualificationRecord(
                task=task,
                candidate_order=order,
                configuration_id=f"{task}-config-{order}",
                scene=f"FloorPlan{order}",
                passed=passed,
                start_pose={
                    "position": {"x": float(order), "y": 0.9, "z": 1.0},
                    "rotation": {"x": 0.0, "y": 90.0, "z": 0.0},
                    "horizon": 0.0,
                },
                rejection_reasons=() if passed else ("target_not_visible",),
                qualification_evidence={"solvable": passed},
            )
        )
    return records


class Phase5ProtocolTests(unittest.TestCase):
    def test_first_six_rule_retains_order_and_skips_failures(self) -> None:
        selected = select_first_passing(_records("r1"), task="r1")
        self.assertEqual(
            [record.candidate_order for record in selected], [1, 3, 4, 6, 7, 8]
        )

    def test_first_six_rule_rejects_reordered_or_duplicate_candidates(self) -> None:
        records = _records("r1")
        with self.assertRaisesRegex(ValueError, "ascending"):
            select_first_passing(list(reversed(records)), task="r1")
        duplicate = list(records)
        duplicate[2] = QualificationRecord(
            **{**duplicate[2].__dict__, "configuration_id": duplicate[0].configuration_id}
        )
        with self.assertRaisesRegex(ValueError, "not distinct"):
            select_first_passing(duplicate, task="r1")

    def test_formal_manifest_is_exact_matched_54_cell_matrix(self) -> None:
        manifest = self._manifest()
        self.assertEqual(len(manifest["episodes"]), FORMAL_EPISODE_COUNT)
        self.assertEqual(manifest["required_metrics"], list(PHASE5_REQUIRED_METRICS))
        self.assertEqual(
            manifest["qualification"]["r1_selected_ids"],
            [
                "r1-config-1",
                "r1-config-3",
                "r1-config-4",
                "r1-config-6",
                "r1-config-7",
                "r1-config-8",
            ],
        )
        stable = {
            row["configuration_id"]
            for row in manifest["episodes"]
            if row["panel"] == "r1_stable"
        }
        stale = {
            row["configuration_id"]
            for row in manifest["episodes"]
            if row["panel"] == "r1_stale"
        }
        self.assertEqual(stable, stale)

    def test_formal_manifest_refuses_dirty_tree_and_visual_output_mutation(self) -> None:
        with self.assertRaisesRegex(ValueError, "clean working tree"):
            build_formal_manifest(
                r1_records=_records("r1"),
                r2_records=_records("r2"),
                code_revision="a" * 40,
                working_tree_dirty=True,
                controller_settings={"width": 300},
            )
        tampered = deepcopy(self._manifest())
        tampered["episodes"][0]["save_frames"] = True
        with self.assertRaisesRegex(ValueError, "formal_output_policy"):
            validate_formal_manifest(tampered)
        unmatched = deepcopy(self._manifest())
        unmatched["episodes"][0]["memory"] = "object_memory"
        with self.assertRaisesRegex(ValueError, "unmatched_variants"):
            validate_formal_manifest(unmatched)

    def test_relocation_actions_match_documented_evaluator_api_shape(self) -> None:
        self.assertEqual(
            spawn_coordinate_query("CounterTop|1"),
            {
                "action": "GetSpawnCoordinatesAboveReceptacle",
                "objectId": "CounterTop|1",
                "anywhere": False,
            },
        )
        self.assertEqual(
            place_object_at_point_action(
                "Book|1", {"x": 1, "y": 0.9, "z": -2}
            ),
            {
                "action": "PlaceObjectAtPoint",
                "objectId": "Book|1",
                "position": {"x": 1.0, "y": 0.9, "z": -2.0},
            },
        )
        with self.assertRaisesRegex(ValueError, "position.x"):
            place_object_at_point_action(
                "Book|1", {"x": float("nan"), "y": 1, "z": 2}
            )

    def test_relocation_probe_requires_move_hidden_old_view_and_stability(self) -> None:
        passed = assess_relocation_probe(
            target_object_id="Book|1",
            before_position={"x": 0.0, "y": 0.8, "z": 0.0},
            spawn_query_success=True,
            spawn_candidates=[{"x": 2.0, "y": 0.8, "z": 2.0}],
            placement_success=True,
            after_target={
                "objectId": "Book|1",
                "position": {"x": 2.0, "y": 0.8, "z": 2.0},
            },
            immediate_visible_object_ids=[],
            old_view_visible_object_ids=[],
            stability_samples=[
                {"x": 2.0, "y": 0.8, "z": 2.0},
                {"x": 2.005, "y": 0.8, "z": 2.005},
            ],
        )
        self.assertTrue(passed["passed"])
        self.assertFalse(passed["planner_visible"])

        failed = assess_relocation_probe(
            target_object_id="Book|1",
            before_position={"x": 0.0, "y": 0.8, "z": 0.0},
            spawn_query_success=True,
            spawn_candidates=[{"x": 0.05, "y": 0.8, "z": 0.05}],
            placement_success=True,
            after_target={
                "objectId": "Book|1",
                "position": {"x": 0.05, "y": 0.8, "z": 0.05},
            },
            immediate_visible_object_ids=["Book|1"],
            old_view_visible_object_ids=["Book|1"],
            stability_samples=[{"x": 0.05, "y": 0.8, "z": 0.05}],
        )
        self.assertFalse(failed["passed"])
        self.assertEqual(
            set(failed["rejection_reasons"]),
            {
                "target_position_not_materially_changed",
                "target_visible_immediately_after_placement",
                "target_still_visible_from_old_viewpoint",
                "insufficient_stability_samples",
            },
        )

    @staticmethod
    def _manifest() -> dict:
        return build_formal_manifest(
            r1_records=_records("r1"),
            r2_records=_records("r2"),
            code_revision="a" * 40,
            working_tree_dirty=False,
            controller_settings={"width": 300, "height": 300},
        )


if __name__ == "__main__":
    unittest.main()

"""Unit tests for Phase 3 observation-derived memory invariants."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env.mock_env import MockEnv  # noqa: E402
from embodied_memory_thor.memory import (  # noqa: E402
    ActionLog,
    ObjectMemory,
    ShortTermMemory,
    retrieve_relevant_objects,
)


class ShortTermMemoryTests(unittest.TestCase):
    def test_exact_k_eviction_and_defensive_snapshot(self) -> None:
        memory = ShortTermMemory(capacity=2)
        for step in range(3):
            memory.add(
                step=step,
                observation={"objects": [{"objectType": f"Type{step}", "visible": True}]},
                action={"action": "Pass"},
                success=True,
            )

        snapshot = memory.snapshot()
        self.assertEqual([1, 2], [record["step"] for record in snapshot["records"]])
        snapshot["records"].clear()
        self.assertEqual(2, memory.snapshot()["size"])

    def test_latest_object_has_observation_provenance(self) -> None:
        env = MockEnv(partial_observability=True, layout_seed=0)
        memory = ShortTermMemory(capacity=2)
        memory.add(
            step=0,
            observation=env.get_observation(),
            observation_id="reset:0",
            action={"action": "Reset"},
            success=True,
        )

        apple = memory.find_latest_object("Apple")

        self.assertIsNotNone(apple)
        self.assertEqual("reset:0", apple["provenance"]["observation_id"])


class ObjectMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = MockEnv(partial_observability=True, layout_seed=0)
        self.memory = ObjectMemory()

    def test_update_uses_visible_observation_and_preserves_hidden_record(self) -> None:
        updated = self.memory.update(self.env.get_observation(), step=0, observation_id="reset:0")
        self.assertIn("Apple|1", updated)
        initial = self.memory.get("Apple|1")

        self.env.step({"action": "MoveToRegion", "region": "DiningArea"})
        self.memory.update(self.env.get_observation(), step=1, observation_id="step:1")

        hidden = self.memory.get("Apple|1")
        self.assertEqual(initial.last_seen_region, hidden.last_seen_region)
        self.assertEqual(0, hidden.last_seen_step)
        self.assertEqual("reset:0", hidden.source_observation_id)

    def test_hidden_evaluator_objects_are_not_ingested(self) -> None:
        self.memory.update(self.env.get_evaluator_state(), step=0)

        self.assertIsNotNone(self.memory.get("Apple|1"))
        self.assertIsNone(self.memory.get("Knife|1"))

    def test_revisit_refreshes_provenance(self) -> None:
        apple_region = self.env.get_agent_state()["region"]
        self.memory.update(self.env.get_observation(), step=0)
        other = next(region for region in self.env.REGIONS if region != apple_region)
        self.env.step({"action": "MoveToRegion", "region": other})
        self.env.step({"action": "MoveToRegion", "region": apple_region})

        self.memory.update(self.env.get_observation(), step=2, observation_id="return:2")

        refreshed = self.memory.get("Apple|1")
        self.assertEqual(2, refreshed.last_seen_step)
        self.assertEqual("return:2", refreshed.source_observation_id)

    def test_expected_region_miss_marks_stale_and_rediscovery_clears_it(self) -> None:
        apple_region = self.env.get_agent_state()["region"]
        self.memory.update(self.env.get_observation(), step=0)
        intervention = self.env.relocate_object_for_experiment("Apple|1", "DiningArea")
        self.assertEqual(apple_region, intervention["before"]["region"])
        self.assertEqual("DiningArea", intervention["after"]["region"])
        self.assertEqual("Reset", self.env.get_observation()["lastAction"])

        self.assertTrue(
            self.memory.mark_expected_region_miss(
                "Apple|1", self.env.get_observation(), step=1
            )
        )
        self.assertEqual("suspected_stale", self.memory.get("Apple|1").status)

        self.env.step({"action": "MoveToRegion", "region": "DiningArea"})
        self.memory.update(self.env.get_observation(), step=2)
        recovered = self.memory.get("Apple|1")
        self.assertEqual("fresh", recovered.status)
        self.assertEqual("DiningArea", recovered.last_seen_region)
        self.assertEqual(2, recovered.last_seen_step)
        self.assertIsNone(recovered.suspected_stale_region)
        self.assertIsNone(recovered.suspected_stale_step)

    def test_retrieval_and_snapshot_are_json_safe(self) -> None:
        self.memory.update(self.env.get_observation(), step=0)

        results = retrieve_relevant_objects(
            "Return to the apple.", self.memory, required_object_types=("Knife",)
        )

        self.assertEqual(["Apple"], [record.object_type for record in results])
        json.dumps(self.memory.snapshot())


class ActionLogTests(unittest.TestCase):
    def test_failures_and_repetitions_are_queryable(self) -> None:
        log = ActionLog()
        action = {"action": "PickupObject", "objectId": "Apple|1"}
        log.add(step=1, action=action, success=False, error="not visible")
        log.add(step=2, action=action, success=True, latency_seconds=0.01)

        self.assertEqual(2, log.repetition_count(action))
        self.assertEqual([1], [record["step"] for record in log.recent_failures()])
        json.dumps(log.snapshot())


if __name__ == "__main__":
    unittest.main()

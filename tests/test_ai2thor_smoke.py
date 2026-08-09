"""Unit tests for live-smoke helpers that do not start Unity."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "smoke_ai2thor.py"
SPEC = importlib.util.spec_from_file_location("smoke_ai2thor", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
smoke_ai2thor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke_ai2thor)


class SmokeHelperTests(unittest.TestCase):
    def test_visible_ids_exclude_hidden_objects(self) -> None:
        metadata = {
            "objects": [
                {"objectId": "Apple|1", "visible": True},
                {"objectId": "Knife|1", "visible": False},
            ]
        }

        self.assertEqual(["Apple|1"], smoke_ai2thor._visible_ids(metadata))

    def test_interaction_candidates_use_current_visible_state(self) -> None:
        metadata = {
            "objects": [
                {
                    "objectId": "Apple|1",
                    "visible": True,
                    "pickupable": True,
                    "isPickedUp": False,
                },
                {
                    "objectId": "Cabinet|1",
                    "visible": True,
                    "openable": True,
                    "isOpen": False,
                },
                {
                    "objectId": "Lamp|1",
                    "visible": False,
                    "toggleable": True,
                    "isToggled": False,
                },
            ]
        }

        self.assertEqual(
            [
                {"action": "PickupObject", "objectId": "Apple|1"},
                {"action": "OpenObject", "objectId": "Cabinet|1"},
            ],
            smoke_ai2thor._interaction_candidates(metadata),
        )

    def test_argument_validation_rejects_non_positive_dimensions(self) -> None:
        args = smoke_ai2thor.build_parser().parse_args(["--width", "0"])

        with self.assertRaisesRegex(ValueError, "positive"):
            smoke_ai2thor._validate_args(args)


if __name__ == "__main__":
    unittest.main()

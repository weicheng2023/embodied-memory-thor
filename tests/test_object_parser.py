"""Tests for safe AI2-THOR object normalization."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env.object_parser import parse_object, parse_objects  # noqa: E402


class ObjectParserTests(unittest.TestCase):
    def test_missing_fields_receive_safe_defaults(self) -> None:
        parsed = parse_object({"objectType": "Apple", "objectId": "Apple|1"})

        self.assertEqual("Apple", parsed["objectType"])
        self.assertFalse(parsed["visible"])
        self.assertEqual([], parsed["parentReceptacles"])
        self.assertIsNone(parsed["position"])

    def test_none_and_scalar_receptacle_fields_are_normalized(self) -> None:
        parsed = parse_object(
            {"parentReceptacles": None, "receptacleObjectIds": "Apple|1"}
        )

        self.assertEqual([], parsed["parentReceptacles"])
        self.assertEqual(["Apple|1"], parsed["receptacleObjectIds"])

    def test_visible_filter_accepts_event_like_object(self) -> None:
        event = type(
            "Event",
            (),
            {
                "metadata": {
                    "objects": [
                        {"objectId": "Apple|1", "visible": True},
                        {"objectId": "Knife|1", "visible": False},
                    ]
                }
            },
        )()

        parsed = parse_objects(event, visible_only=True)

        self.assertEqual(["Apple|1"], [obj["objectId"] for obj in parsed])

    def test_non_list_objects_field_is_safe(self) -> None:
        self.assertEqual([], parse_objects({"objects": "invalid"}))


if __name__ == "__main__":
    unittest.main()

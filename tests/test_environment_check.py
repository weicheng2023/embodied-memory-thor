"""Tests for the Phase 0 environment diagnostics."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.utils.environment import (  # noqa: E402
    collect_environment_report,
    format_human_report,
)


class EnvironmentCheckTests(unittest.TestCase):
    """Verify that missing optional capabilities are reported safely."""

    @patch("embodied_memory_thor.utils.environment.importlib.util.find_spec")
    def test_missing_ai2thor_is_a_warning_not_an_exception(self, find_spec) -> None:
        find_spec.return_value = None

        report = collect_environment_report(environ={})
        checks = {check.name: check for check in report.checks}

        self.assertEqual("WARN", checks["AI2-THOR package"].status)
        self.assertEqual("WARN", checks["AI2-THOR Controller"].status)
        self.assertIn("mock environment", report.recommendation)

    def test_secret_value_is_never_in_report(self) -> None:
        secret = "do-not-print-this-secret"

        report = collect_environment_report(environ={"OPENAI_API_KEY": secret})
        serialized = json.dumps(report.to_dict())
        human = format_human_report(report)

        self.assertNotIn(secret, serialized)
        self.assertNotIn(secret, human)
        self.assertIn("value hidden", human)

    def test_report_is_json_serializable(self) -> None:
        report = collect_environment_report(environ={})

        encoded = json.dumps(report.to_dict())

        self.assertIn("strict_ready", encoded)
        self.assertIn("recommendation", encoded)

    def test_default_base_url_is_not_a_failure(self) -> None:
        report = collect_environment_report(environ={})
        checks = {check.name: check for check in report.checks}

        self.assertEqual("PASS", checks["OpenAI-compatible base URL"].status)

    def test_human_report_has_actionable_sections(self) -> None:
        text = format_human_report(collect_environment_report(environ={}))

        self.assertIn("Environment Check", text)
        self.assertIn("Recommendation:", text)
        self.assertNotIn("OPENAI_API_KEY=", text)


if __name__ == "__main__":
    unittest.main()

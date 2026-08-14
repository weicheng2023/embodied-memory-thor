from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

from embodied_memory_thor.phase5.search import (
    SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT,
    SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r2_production_integration_probe_v4.json"
POLICY = ROOT / "configs" / "phase5_shared_search_entry_recovery_v1.json"
STOP_EVIDENCE = (
    ROOT / "docs" / "evidence" / "phase5_r2_production_probe_v3_stop.json"
)
PASS_EVIDENCE = (
    ROOT / "docs" / "evidence" / "phase5_r2_production_probe_v4.json"
)


def _module() -> object:
    path = ROOT / "scripts" / "run_phase5_r2_production_probe_v4.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_probe_v4_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_v4_is_fresh_excluded_and_policy_bound() -> None:
    module = _module()
    predecessor = module._predecessor()  # type: ignore[attr-defined]
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="historical artifact changed"):
        module.validate_probe_config(config, predecessor)  # type: ignore[attr-defined]
    assert config["variants"] == [
        "no_memory",
        "short_memory_k2",
        "object_memory",
    ]
    assert config["episode_reuse_from_v2"] is False
    assert config["episode_reuse_from_v3"] is False
    assert config["included_in_formal_aggregate"] is False
    assert (
        config["shared_search_entry_recovery_policy"]
        == SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION
    )
    assert (
        config["shared_search_entry_recovery_action_limit"]
        == SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT
        == 64
    )


def test_entry_recovery_policy_is_shared_bounded_and_target_free() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["applies_to_variants"] == [
        "no_memory",
        "short_memory_k2",
        "object_memory",
    ]
    assert policy["recorded_input"] == "successful planner action names only"
    assert policy["fixed_action_limit"] == 64
    assert policy["formal_aggregate_authorized"] is False
    serialized = json.dumps(policy, sort_keys=True)
    for forbidden in (
        '"x"',
        '"y"',
        '"z"',
        "Cup|",
        "CoffeeMachine|",
        "TeleportFull",
    ):
        assert forbidden not in serialized


def test_probe_v4_freezes_runtime_predecessor_and_remediation_sources() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    changed = []
    for relative, expected in config["historical_artifacts_frozen"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            changed.append(relative)
    assert changed == [
        "src/embodied_memory_thor/phase5/search.py",
        "src/embodied_memory_thor/phase4/contracts.py",
        "src/embodied_memory_thor/phase4/planners.py",
        "src/embodied_memory_thor/phase4/runner.py",
    ]
    evidence = json.loads(STOP_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["classification"] == (
        "excluded_integration_probe_failed_shared_search_entry_contract"
    )
    assert evidence["included_in_formal_aggregate"] is False
    assert evidence["old_probe_output_reuse_allowed"] is False
    assert evidence["rows"][0]["success"] is True
    assert evidence["rows"][1]["success"] is True
    assert evidence["rows"][2]["success"] is False
    assert evidence["rows"][2]["information_boundary_passed"] is True


def test_v4_audit_requires_baseline_parity_and_exercised_object_recovery() -> None:
    module = _module()
    rows = [
        {"variant": variant, "audit_errors": []}
        for variant in ("no_memory", "short_memory_k2", "object_memory")
    ]
    with tempfile.TemporaryDirectory() as temporary_dir:
        root = Path(temporary_dir)
        for variant in ("no_memory", "short_memory_k2", "object_memory"):
            episode = root / variant
            episode.mkdir(parents=True)
            recovery = 1 if variant == "object_memory" else 0
            (episode / "summary.json").write_text(
                json.dumps(
                    {
                        "shared_search_entry_recovery_policy": (
                            SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION
                        ),
                        "shared_search_entry_recovery_action_limit": 64,
                        "shared_search_entry_departure_action_count": recovery,
                        "shared_search_entry_recovery_action_count": recovery,
                        "shared_search_entry_recovery_pending_action_count": 0,
                        "shared_search_entry_recovery_record_failure_count": 0,
                        "shared_search_route_entry_mismatch_count": 0,
                        "shared_search_coverage_action_count": 2,
                    }
                ),
                encoding="utf-8",
            )
        result = module._enrich_and_audit(  # type: ignore[attr-defined]
            result={"rows": rows}, output_dir=root
        )
        assert result["passed"] is True
        object_row = result["rows"][2]
        assert object_row["shared_search_entry_recovery_action_count"] == 1

        object_summary = json.loads(
            (root / "object_memory" / "summary.json").read_text(encoding="utf-8")
        )
        object_summary["shared_search_entry_recovery_action_count"] = 0
        (root / "object_memory" / "summary.json").write_text(
            json.dumps(object_summary), encoding="utf-8"
        )
        fresh_rows = [
            {"variant": variant, "audit_errors": []}
            for variant in ("no_memory", "short_memory_k2", "object_memory")
        ]
        failed = module._enrich_and_audit(  # type: ignore[attr-defined]
            result={"rows": fresh_rows}, output_dir=root
        )
        assert failed["passed"] is False
        assert "object_memory_entry_recovery_not_exercised" in failed["rows"][2][
            "audit_errors"
        ]


def test_public_probe_material_contains_no_private_route_state() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (CONFIG, POLICY, STOP_EVIDENCE, PASS_EVIDENCE)
    )
    for forbidden in (
        '"x":',
        '"y":',
        '"z":',
        "Cup|",
        "CoffeeMachine|",
        "TeleportFull",
        "reachable_positions",
    ):
        assert forbidden not in text


def test_v4_public_result_is_complete_excluded_and_reports_regression() -> None:
    evidence = json.loads(PASS_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["classification"] == (
        "excluded_integration_probe_passed_with_entry_recovery"
    )
    assert evidence["included_in_formal_aggregate"] is False
    assert evidence["episode_reuse_from_v3"] is False
    assert evidence["completed_variant_count"] == 3
    assert evidence["shared_search_route_entry_mismatch_count_all_variants"] == 0
    assert evidence[
        "shared_search_entry_recovery_record_failure_count_all_variants"
    ] == 0
    rows = {row["variant"]: row for row in evidence["rows"]}
    assert rows["no_memory"]["steps"] == rows["short_memory_k2"]["steps"] == 60
    assert rows["no_memory"]["shared_search_entry_recovery_action_count"] == 0
    assert rows["short_memory_k2"]["shared_search_entry_recovery_action_count"] == 0
    assert rows["object_memory"]["shared_search_entry_recovery_action_count"] == 14
    assert rows["object_memory"]["shared_search_coverage_action_count"] == 45
    assert rows["object_memory"]["steps"] == 88
    assert rows["object_memory"]["steps"] > rows["no_memory"]["steps"]
    assert evidence["not_a_memory_improvement_result"] is True

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from embodied_memory_thor.phase5.formal_analysis_v1 import (
    FormalAnalysisError,
    MECHANISM_COUNT_FIELDS,
    build_descriptive_analysis,
    render_markdown,
    stable_digest,
    validate_analysis_config,
    validate_completion_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_real_formal_analysis_v1.json"
EVIDENCE = ROOT / "docs" / "evidence" / "phase5_real_formal_v5_complete.json"


def _config() -> dict[str, object]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _summary() -> dict[str, object]:
    config = _config()
    rows: list[dict[str, object]] = []
    episode_index = 1
    for panel in config["panel_order"]:  # type: ignore[index]
        for offset, configuration_id in enumerate(
            config["configuration_order"][panel]  # type: ignore[index]
        ):
            for variant in config["variant_order"]:  # type: ignore[index]
                variant_offset = {
                    "no_memory": 3,
                    "short_memory_k2": 2,
                    "object_memory": 1,
                }[variant]
                row: dict[str, object] = {
                    "episode_index": episode_index,
                    "panel": panel,
                    "configuration_id": configuration_id,
                    "memory": variant,
                    "success": True,
                    "information_boundary_passed": True,
                    "integrity_errors": [],
                    "short_memory_evicted_before_reacquisition": (
                        variant == "short_memory_k2"
                    ),
                }
                for metric in config["performance_metrics"]:  # type: ignore[index]
                    row[metric] = offset + variant_offset
                for field in MECHANISM_COUNT_FIELDS:
                    row[field] = 1 if field == "memory_guided_action_count" and variant == "object_memory" else 0
                rows.append(row)
                episode_index += 1
    return {
        "code_revision": config["source_code_revision"],
        "executor_version": config["source_executor_version"],
        "expected_episode_count": 54,
        "completed_episode_count": 54,
        "matrix_complete": True,
        "integrity_valid": True,
        "included_in_formal_aggregate": True,
        "task_success_count": 54,
        "task_failure_count": 0,
        "manifest_digest": config["expected_manifest_digest"],
        "result_digest": config["expected_result_digest"],
        "rows": rows,
    }


def test_config_and_completion_evidence_bind_frozen_source() -> None:
    config = _config()
    validate_analysis_config(config)
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    validate_completion_evidence(evidence, config)
    assert evidence["artifact_sha256"]["formal_summary.json"] == config[
        "source_summary_sha256"
    ]


def test_analysis_is_deterministic_panel_separated_and_paired() -> None:
    config = _config()
    first = build_descriptive_analysis(_summary(), config)
    second = build_descriptive_analysis(_summary(), config)
    assert first == second
    assert stable_digest({k: v for k, v in first.items() if k != "analysis_digest"}) == first[
        "analysis_digest"
    ]
    assert [panel["panel"] for panel in first["panels"]] == config["panel_order"]
    assert first["panel_pooling_used"] is False
    assert first["significance_test_used"] is False
    for panel in first["panels"]:
        comparison = panel["paired_comparisons"][0]
        steps = comparison["metrics"]["steps"]
        assert comparison["comparison"] == "object_memory_vs_no_memory"
        assert steps["difference_summary"]["mean"] == -2
        assert steps["improvement_count"] == 6
        assert steps["tie_count"] == 0
        assert steps["regression_count"] == 0


def test_analysis_rejects_missing_or_integrity_invalid_cell() -> None:
    config = _config()
    missing = _summary()
    missing["rows"].pop()  # type: ignore[union-attr]
    with pytest.raises(FormalAnalysisError, match="rows"):
        build_descriptive_analysis(missing, config)

    invalid = _summary()
    invalid["rows"][0]["integrity_errors"] = ["leak"]  # type: ignore[index]
    with pytest.raises(FormalAnalysisError, match="integrity error"):
        build_descriptive_analysis(invalid, config)


def test_analysis_rejects_reordered_matrix_and_changed_methods() -> None:
    config = _config()
    reordered = _summary()
    reordered["rows"][0], reordered["rows"][1] = (  # type: ignore[index]
        reordered["rows"][1],
        reordered["rows"][0],
    )
    with pytest.raises(FormalAnalysisError, match="row order"):
        build_descriptive_analysis(reordered, config)

    pooled = deepcopy(config)
    pooled["panel_pooling_allowed"] = True
    with pytest.raises(FormalAnalysisError, match="pooling"):
        validate_analysis_config(pooled)

    inferential = deepcopy(config)
    inferential["significance_testing_allowed"] = True
    with pytest.raises(FormalAnalysisError, match="significance"):
        validate_analysis_config(inferential)


def test_report_states_direction_and_interpretation_boundary() -> None:
    report = render_markdown(build_descriptive_analysis(_summary(), _config()))
    assert "54/54 integrity-valid" in report
    assert "first variant minus second variant" in report
    assert "lower is better" in report
    assert "No significance test" in report


def test_public_analysis_material_contains_no_private_runtime_fields() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            CONFIG,
            ROOT / "src" / "embodied_memory_thor" / "phase5" / "formal_analysis_v1.py",
            ROOT / "scripts" / "aggregate_phase5_real_formal_v5.py",
        )
    )
    for forbidden in (
        '"start_pose"',
        '"target_point"',
        '"anchor_id"',
        '"objectId"',
        "Book|",
        "Cup|",
        "CoffeeMachine|",
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in text

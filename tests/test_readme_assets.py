from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_readme_assets.py"


def _module():
    spec = importlib.util.spec_from_file_location("render_readme_assets", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_system_overview_preserves_information_boundary(tmp_path: Path) -> None:
    module = _module()
    output = module.render_system_overview(tmp_path / "system.svg")
    text = output.read_text(encoding="utf-8")
    assert "PLANNER-VISIBLE EXECUTION PATH" in text
    assert "EVALUATOR-ONLY PATH · NEVER PLANNER INPUT" in text
    assert "Full Simulator State" in text
    assert "Shared Planner" in text
    assert "marker-end:url(#arrow-amber)" in text


def test_memory_horizon_chart_reads_frozen_counts(tmp_path: Path) -> None:
    module = _module()
    evidence = {
        "analysis_digest": "a" * 64,
        "target_retention_counts": {
            "no_memory": {"present": 0, "absent": 6},
            "recent_memory_k2": {"present": 0, "absent": 6},
            "recent_memory_k4": {"present": 2, "absent": 4},
            "recent_memory_k8": {"present": 6, "absent": 0},
            "object_memory": {"present": 6, "absent": 0},
        },
    }
    source = tmp_path / "evidence.json"
    source.write_text(json.dumps(evidence), encoding="utf-8")
    output = module.render_memory_horizon_chart(source, tmp_path / "chart.svg")
    text = output.read_text(encoding="utf-8")
    assert text.count(">0/6<") == 2
    assert text.count(">2/6<") == 1
    assert text.count(">6/6<") == 2
    assert "does not establish general equivalence" in text


def test_committed_readme_diagrams_are_deterministic(tmp_path: Path) -> None:
    module = _module()
    generated_system = module.render_system_overview(tmp_path / "system.svg")
    generated_chart = module.render_memory_horizon_chart(
        module.DEFAULT_EVIDENCE,
        tmp_path / "chart.svg",
    )
    asset_dir = ROOT / "docs" / "assets" / "readme"
    assert generated_system.read_bytes() == (asset_dir / "system_overview.svg").read_bytes()
    assert generated_chart.read_bytes() == (
        asset_dir / "memory_horizon_retention.svg"
    ).read_bytes()


def test_readme_replay_manifest_matches_public_assets() -> None:
    asset_dir = ROOT / "docs" / "assets" / "readme"
    manifest = json.loads((asset_dir / "demo_manifest.json").read_text(encoding="utf-8"))
    gif = asset_dir / "book_reacquisition.gif"
    poster = asset_dir / "book_reacquisition_poster.png"
    assert manifest["artifact_role"] == "presentation_only_not_formal_comparative_evidence"
    assert manifest["desktop_screenshot_used"] is False
    assert manifest["evaluator_only_state_in_overlay"] is False
    assert manifest["source_boundary"] == "planner_visible_trace_and_in_memory_rgb_frames_only"
    assert manifest["gif_sha256"] == hashlib.sha256(gif.read_bytes()).hexdigest()
    assert manifest["poster_sha256"] == hashlib.sha256(poster.read_bytes()).hexdigest()
    assert gif.stat().st_size < 8 * 1024 * 1024
    assert not ({"object_id", "objectId", "coordinates", "reachable_graph"} & manifest.keys())


def test_readme_links_visuals_with_bounded_role() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/assets/readme/book_reacquisition.gif" in readme
    assert "docs/assets/readme/system_overview.svg" in readme
    assert "docs/assets/readme/memory_horizon_retention.svg" in readme
    assert "not a formal comparison row" in readme

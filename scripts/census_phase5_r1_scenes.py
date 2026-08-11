#!/usr/bin/env python3
"""Run the coordinate-free Phase 5 R1 Book scene-presence census."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POOL = PROJECT_ROOT / "configs" / "phase5_r1_scene_pool.json"
CONTROLLER_SETTINGS = {
    "width": 300,
    "height": 300,
    "quality": "Low",
    "gridSize": 0.25,
    "snapToGrid": True,
    "rotateStepDegrees": 90,
    "fieldOfView": 90,
    "renderDepthImage": False,
    "renderInstanceSegmentation": False,
}


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _git_state() -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"code_revision": revision, "working_tree_dirty": dirty}


def _load_pool(path: Path) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("scene-pool document must be a mapping")
    ordered: list[tuple[str, str]] = []
    for family in raw.get("scene_families", []):
        if not isinstance(family, Mapping):
            raise ValueError("scene family must be a mapping")
        name = str(family.get("name", ""))
        for scene in family.get("scenes", []):
            ordered.append((name, str(scene)))
    scenes = [scene for _, scene in ordered]
    if not scenes or len(scenes) != len(set(scenes)):
        raise ValueError("candidate scenes must be nonempty and unique")
    return raw, ordered


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    pool, ordered = _load_pool(args.pool.resolve())
    gate = pool["presence_gate"]
    support_types = set(gate["open_support_types"])

    from ai2thor.controller import Controller

    controller = Controller(scene=ordered[0][1], **CONTROLLER_SETTINGS)
    rows: list[dict[str, Any]] = []
    try:
        for candidate_order, (family, scene) in enumerate(ordered, start=1):
            try:
                event = controller.reset(scene=scene)
                objects = event.metadata.get("objects", [])
                reachable_event = controller.step(action="GetReachablePositions")
                reachable_count = (
                    len(reachable_event.metadata.get("actionReturn") or [])
                    if reachable_event.metadata.get("lastActionSuccess") is True
                    else 0
                )
                book_count = sum(
                    item.get("objectType") == "Book"
                    and item.get("pickupable") is True
                    for item in objects
                )
                visible_book_count = sum(
                    item.get("objectType") == "Book"
                    and item.get("pickupable") is True
                    and item.get("visible") is True
                    for item in objects
                )
                support_counts = {
                    object_type: sum(
                        item.get("objectType") == object_type
                        and item.get("receptacle") is True
                        for item in objects
                    )
                    for object_type in sorted(support_types)
                }
                support_count = sum(support_counts.values())
                passed = (
                    book_count >= int(gate["pickupable_book_minimum"])
                    and support_count >= int(gate["declared_open_support_minimum"])
                    and reachable_count >= int(gate["reachable_position_minimum"])
                )
                row = {
                    "candidate_order": candidate_order,
                    "family": family,
                    "scene": scene,
                    "pickupable_book_count": book_count,
                    "default_view_visible_pickupable_book_count": visible_book_count,
                    "declared_open_support_count": support_count,
                    "declared_open_support_counts_by_type": support_counts,
                    "reachable_position_count": reachable_count,
                    "presence_gate_passed": passed,
                    "error": "",
                }
            except Exception as exc:
                row = {
                    "candidate_order": candidate_order,
                    "family": family,
                    "scene": scene,
                    "presence_gate_passed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            rows.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
    finally:
        controller.stop()

    passed = [row["scene"] for row in rows if row["presence_gate_passed"]]
    result = {
        "census_version": "phase5-r1-book-scene-census-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": pool["claim_boundary"],
        "pool_version": pool["pool_version"],
        "selection_rule": pool["selection_rule"],
        "pool_path": str(args.pool.resolve()),
        "controller_settings": CONTROLLER_SETTINGS,
        "runtime": {
            "ai2thor_version": _package_version("ai2thor"),
            **_git_state(),
        },
        "images_saved": False,
        "memory_agents_run": False,
        "candidate_count": len(rows),
        "error_count": sum(bool(row["error"]) for row in rows),
        "presence_passed_count": len(passed),
        "presence_passed_scenes_in_declared_order": passed,
        "first_six_presence_candidates": passed[:6],
        "six_scene_presence_pool_feasible": len(passed) >= 6,
        "rows": rows,
    }
    _write_json(args.output.resolve(), result)
    print(
        "SUMMARY "
        + json.dumps(
            {
                "candidate_count": len(rows),
                "error_count": result["error_count"],
                "presence_passed_count": len(passed),
                "first_six_presence_candidates": passed[:6],
                "six_scene_presence_pool_feasible": len(passed) >= 6,
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if len(passed) >= 6 and result["error_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

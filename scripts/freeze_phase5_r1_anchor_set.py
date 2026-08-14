#!/usr/bin/env python3
"""Merge verified private anchor sources into one evaluator-only registry."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


BOUNDARY = "EVALUATOR-ONLY FROZEN ANCHOR SET - NEVER PLANNER INPUT"


def build_frozen_anchor_set(
    manifest: Mapping[str, Any], *, root: Path
) -> dict[str, Any]:
    expected_count = int(manifest["target_anchor_count"])
    rows = manifest.get("scenes", [])
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ValueError("manifest scene count does not match target anchor count")
    anchors: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    seen_scenes: set[str] = set()
    seen_anchor_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("manifest scene row must be an object")
        scene = str(row["scene"])
        if scene in seen_scenes:
            raise ValueError("manifest scenes must be distinct")
        registry_path = (root / str(row["private_registry"])).resolve()
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if registry.get("scene") != scene:
            raise ValueError(f"private registry scene mismatch for {scene}")
        if registry.get("private_registry_digest") != row.get("private_registry_digest"):
            raise ValueError(f"private registry digest mismatch for {scene}")
        private_anchors = registry.get("anchors", [])
        if not isinstance(private_anchors, list) or len(private_anchors) != 1:
            raise ValueError(f"private registry must contain one anchor for {scene}")
        anchor = deepcopy(private_anchors[0])
        anchor_id = str(anchor.get("anchor_id", ""))
        if anchor_id != row.get("anchor_id") or anchor_id in seen_anchor_ids:
            raise ValueError(f"anchor identity mismatch for {scene}")
        public_path = (root / str(row["public_evidence"])).resolve()
        public = json.loads(public_path.read_text(encoding="utf-8"))
        public_pass = public.get("passed", public.get("qualification", {}).get("passed"))
        if public.get("scene") != scene or public_pass is not True:
            raise ValueError(f"public qualification evidence mismatch for {scene}")
        seen_scenes.add(scene)
        seen_anchor_ids.add(anchor_id)
        anchors.append(anchor)
        sources.append({
            "scene": scene,
            "anchor_id": anchor_id,
            "private_registry_digest": row["private_registry_digest"],
            "public_evidence": row["public_evidence"],
            "baseline_execution_gate_status": row["baseline_execution_gate_status"],
        })
    combined = {
        "anchor_set_version": manifest["anchor_set_version"],
        "boundary": BOUNDARY,
        "planner_visible": False,
        "included_in_planner_metrics": False,
        "anchor_count": len(anchors),
        "scenes": [row["scene"] for row in sources],
        "sources": sources,
        "anchors": anchors,
    }
    combined["private_anchor_set_digest"] = stable_digest(combined)
    return combined


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.resolve().read_text(encoding="utf-8"))
    frozen = build_frozen_anchor_set(manifest, root=PROJECT_ROOT)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(to_jsonable(frozen), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "anchor_set_version": frozen["anchor_set_version"],
        "anchor_count": frozen["anchor_count"],
        "scenes": frozen["scenes"],
        "private_anchor_set_digest": frozen["private_anchor_set_digest"],
        "coordinates_exposed": False,
        "output": str(output),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

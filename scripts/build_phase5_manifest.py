#!/usr/bin/env python3
"""Build the frozen 54-cell Phase 5 manifest from retained qualification JSON."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import ThorEpisodeConfig  # noqa: E402
from embodied_memory_thor.phase5.protocol import (  # noqa: E402
    QualificationRecord,
    build_formal_manifest,
)


def _git_state() -> tuple[str, bool]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return revision, dirty


def _records(raw: Any, task: str) -> list[QualificationRecord]:
    if not isinstance(raw, list):
        raise ValueError(f"qualification.{task} must be a list")
    records: list[QualificationRecord] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"qualification.{task}[{index}] must be a mapping")
        if not isinstance(item.get("passed"), bool):
            raise ValueError(f"qualification.{task}[{index}].passed must be boolean")
        if not isinstance(item.get("start_pose"), Mapping):
            raise ValueError(f"qualification.{task}[{index}].start_pose must be a mapping")
        records.append(QualificationRecord(
            task=task,
            candidate_order=int(item["candidate_order"]),
            configuration_id=str(item["configuration_id"]),
            scene=str(item["scene"]),
            passed=item["passed"],
            start_pose=dict(item["start_pose"]),
            rejection_reasons=tuple(str(x) for x in item.get("rejection_reasons", [])),
            qualification_evidence=dict(item.get("qualification_evidence", {})),
        ))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze the formal Phase 5 matrix; refuses a dirty Git tree."
    )
    parser.add_argument("--qualification", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        source = Path(args.qualification).expanduser().resolve()
        document = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            raise ValueError("qualification document must be a mapping")
        revision, dirty = _git_state()
        manifest = build_formal_manifest(
            r1_records=_records(document.get("r1"), "r1"),
            r2_records=_records(document.get("r2"), "r2"),
            code_revision=revision,
            working_tree_dirty=dirty,
            controller_settings=ThorEpisodeConfig().controller_settings,
        )
        destination = Path(args.output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (KeyError, OSError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        print(f"phase5_manifest_error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote frozen {len(manifest['episodes'])}-episode manifest: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

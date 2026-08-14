#!/usr/bin/env python3
"""Validate and descriptively aggregate the frozen formal-v5 summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.formal_analysis_v1 import (  # noqa: E402
    FormalAnalysisError,
    build_descriptive_analysis,
    render_markdown,
    sha256_file,
    validate_analysis_config,
    validate_completion_evidence,
)


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_real_formal_analysis_v1.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalAnalysisError(f"expected JSON object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.config.expanduser().resolve()
    summary_path = args.summary.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    config = _load_json(config_path)
    validate_analysis_config(config)

    if sha256_file(summary_path) != config["source_summary_sha256"]:
        raise FormalAnalysisError("formal summary SHA-256 does not match precommit")
    evidence_path = PROJECT_ROOT / str(config["completion_evidence_path"])
    if sha256_file(evidence_path) != config["completion_evidence_sha256"]:
        raise FormalAnalysisError("completion evidence SHA-256 does not match precommit")
    evidence = _load_json(evidence_path)
    validate_completion_evidence(evidence, config)

    if output_dir.exists() and any(output_dir.iterdir()):
        raise FormalAnalysisError("output directory must be new or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis = build_descriptive_analysis(_load_json(summary_path), config)
    (output_dir / "formal_v5_descriptive_results.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "formal_v5_descriptive_report.md").write_text(
        render_markdown(analysis), encoding="utf-8"
    )
    print(json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

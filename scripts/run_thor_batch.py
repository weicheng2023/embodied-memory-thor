#!/usr/bin/env python3
"""Run a manifest-defined Phase 4 acceptance batch through one episode engine."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import (  # noqa: E402
    PHASE4_PROTOCOL_VERSION,
    ThorEpisodeConfig,
    ThorEpisodeRunner,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the small Phase 4 acceptance manifest, not the Phase 5 ablation."
    )
    parser.add_argument(
        "--manifest", default=str(PROJECT_ROOT / "configs" / "phase4_acceptance.yaml")
    )
    parser.add_argument("--mode", choices=("formal", "debug"), default="formal")
    parser.add_argument("--output-root")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="maximum cases to run; defaults to one for cautious first acceptance",
    )
    parser.add_argument("--continue-on-failure", action="store_true")
    return parser


def _load_manifest(path: str | Path) -> Mapping[str, Any]:
    try:
        import yaml
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError("PyYAML is required to load the batch manifest") from exc
    manifest_path = Path(path).expanduser().resolve()
    with manifest_path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, Mapping):
        raise ValueError("batch manifest must be a mapping")
    if document.get("protocol_version") != PHASE4_PROTOCOL_VERSION:
        raise ValueError(
            f"manifest protocol_version must be {PHASE4_PROTOCOL_VERSION!r}"
        )
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("batch manifest requires a non-empty cases list")
    return document


def _case_config(
    case: Mapping[str, Any], *, mode: str, output_dir: Path
) -> ThorEpisodeConfig:
    controller = case.get("controller_settings", {})
    if not isinstance(controller, Mapping):
        raise ValueError("controller_settings must be a mapping")
    return ThorEpisodeConfig(
        task=str(case.get("task", "thor_book_reacquire")),
        scene=str(case.get("scene", "FloorPlan1")),
        planner=str(case.get("planner", "deterministic")),
        memory=str(case.get("memory", "object_memory")),
        search_route_id=(
            str(case["search_route_id"])
            if case.get("search_route_id")
            else None
        ),
        mode=mode,
        max_steps=int(case.get("max_steps", 12)),
        output_dir=output_dir,
        save_frames=bool(case.get("save_frames", False)),
        trace_html=bool(case.get("trace_html", True)),
        visualize=bool(case.get("visualize", False)) if mode == "debug" else False,
        step_delay=float(case.get("step_delay", 0.0)) if mode == "debug" else 0.0,
        save_evaluator_debug=bool(case.get("save_evaluator_debug", False)),
        model=str(case.get("model", "gpt-5.6")),
        base_url=str(case["base_url"]) if case.get("base_url") else None,
        controller_settings=dict(controller) or ThorEpisodeConfig().controller_settings,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit <= 0:
        print("configuration_error: --limit must be positive", file=sys.stderr)
        return 2
    try:
        manifest = _load_manifest(args.manifest)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"manifest_error: {exc}", file=sys.stderr)
        return 2

    root = (
        Path(args.output_root).expanduser().resolve()
        if args.output_root
        else PROJECT_ROOT
        / "outputs"
        / "thor_runs"
        / f"batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    root.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    cases = manifest["cases"][: args.limit]
    for index, raw_case in enumerate(cases):
        if not isinstance(raw_case, Mapping):
            print(f"manifest_error: case {index} is not a mapping", file=sys.stderr)
            return 2
        case_id = str(raw_case.get("case_id", f"case_{index:03d}"))
        try:
            config = _case_config(raw_case, mode=args.mode, output_dir=root / case_id)
            config.validate()
        except (TypeError, ValueError) as exc:
            print(f"manifest_error:{case_id}:{exc}", file=sys.stderr)
            return 2
        result = ThorEpisodeRunner(config).run()
        results.append(result)
        if not result["success"] and not args.continue_on_failure:
            break

    batch_summary = {
        "protocol_version": PHASE4_PROTOCOL_VERSION,
        "purpose": "Phase 4 acceptance only; not Phase 5 research evidence",
        "requested_limit": args.limit,
        "case_count": len(results),
        "success_count": sum(bool(item["success"]) for item in results),
        "all_succeeded": bool(results) and all(item["success"] for item in results),
        "results": results,
    }
    (root / "batch_summary.json").write_text(
        json.dumps(to_jsonable(batch_summary), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(batch_summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if batch_summary["all_succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

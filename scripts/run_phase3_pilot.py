#!/usr/bin/env python3
"""Execute and summarize the frozen 54-episode Phase 3 mock pilot."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.evaluation import (  # noqa: E402
    CONDITIONS,
    LAYOUT_SEEDS,
    SHORT_TERM_CAPACITY,
    VARIANT_PLANNERS,
    add_matched_deltas,
    aggregate_results,
    build_protocol_manifest,
    evaluate_acceptance,
)


ROW_FIELDS = (
    "condition",
    "task",
    "memory_variant",
    "planner",
    "layout_seed",
    "success",
    "steps",
    "search_move_count",
    "repeated_region_visit_count",
    "invalid_action_count",
    "memory_retrieval_count",
    "memory_hint_count",
    "memory_guided_action_count",
    "last_seen_hit_count",
    "stale_memory_miss_count",
    "stale_record_recovery_count",
    "recovery_search_move_count",
    "extra_steps_vs_stable",
    "extra_moves_vs_stable",
    "intervention_count",
    "information_leak_audit_passed",
    "ordered_subgoal_passed",
    "failure_reason",
    "output_dir",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        help="new output directory; defaults to outputs/phase3_pilot/<UTC timestamp>",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow a development-only run from a dirty working tree",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="development check using seed 0 only; never labeled formal pilot",
    )
    return parser


def _git(command: list[str]) -> str:
    completed = subprocess.run(
        ["git", *command], cwd=PROJECT_ROOT, check=True, text=True, capture_output=True
    )
    return completed.stdout.strip()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _row_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {field: summary.get(field) for field in ROW_FIELDS if not field.startswith("extra_")}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    path: Path,
    *,
    rows: list[dict[str, Any]],
    aggregates: list[dict[str, Any]],
    acceptance: dict[str, Any],
    formal: bool,
) -> None:
    lines = [
        "# Phase 3 Pilot Report",
        "",
        f"Evidence status: {'formal frozen pilot' if formal else 'development-only smoke'}",
        "",
        f"Episodes: {len(rows)}",
        "",
        f"Protocol acceptance: {'PASS' if acceptance['passed'] else 'FAIL'}",
        "",
        "## Acceptance checks",
        "",
    ]
    lines.extend(
        f"- {'PASS' if passed else 'FAIL'} — `{name}`"
        for name, passed in acceptance["checks"].items()
    )
    lines.extend(
        [
            "",
            "## Descriptive results",
            "",
            "| Condition | Variant | Success | Mean steps | Mean moves | Mean revisits | Memory-guided | Stale misses | Recoveries |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in aggregates:
        lines.append(
            "| {condition} | {memory_variant} | {success_count}/{episodes} | "
            "{mean_steps:.2f} | {mean_search_move_count:.2f} | "
            "{mean_repeated_region_visit_count:.2f} | {mean_memory_guided_action_count:.2f} | "
            "{mean_stale_memory_miss_count:.2f} | {mean_stale_record_recovery_count:.2f} |".format(
                **item
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "These are descriptive results from six deterministic layouts in a symbolic partial-observation mock. They do not establish statistical significance, broad task generalization, or memory gains in real AI2-THOR.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else (PROJECT_ROOT / "outputs" / "phase3_pilot" / timestamp).resolve()
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        print(f"output directory must be new or empty: {output_dir}", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)

    revision = _git(["rev-parse", "HEAD"])
    dirty = bool(_git(["status", "--porcelain", "--untracked-files=normal"]))
    if dirty and not args.allow_dirty:
        print("working tree is dirty; commit first or use --allow-dirty for development only", file=sys.stderr)
        return 2

    manifest = build_protocol_manifest(
        code_revision=revision, working_tree_dirty=dirty, command=[sys.executable, *sys.argv]
    )
    if args.smoke:
        manifest["evidence_status"] = "development_only_smoke"
        manifest["ordinary_episode_count"] = len(VARIANT_PLANNERS) * len(CONDITIONS)
    manifest["created_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(output_dir / "run_manifest.json", manifest)

    seeds = (LAYOUT_SEEDS[0],) if args.smoke else LAYOUT_SEEDS
    rows: list[dict[str, Any]] = []
    for condition_name, condition in CONDITIONS.items():
        for variant, planner in VARIANT_PLANNERS.items():
            for seed in seeds:
                episode_dir = output_dir / "episodes" / condition_name / variant / f"seed_{seed}"
                episode_dir.mkdir(parents=True, exist_ok=False)
                command = [
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "run_episode.py"),
                    "--mock",
                    "--partial-observability",
                    "--seed",
                    str(seed),
                    "--task",
                    str(condition["task"]),
                    "--planner",
                    planner,
                    "--max-steps",
                    str(condition["max_steps"]),
                    "--short-term-capacity",
                    str(SHORT_TERM_CAPACITY),
                    "--output-dir",
                    str(episode_dir),
                ]
                if condition["stale_intervention"]:
                    command.append("--stale-intervention")
                completed = subprocess.run(
                    command, cwd=PROJECT_ROOT, text=True, capture_output=True
                )
                summary_path = episode_dir / "summary.json"
                if not summary_path.exists():
                    print(completed.stdout, file=sys.stderr)
                    print(completed.stderr, file=sys.stderr)
                    print(f"episode failed without summary: {condition_name}/{variant}/{seed}", file=sys.stderr)
                    return 1
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                rows.append(_row_from_summary(summary))
                print(
                    f"{condition_name}/{variant}/seed={seed}: "
                    f"success={summary['success']} steps={summary['steps']} "
                    f"moves={summary['search_move_count']}"
                )

    rows = add_matched_deltas(rows)
    aggregates = aggregate_results(rows)
    acceptance = evaluate_acceptance(rows) if not args.smoke else {
        "passed": False,
        "checks": {"development_smoke_not_formal_acceptance": False},
    }
    _write_csv(output_dir / "pilot_results.csv", rows)
    _write_json(output_dir / "pilot_results.json", {"rows": rows, "aggregates": aggregates})
    _write_json(output_dir / "protocol_acceptance.json", acceptance)
    _write_json(
        output_dir / "run_completion.json",
        {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "episode_count": len(rows),
            "acceptance_passed": acceptance["passed"],
        },
    )
    _write_report(
        output_dir / "pilot_report.md",
        rows=rows,
        aggregates=aggregates,
        acceptance=acceptance,
        formal=not dirty and not args.smoke,
    )
    print(f"phase3_output: {output_dir}")
    return 0 if (args.smoke or acceptance["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

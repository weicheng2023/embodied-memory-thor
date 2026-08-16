#!/usr/bin/env python3
"""Render deterministic README diagrams and a planner-visible THOR replay."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import textwrap
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = (
    ROOT
    / "docs"
    / "evidence"
    / "phase7"
    / "memory_horizon_descriptive_results_v1.json"
)
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "readme"


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_system_overview(output_path: Path) -> Path:
    """Write the exact planner/evaluator information boundary as an SVG."""

    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="820" viewBox="0 0 1500 820" role="img" aria-labelledby="title desc">
  <title id="title">Embodied-Memory-THOR controlled information flow</title>
  <desc id="desc">Current visible observations and permitted memory reach the shared planner. Evaluator-only full state remains on a separate dashed path and never enters planner input.</desc>
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#0f172a" flood-opacity="0.10"/></filter>
    <marker id="arrow-blue" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#2563eb"/></marker>
    <marker id="arrow-teal" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#0f766e"/></marker>
    <marker id="arrow-amber" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#b45309"/></marker>
    <style>
      .title{font:700 32px system-ui,-apple-system,Segoe UI,sans-serif;fill:#0f172a}.subtitle{font:400 17px system-ui,-apple-system,Segoe UI,sans-serif;fill:#475569}
      .lane{font:700 14px system-ui,-apple-system,Segoe UI,sans-serif;letter-spacing:1.4px}.box-title{font:700 19px system-ui,-apple-system,Segoe UI,sans-serif;fill:#0f172a}.box-copy{font:400 14px system-ui,-apple-system,Segoe UI,sans-serif;fill:#475569}.small{font:600 13px system-ui,-apple-system,Segoe UI,sans-serif;fill:#334155}.legend{font:500 13px system-ui,-apple-system,Segoe UI,sans-serif;fill:#475569}
      .box{rx:16;filter:url(#shadow)}.visible{stroke:#93c5fd;stroke-width:2;fill:#eff6ff}.memory{stroke:#5eead4;stroke-width:2;fill:#f0fdfa}.shared{stroke:#c4b5fd;stroke-width:2;fill:#f5f3ff}.action{stroke:#86efac;stroke-width:2;fill:#f0fdf4}.trace{stroke:#cbd5e1;stroke-width:2;fill:#ffffff}.private{stroke:#f59e0b;stroke-width:2;stroke-dasharray:9 7;fill:#fffbeb}
      .blue-line{stroke:#2563eb;stroke-width:3;fill:none;marker-end:url(#arrow-blue)}.teal-line{stroke:#0f766e;stroke-width:3;fill:none;marker-end:url(#arrow-teal)}.amber-line{stroke:#b45309;stroke-width:3;stroke-dasharray:9 7;fill:none;marker-end:url(#arrow-amber)}.audit-line{stroke:#64748b;stroke-width:2.5;fill:none;marker-end:url(#arrow-blue)}
    </style>
  </defs>
  <rect width="1500" height="820" fill="#f8fafc"/>
  <text class="title" x="70" y="65">Embodied-Memory-THOR · Controlled Information Flow</text>
  <text class="subtitle" x="70" y="96">Memory access changes; task, action space, search, recovery, and evaluator remain matched.</text>

  <rect x="55" y="128" width="1390" height="420" rx="24" fill="#ffffff" stroke="#dbeafe" stroke-width="2"/>
  <text class="lane" x="82" y="153" fill="#1d4ed8">PLANNER-VISIBLE EXECUTION PATH</text>

  <rect class="box visible" x="85" y="205" width="235" height="145"/>
  <text class="box-title" x="110" y="245">AI2-THOR</text>
  <text class="box-copy" x="110" y="276">First-person RGB frame</text>
  <text class="box-copy" x="110" y="300">Current visible metadata</text>
  <text class="box-copy" x="110" y="324">Safe agent state</text>

  <rect class="box visible" x="385" y="205" width="245" height="145"/>
  <text class="box-title" x="410" y="245">Observation Parser</text>
  <text class="box-copy" x="410" y="276">Visible objects only</text>
  <text class="box-copy" x="410" y="300">Inventory and pose</text>
  <text class="box-copy" x="410" y="324">No hidden global state</text>

  <rect class="box memory" x="385" y="390" width="245" height="118"/>
  <text class="box-title" x="410" y="428">Memory Provider</text>
  <text class="box-copy" x="410" y="458">None · recent K · object</text>
  <text class="box-copy" x="410" y="482">Visible-history records</text>

  <rect class="box shared" x="700" y="205" width="265" height="210"/>
  <text class="box-title" x="725" y="245">Shared Planner</text>
  <text class="box-copy" x="725" y="278">Current observation</text>
  <text class="box-copy" x="725" y="302">Permitted action history</text>
  <text class="box-copy" x="725" y="326">Retrieved memory</text>
  <line x1="725" y1="346" x2="940" y2="346" stroke="#ddd6fe" stroke-width="2"/>
  <text class="small" x="725" y="374">Matched search + recovery</text>
  <text class="small" x="725" y="396">Deterministic decision</text>

  <rect class="box action" x="1035" y="205" width="220" height="145"/>
  <text class="box-title" x="1060" y="245">Action Executor</text>
  <text class="box-copy" x="1060" y="278">Validated THOR action</text>
  <text class="box-copy" x="1060" y="302">Success / failure</text>
  <text class="box-copy" x="1060" y="326">Error message</text>

  <rect class="box trace" x="1035" y="390" width="330" height="118"/>
  <text class="box-title" x="1060" y="428">Auditable Episode Trace</text>
  <text class="box-copy" x="1060" y="458">Planner input · action · feedback</text>
  <text class="box-copy" x="1060" y="482">Hashes · provenance · no hidden state</text>

  <path class="blue-line" d="M320 278 H385"/>
  <path class="blue-line" d="M630 278 H700"/>
  <path class="teal-line" d="M508 350 V390"/>
  <path class="teal-line" d="M630 448 H665 Q680 448 680 430 V390 Q680 375 700 375"/>
  <path class="blue-line" d="M965 278 H1035"/>
  <path class="blue-line" d="M1255 278 H1375 Q1400 278 1400 205 Q1400 180 1375 180 H235 Q205 180 205 205"/>
  <path class="audit-line" d="M832 415 V475 Q832 490 850 490 H1035"/>
  <path class="audit-line" d="M1145 350 V390"/>

  <rect x="55" y="575" width="1390" height="170" rx="24" fill="#fffbeb" stroke="#fbbf24" stroke-width="2" stroke-dasharray="10 8"/>
  <text class="lane" x="82" y="609" fill="#92400e">EVALUATOR-ONLY PATH · NEVER PLANNER INPUT</text>
  <rect class="box private" x="165" y="638" width="300" height="78"/>
  <text class="box-title" x="190" y="670">Full Simulator State</text>
  <text class="box-copy" x="190" y="696">Setup and intervention metadata</text>
  <rect class="box private" x="600" y="638" width="300" height="78"/>
  <text class="box-title" x="625" y="670">Success Checker</text>
  <text class="box-copy" x="625" y="696">Task verdict after each action</text>
  <rect class="box private" x="1035" y="638" width="300" height="78"/>
  <text class="box-title" x="1060" y="670">Private Evaluator Audit</text>
  <text class="box-copy" x="1060" y="696">Isolated metadata and provenance</text>
  <path class="amber-line" d="M465 677 H600"/>
  <path class="amber-line" d="M900 677 H1035"/>

  <line x1="85" y1="780" x2="135" y2="780" stroke="#2563eb" stroke-width="3"/><text class="legend" x="145" y="785">planner-visible flow</text>
  <line x1="330" y1="780" x2="380" y2="780" stroke="#0f766e" stroke-width="3"/><text class="legend" x="390" y="785">visible-derived memory</text>
  <line x1="610" y1="780" x2="660" y2="780" stroke="#b45309" stroke-width="3" stroke-dasharray="9 7"/><text class="legend" x="670" y="785">evaluator-only flow</text>
  <text class="legend" x="1040" y="785">Dashed boundary is enforced by tests and trace audits.</text>
</svg>
"""
    return _write_text(output_path, svg)


def render_memory_horizon_chart(evidence_path: Path, output_path: Path) -> Path:
    """Render the frozen Phase-7B target-retention counts as an SVG."""

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    retention = evidence["target_retention_counts"]
    series = (
        ("No memory", "no_memory", "#94a3b8"),
        ("Recent K=2", "recent_memory_k2", "#93c5fd"),
        ("Recent K=4", "recent_memory_k4", "#60a5fa"),
        ("Recent K=8", "recent_memory_k8", "#2563eb"),
        ("Object memory", "object_memory", "#0f766e"),
    )
    values = [(label, int(retention[key]["present"]), color) for label, key, color in series]
    maximum = max(int(retention[key]["present"] + retention[key]["absent"]) for _, key, _ in series)
    if maximum <= 0:
        raise ValueError("memory-horizon evidence has no paired configurations")

    bars: list[str] = []
    for index, (label, value, color) in enumerate(values):
        x = 105 + index * 210
        height = int(250 * value / maximum)
        y = 370 - height
        bars.append(
            f'<rect x="{x}" y="{y}" width="130" height="{height}" rx="12" fill="{color}"/>'
            f'<text class="value" x="{x + 65}" y="{max(105, y - 15)}" text-anchor="middle">{value}/{maximum}</text>'
            f'<text class="label" x="{x + 65}" y="410" text-anchor="middle">{html.escape(label)}</text>'
        )
    digest = html.escape(str(evidence.get("analysis_digest", ""))[:12])
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="520" viewBox="0 0 1200 520" role="img" aria-labelledby="title desc">
  <title id="title">Phase 7B target retention at reacquisition</title>
  <desc id="desc">No memory and K equals 2 retained the target in zero of six configurations, K equals 4 in two, and K equals 8 and object memory in all six.</desc>
  <style>.title{{font:700 28px system-ui,-apple-system,Segoe UI,sans-serif;fill:#0f172a}}.subtitle{{font:400 16px system-ui,-apple-system,Segoe UI,sans-serif;fill:#475569}}.value{{font:700 25px system-ui,-apple-system,Segoe UI,sans-serif;fill:#0f172a}}.label{{font:600 15px system-ui,-apple-system,Segoe UI,sans-serif;fill:#334155}}.axis{{font:500 13px system-ui,-apple-system,Segoe UI,sans-serif;fill:#64748b}}</style>
  <rect width="1200" height="520" rx="22" fill="#f8fafc"/>
  <text class="title" x="65" y="58">Phase 7B · Target retained at reacquisition</text>
  <text class="subtitle" x="65" y="88">Fresh paired mechanism study; six fixed configurations per memory condition.</text>
  <line x1="70" y1="370" x2="1135" y2="370" stroke="#cbd5e1" stroke-width="2"/>
  <line x1="70" y1="120" x2="1135" y2="120" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="6 7"/>
  <text class="axis" x="40" y="375">0</text><text class="axis" x="35" y="125">6</text>
  {''.join(bars)}
  <rect x="65" y="452" width="1070" height="42" rx="10" fill="#eef2ff"/>
  <text class="axis" x="85" y="478">K=8 matched object memory here; this narrow result does not establish general equivalence. · analysis {digest}</text>
</svg>
"""
    return _write_text(output_path, svg)


def _records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _safe_frame_path(trace_dir: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe frame path in trace: {value}")
    resolved = (trace_dir / relative).resolve()
    if trace_dir.resolve() not in resolved.parents:
        raise ValueError(f"frame path escapes trace directory: {value}")
    return resolved


def _visible_types(request: Mapping[str, Any]) -> list[str]:
    observation = request.get("observation", {})
    objects = observation.get("objects", []) if isinstance(observation, Mapping) else []
    values = {
        str(item.get("object_type") or item.get("objectType") or "")
        for item in objects
        if isinstance(item, Mapping)
    }
    return sorted((value for value in values if value), key=lambda value: (value != "Book", value))


def _memory_lines(request: Mapping[str, Any]) -> list[str]:
    records = request.get("retrieved_memory", [])
    lines: list[str] = []
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, Mapping):
            continue
        object_type = str(record.get("object_type") or record.get("objectType") or "object")
        last_seen = record.get("last_seen_step")
        suffix = f" · last seen step {last_seen}" if last_seen is not None else ""
        lines.append(f"{object_type}{suffix}")
    return lines


def _font(ImageFont: Any, size: int, *, bold: bool = False) -> Any:
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _fit_image(image: Any, Image: Any, size: tuple[int, int]) -> Any:
    canvas = Image.new("RGB", size, "#020617")
    copy = image.convert("RGB")
    copy.thumbnail(size)
    canvas.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return canvas


def _beat_label(*, stage: str, reason: str, visible: list[str], task_success: bool) -> str:
    if task_success:
        return "TARGET REACQUIRED · PICKUP COMPLETE"
    if reason.startswith("return_to_last_seen"):
        return "MEMORY-GUIDED RETURN TO LAST-SEEN VIEW"
    if stage.startswith("controlled_distraction") and "Book" not in visible:
        return "TARGET OUT OF CURRENT VIEW"
    if "Book" in visible:
        return "TARGET VISIBLE · MEMORY RECORD AVAILABLE"
    return stage.replace("_", " ").upper()


def _compact_visible(values: list[str]) -> str:
    selected = values[:5]
    text = ", ".join(selected) if selected else "None"
    if len(values) > len(selected):
        text += f" · +{len(values) - len(selected)} more"
    return "\n".join(textwrap.wrap(text, width=34))


def render_demo(trace_dir: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    """Create a GIF/poster using only planner-visible trace fields and RGB frames."""

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - depends on optional thor extra
        raise RuntimeError("Pillow is required to render the README replay") from exc

    rows = _records(trace_dir / "episode.jsonl")
    summary = json.loads((trace_dir / "summary.json").read_text(encoding="utf-8"))
    if not rows:
        raise ValueError("episode trace contains no evaluated steps")
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas_size = (1200, 500)
    frame_size = (720, 405)
    title_font = _font(ImageFont, 28, bold=True)
    heading_font = _font(ImageFont, 18, bold=True)
    body_font = _font(ImageFont, 16)
    small_font = _font(ImageFont, 13)
    frames: list[Any] = []

    for index, row in enumerate(rows):
        observation = row.get("observation", {})
        frame_value = observation.get("frame_path") if isinstance(observation, Mapping) else None
        if not frame_value:
            continue
        source = _safe_frame_path(trace_dir, str(frame_value))
        rgb = _fit_image(Image.open(source), Image, frame_size)
        canvas = Image.new("RGB", canvas_size, "#f8fafc")
        canvas.paste(rgb, (35, 55))
        draw = ImageDraw.Draw(canvas)
        request = row.get("planner_input", {}).get("request", {})
        decision = row.get("planner_decision", {})
        action = decision.get("action", {}) if isinstance(decision, Mapping) else {}
        feedback = row.get("environment_feedback", {})
        visible = _visible_types(request)
        memory = _memory_lines(request)
        stage = str(request.get("task_stage") or "")
        action_name = str(action.get("action") or "") if isinstance(action, Mapping) else str(action)
        reason = str(decision.get("reason_code") or "")
        success = bool(feedback.get("action_success"))
        task_success = bool(feedback.get("task_success"))

        draw.text((35, 17), "REAL AI2-THOR · PLANNER-VISIBLE PRESENTATION REPLAY", fill="#1e3a8a", font=small_font)
        draw.rounded_rectangle((790, 55, 1165, 460), radius=18, fill="#0f172a")
        draw.text((820, 76), f"Step {row.get('step', index + 1)}", fill="#ffffff", font=title_font)
        beat = _beat_label(stage=stage, reason=reason, visible=visible, task_success=task_success)
        draw.multiline_text(
            (820, 118),
            "\n".join(textwrap.wrap(beat, width=38)),
            fill="#93c5fd",
            font=small_font,
            spacing=3,
        )
        y = 165
        draw.text((820, y), "VISIBLE OBJECTS", fill="#5eead4", font=heading_font)
        y += 30
        draw.multiline_text((820, y), _compact_visible(visible), fill="#e2e8f0", font=body_font, spacing=3)
        y = 240
        draw.text((820, y), "RETRIEVED MEMORY", fill="#5eead4", font=heading_font)
        y += 30
        draw.text((820, y), memory[0] if memory else "None", fill="#e2e8f0", font=body_font)
        y = 315
        draw.text((820, y), "PLANNER ACTION", fill="#c4b5fd", font=heading_font)
        y += 30
        draw.text((820, y), action_name or "None", fill="#ffffff", font=body_font)
        y += 25
        compact_reason = "\n".join(textwrap.wrap(reason.replace("_", " "), width=42)[:2])
        draw.multiline_text((820, y), compact_reason, fill="#94a3b8", font=small_font, spacing=2)
        y = 420
        status = "Task completed" if task_success else ("Action succeeded" if success else "Action failed")
        draw.text((820, y), status, fill="#86efac" if success else "#fca5a5", font=heading_font)
        draw.text((35, 472), "RGB is a human-audit artifact; evaluator-only state is excluded from this overlay.", fill="#475569", font=small_font)
        frames.append(canvas)

    if not frames:
        raise ValueError("episode trace contains no saved planner-step frames")
    gif_path = output_dir / "book_reacquisition.gif"
    poster_path = output_dir / "book_reacquisition_poster.png"
    manifest_path = output_dir / "demo_manifest.json"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=[1900] * len(frames),
        loop=0,
        optimize=True,
        disposal=2,
    )
    frames[0].save(poster_path, optimize=True)
    manifest = {
        "artifact_role": "presentation_only_not_formal_comparative_evidence",
        "source_boundary": "planner_visible_trace_and_in_memory_rgb_frames_only",
        "desktop_screenshot_used": False,
        "evaluator_only_state_in_overlay": False,
        "scene": summary.get("scene"),
        "task": summary.get("task"),
        "memory": summary.get("memory"),
        "success": summary.get("success"),
        "evaluated_step_count": summary.get("steps"),
        "rendered_frame_count": len(frames),
        "source_episode_jsonl_sha256": _sha256(trace_dir / "episode.jsonl"),
        "gif_sha256": _sha256(gif_path),
        "poster_sha256": _sha256(poster_path),
        "generator": "scripts/render_readme_assets.py",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return gif_path, poster_path, manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--trace-dir", type=Path, help="optional saved-frame episode directory")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    render_system_overview(args.output_dir / "system_overview.svg")
    render_memory_horizon_chart(args.evidence, args.output_dir / "memory_horizon_retention.svg")
    if args.trace_dir:
        render_demo(args.trace_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

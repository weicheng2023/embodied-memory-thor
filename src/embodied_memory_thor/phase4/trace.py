"""Durable JSON, console, frame, and HTML traces for Phase 4."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any, Mapping

from embodied_memory_thor.phase4.contracts import EVALUATOR_ONLY_LABEL, RGB_BOUNDARY_LABEL
from embodied_memory_thor.utils.serialization import to_jsonable


def file_sha256(path: str | Path) -> str:
    """Hash a saved frame so the JSONL/HTML alignment can be audited."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rgb_array_diagnostics(frame: Any) -> dict[str, Any]:
    """Describe an AI2-THOR RGB array without taking or writing a screenshot."""

    base: dict[str, Any] = {
        "available": frame is not None,
        "diagnostic_method": "in_memory_rgb_array_bytes_no_desktop_capture",
        "frame_shape": list(getattr(frame, "shape", [])) if frame is not None else [],
        "frame_dtype": str(getattr(frame, "dtype", "")) if frame is not None else "",
        "raw_sha256": None,
        "byte_count": 0,
        "channel_byte_min": None,
        "channel_byte_max": None,
        "channel_byte_mean": None,
        "channel_byte_std": None,
        "near_black_channel_fraction": None,
        "suspected_all_black": None,
    }
    if frame is None:
        return base

    try:
        raw = frame.tobytes()
    except (AttributeError, TypeError, ValueError):
        return base
    if not raw:
        return base

    count = len(raw)
    total = sum(raw)
    mean = total / count
    variance = max(0.0, sum(value * value for value in raw) / count - mean * mean)
    minimum = min(raw)
    maximum = max(raw)
    near_black_count = sum(value <= 5 for value in raw)
    base.update(
        {
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "byte_count": count,
            "channel_byte_min": minimum,
            "channel_byte_max": maximum,
            "channel_byte_mean": mean,
            "channel_byte_std": variance**0.5,
            "near_black_channel_fraction": near_black_count / count,
            "suspected_all_black": maximum <= 5,
        }
    )
    return base


class ThorTraceWriter:
    """Write planner-safe trace files and separately gated evaluator state."""

    def __init__(self, output_dir: str | Path, *, evaluator_debug: bool = False) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=False)
        self.frames_dir = self.output_dir / "frames"
        self.setup_path = self.output_dir / "setup.jsonl"
        self.episode_path = self.output_dir / "episode.jsonl"
        self.summary_path = self.output_dir / "summary.json"
        self.manifest_path = self.output_dir / "run_manifest.json"
        self.html_path = self.output_dir / "trace.html"
        self.evaluator_path = self.output_dir / "evaluator_debug.jsonl"
        self.setup_path.write_text("", encoding="utf-8")
        self.episode_path.write_text("", encoding="utf-8")
        self.evaluator_debug = evaluator_debug
        if evaluator_debug:
            self.evaluator_path.write_text("", encoding="utf-8")
        self._steps: list[dict[str, Any]] = []
        self._setup_events: list[dict[str, Any]] = []

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.write_text(
            json.dumps(
                to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True
            )
            + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _append_jsonl(path: Path, value: Any) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True)
            )
            handle.write("\n")

    def write_manifest(self, manifest: Mapping[str, Any]) -> None:
        self._write_json(self.manifest_path, manifest)

    def log_step(self, record: Mapping[str, Any]) -> None:
        payload = to_jsonable(dict(record))
        self._steps.append(payload)
        self._append_jsonl(self.episode_path, payload)

    def log_setup(self, record: Mapping[str, Any]) -> None:
        """Write planner-independent task setup separately from evaluated steps."""

        payload = to_jsonable(dict(record))
        self._setup_events.append(payload)
        self._append_jsonl(self.setup_path, payload)

    def log_evaluator_state(self, *, step: int, metadata: Mapping[str, Any]) -> None:
        if not self.evaluator_debug:
            return
        self._append_jsonl(
            self.evaluator_path,
            {
                "label": EVALUATOR_ONLY_LABEL,
                "step": int(step),
                "metadata": to_jsonable(metadata),
            },
        )

    def write_summary(self, summary: Mapping[str, Any]) -> None:
        self._write_json(self.summary_path, summary)

    def render_html(self, summary: Mapping[str, Any]) -> Path:
        """Render a portable four-panel trace with relative frame links."""

        title = html.escape(
            f"{summary.get('task', 'Phase 4 episode')} — {summary.get('episode_id', '')}"
        )
        setup_blocks = "\n".join(
            f"<details><summary>Setup observation {html.escape(str(event.get('setup_index')))}</summary>"
            f"<pre>{self._escaped_json(event)}</pre></details>"
            for event in self._setup_events
        )
        step_blocks = "\n".join(self._step_html(step) for step in self._steps)
        summary_json = html.escape(
            json.dumps(to_jsonable(summary), indent=2, ensure_ascii=False, sort_keys=True)
        )
        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ max-width: 1500px; margin: 0 auto; padding: 24px; background: #101319; color: #eef2f7; }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    .notice {{ border: 2px solid #f0b429; padding: 12px; margin: 16px 0; background: #342a10; }}
    .step {{ border-top: 4px solid #4f8cff; padding-top: 18px; margin-top: 32px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .panel {{ border: 1px solid #3a4658; border-radius: 8px; padding: 14px; background: #171d27; overflow: auto; }}
    .panel h3 {{ color: #8db5ff; }}
    img {{ width: 100%; max-height: 520px; object-fit: contain; background: #000; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; }}
    .ok {{ color: #5bd18b; }} .fail {{ color: #ff7272; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="notice"><strong>Observation boundary:</strong> {html.escape(RGB_BOUNDARY_LABEL)}.<br>
  Evaluator detail, when explicitly enabled, is stored separately as
  <strong>{html.escape(EVALUATOR_ONLY_LABEL)}</strong>.</div>
  <details><summary>Episode summary</summary><pre>{summary_json}</pre></details>
  <section><h2>Planner-independent task setup</h2>{setup_blocks}</section>
  {step_blocks}
</body>
</html>
"""
        self.html_path.write_text(document, encoding="utf-8")
        return self.html_path

    def _step_html(self, step: Mapping[str, Any]) -> str:
        index = int(step.get("step", 0))
        observation = step.get("observation", {})
        planner_input = step.get("planner_input", {})
        decision = step.get("planner_decision", {})
        feedback = step.get("environment_feedback", {})
        frame = observation.get("frame_path") if isinstance(observation, Mapping) else None
        if frame:
            frame_html = (
                f'<img src="{html.escape(str(frame))}" alt="AI2-THOR step {index} frame">'
            )
        else:
            frame_html = "<p>Frame was not saved for this run.</p>"
        status_class = "ok" if feedback.get("action_success") else "fail"
        return f"""
<section class="step">
  <h2>Step {index}</h2>
  <div class="grid">
    <article class="panel"><h3>A. RGB Observation</h3>{frame_html}
      <p>{html.escape(RGB_BOUNDARY_LABEL)}</p>
      <pre>{self._escaped_json(observation)}</pre></article>
    <article class="panel"><h3>B. Planner Input</h3><pre>{self._escaped_json(planner_input)}</pre></article>
    <article class="panel"><h3>C. Planner Decision</h3><pre>{self._escaped_json(decision)}</pre></article>
    <article class="panel"><h3>D. Environment Feedback</h3>
      <p class="{status_class}">Action success: {html.escape(str(feedback.get('action_success')))}</p>
      <pre>{self._escaped_json(feedback)}</pre></article>
  </div>
</section>"""

    @staticmethod
    def _escaped_json(value: Any) -> str:
        return html.escape(
            json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        )


def render_console_step(record: Mapping[str, Any]) -> None:
    """Print the compact live/debug view without evaluator-only metadata."""

    planner_input = record.get("planner_input", {})
    request = planner_input.get("request", {}) if isinstance(planner_input, Mapping) else {}
    observation = request.get("observation", {}) if isinstance(request, Mapping) else {}
    objects = observation.get("objects", []) if isinstance(observation, Mapping) else []
    visible = [
        f"{obj.get('objectType')} ({obj.get('objectId')})"
        for obj in objects
        if isinstance(obj, Mapping)
    ]
    retrieval = request.get("retrieved_memory", []) if isinstance(request, Mapping) else []
    decision = record.get("planner_decision", {})
    feedback = record.get("environment_feedback", {})
    print(f"\nStep {record.get('step')}")
    print(f"RGB frame: {record.get('observation', {}).get('frame_path') or 'not saved'}")
    print(f"Visible objects: {', '.join(visible) if visible else '(none)'}")
    print(
        "Memory retrieval: "
        + (
            ", ".join(str(item.get("record_id")) for item in retrieval)
            if retrieval
            else "(none)"
        )
    )
    print(f"Planner input digest: {planner_input.get('audit', {}).get('input_digest')}")
    print(f"Planner output: {decision.get('action')} [{decision.get('reason_code')}]")
    print(
        f"Action result: {'success' if feedback.get('action_success') else 'failure'}"
        + (f" — {feedback.get('error_message')}" if feedback.get("error_message") else "")
    )
    print(
        "Memory update: "
        + json.dumps(feedback.get("memory_update", {}), ensure_ascii=False, sort_keys=True)
    )
    print(
        "Success checker: "
        + ("completed" if feedback.get("task_success") else "not completed")
        + " (evaluator-only verdict; not returned to planner)"
    )


class LiveFrameViewer:
    """Optional OpenCV RGB window used only by the debug presentation layer."""

    def __init__(self, title: str = "Embodied-Memory-THOR Phase 4") -> None:
        try:
            import cv2
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError("OpenCV is required for --visualize") from exc
        self.cv2 = cv2
        self.title = title

    def show(self, rgb_frame: Any, *, step_delay: float) -> bool:
        if rgb_frame is None:
            raise RuntimeError("AI2-THOR event has no RGB frame for visualization")
        bgr = self.cv2.cvtColor(rgb_frame, self.cv2.COLOR_RGB2BGR)
        self.cv2.imshow(self.title, bgr)
        delay_ms = max(1, int(max(0.0, step_delay) * 1000))
        key = int(self.cv2.waitKey(delay_ms)) & 0xFF
        return key not in (27, ord("q"))

    def close(self) -> None:
        self.cv2.destroyWindow(self.title)

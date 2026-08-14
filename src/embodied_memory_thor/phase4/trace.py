"""Durable JSON, console, frame, and HTML traces for Phase 4."""

from __future__ import annotations

import hashlib
import html
import json
import multiprocessing
import os
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full
from time import monotonic
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


@dataclass(frozen=True)
class ViewerDisplayResult:
    """One safe status message from the optional presentation process."""

    available: bool
    displayed: bool = False
    user_stopped: bool = False
    failure_reason: str = ""


def _redirect_native_stderr(path: str | None) -> None:
    """Capture native Qt/OpenCV diagnostics that bypass Python ``sys.stderr``."""

    if not path:
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.dup2(descriptor, 2)
    finally:
        os.close(descriptor)


def _opencv_viewer_worker(
    frame_queue: Any,
    status_queue: Any,
    title: str,
    stderr_path: str | None,
) -> None:
    """Own all Qt/OpenCV GUI calls so a native abort cannot kill the episode."""

    try:
        _redirect_native_stderr(stderr_path)
        import cv2
    except BaseException as exc:
        status_queue.put(
            {
                "kind": "startup_error",
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )
        return

    status_queue.put({"kind": "ready"})
    try:
        while True:
            payload = frame_queue.get()
            if payload is None:
                break
            rgb_frame, delay_ms = payload
            try:
                bgr = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
                cv2.imshow(title, bgr)
                key = int(cv2.waitKey(int(delay_ms))) & 0xFF
            except BaseException as exc:
                status_queue.put(
                    {
                        "kind": "display_error",
                        "reason": f"{type(exc).__name__}: {exc}",
                    }
                )
                break
            if key in (27, ord("q")):
                status_queue.put({"kind": "user_stopped"})
                break
            status_queue.put({"kind": "displayed"})
    finally:
        try:
            cv2.destroyAllWindows()
        except BaseException:
            pass


class LiveFrameViewer:
    """Crash-isolated optional OpenCV viewer for the debug presentation layer."""

    def __init__(
        self,
        title: str = "Embodied-Memory-THOR Phase 4",
        *,
        diagnostic_log: str | Path | None = None,
        startup_timeout_seconds: float = 5.0,
        response_grace_seconds: float = 3.0,
        worker_target: Any = _opencv_viewer_worker,
    ) -> None:
        self.title = title
        self.diagnostic_log = (
            str(Path(diagnostic_log).expanduser().resolve())
            if diagnostic_log is not None
            else None
        )
        self.response_grace_seconds = max(0.5, float(response_grace_seconds))
        self._context = multiprocessing.get_context("spawn")
        self._frames = self._context.Queue(maxsize=1)
        self._statuses = self._context.Queue()
        self._process = self._context.Process(
            target=worker_target,
            args=(self._frames, self._statuses, self.title, self.diagnostic_log),
            name="phase4-opencv-viewer",
            daemon=True,
        )
        try:
            self._process.start()
            self.startup_status = self._await_status(
                timeout_seconds=max(0.5, float(startup_timeout_seconds)),
                phase="startup",
            )
        except BaseException as exc:
            self.startup_status = ViewerDisplayResult(
                available=False,
                failure_reason=f"viewer_start_failed:{type(exc).__name__}:{exc}",
            )
            self._stop_process()

    @property
    def available(self) -> bool:
        return bool(
            self.startup_status.available
            and self._process is not None
            and self._process.is_alive()
        )

    def show(self, rgb_frame: Any, *, step_delay: float) -> ViewerDisplayResult:
        if not self.available:
            reason = self.startup_status.failure_reason or self._exit_reason("display")
            return ViewerDisplayResult(available=False, failure_reason=reason)
        if rgb_frame is None:
            return ViewerDisplayResult(
                available=False,
                failure_reason="viewer_frame_missing:AI2-THOR event has no RGB frame",
            )

        delay_ms = max(1, int(max(0.0, step_delay) * 1000))
        try:
            self._frames.put((rgb_frame, delay_ms), timeout=1.0)
        except Full:
            return ViewerDisplayResult(
                available=False,
                failure_reason="viewer_frame_queue_full",
            )
        return self._await_status(
            timeout_seconds=(delay_ms / 1000.0) + self.response_grace_seconds,
            phase="display",
        )

    def _await_status(self, *, timeout_seconds: float, phase: str) -> ViewerDisplayResult:
        deadline = monotonic() + timeout_seconds
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                self._stop_process()
                return ViewerDisplayResult(
                    available=False,
                    failure_reason=f"viewer_{phase}_timeout",
                )
            try:
                message = self._statuses.get(timeout=min(0.1, remaining))
            except Empty:
                if not self._process.is_alive():
                    return ViewerDisplayResult(
                        available=False,
                        failure_reason=self._exit_reason(phase),
                    )
                continue

            kind = str(message.get("kind", "")) if isinstance(message, Mapping) else ""
            reason = str(message.get("reason", "")) if isinstance(message, Mapping) else ""
            if kind == "ready":
                return ViewerDisplayResult(available=True)
            if kind == "displayed":
                return ViewerDisplayResult(available=True, displayed=True)
            if kind == "user_stopped":
                return ViewerDisplayResult(available=False, user_stopped=True)
            if kind in {"startup_error", "display_error"}:
                return ViewerDisplayResult(
                    available=False,
                    failure_reason=f"viewer_{kind}:{reason}",
                )

    def _exit_reason(self, phase: str) -> str:
        exit_code = self._process.exitcode if self._process is not None else None
        suffix = f"; diagnostic_log={self.diagnostic_log}" if self.diagnostic_log else ""
        return f"viewer_process_exited_during_{phase}:exit_code={exit_code}{suffix}"

    def _stop_process(self) -> None:
        process = getattr(self, "_process", None)
        if process is None:
            return
        if process.is_alive():
            process.terminate()
            process.join(timeout=2.0)

    def close(self) -> None:
        process = getattr(self, "_process", None)
        if process is not None and process.is_alive():
            try:
                self._frames.put(None, timeout=0.5)
            except Full:
                pass
            process.join(timeout=2.0)
        self._stop_process()
        for queue in (getattr(self, "_frames", None), getattr(self, "_statuses", None)):
            if queue is None:
                continue
            try:
                queue.close()
                queue.cancel_join_thread()
            except (AttributeError, OSError, ValueError):
                pass

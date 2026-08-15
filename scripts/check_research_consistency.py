#!/usr/bin/env python3
"""Catch deterministic cross-document and frozen-artifact drift."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
ABSTRACT_RE = re.compile(
    r"## Copy-ready English version \((\d+) words\)\s+(.*?)\s+## Claim boundary",
    flags=re.DOTALL,
)

REQUIRED_PATHS = (
    "README.md",
    "docs/application_abstract.md",
    "docs/development_status.md",
    "docs/report.md",
    "docs/architecture.md",
    "docs/CONTRIBUTIONS_AND_REPRODUCIBILITY.md",
    "docs/phase5_formal_results.md",
    "docs/phase5_experiment_protocol.md",
    "docs/evidence/phase5_real_formal_v5_complete.json",
    "docs/evidence/phase5_real_formal_v5_descriptive_results.json",
    "configs/phase5_real_formal_pilot_v5.json",
    "configs/phase5_real_formal_execution_v5.json",
)

CURRENT_FACING_PATHS = (
    "README.md",
    "docs/application_abstract.md",
    "docs/report.md",
    "docs/phase5_formal_results.md",
)

ACCEPTED_JSON_DIGESTS = {
    "docs/evidence/phase5_real_formal_v5_complete.json": (
        "8dafb14146b69c41f913db36b119a8429d99ddfd1d23ead4ec92b4b302e98ff6"
    ),
    "docs/evidence/phase5_real_formal_v5_descriptive_results.json": (
        "95712583c3849970621fe2d1fe0a66045f43fbd97646a564a1d43ed715b9fcad"
    ),
}


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_sha256(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def abstract_word_count(text: str) -> tuple[int, int] | None:
    """Return (declared, actual) using the same rule as the documentation test."""

    match = ABSTRACT_RE.search(text)
    if match is None:
        return None
    return int(match.group(1)), len(WORD_RE.findall(match.group(2)))


def markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        return ""
    next_heading = text.find("\n## ", start + len(marker))
    return text[start:] if next_heading < 0 else text[start:next_heading]


def _phase7_status(root: Path) -> str:
    path = root / "docs" / "phase7" / "README.md"
    if not path.is_file():
        return "absent"
    match = re.search(
        r"^Current status:\s*([a-z0-9_-]+)\s*$",
        path.read_text(encoding="utf-8"),
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return "unspecified" if match is None else match.group(1).lower()


def check_repository(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED_PATHS:
        if not (root / relative).is_file():
            errors.append(f"missing required canonical path: {relative}")

    if errors:
        return errors

    readme = _read(root, "README.md")
    abstract = _read(root, "docs/application_abstract.md")
    status = _read(root, "docs/development_status.md")

    if "docs/phase5_formal_results.md" not in readme:
        errors.append("README does not link to docs/phase5_formal_results.md")

    supervisor_section = markdown_section(readme, "Research presentation package")
    if not supervisor_section:
        errors.append("README is missing the Research presentation package section")
    elif "PROJECT_SCORECARD.md" in supervisor_section:
        errors.append("README supervisor-facing package lists PROJECT_SCORECARD.md")

    for relative in CURRENT_FACING_PATHS:
        text = _read(root, relative).lower()
        if "clean positive result" in text:
            errors.append(f"unsupported phrase 'clean positive result' in {relative}")

    count = abstract_word_count(abstract)
    if count is None:
        errors.append("application abstract word-count block is missing or malformed")
    elif count[0] != count[1]:
        errors.append(
            f"application abstract declares {count[0]} words but contains {count[1]}"
        )

    readme_phase = re.search(r"Phases 0-(\d+) are complete", readme)
    status_phase = re.search(r"Current status: Phases 0-(\d+) complete", status)
    if readme_phase is None or status_phase is None:
        errors.append("current Phase 0-N completion labels are missing")
    elif readme_phase.group(1) != status_phase.group(1):
        errors.append(
            "README and development-status current phase labels disagree: "
            f"{readme_phase.group(1)} != {status_phase.group(1)}"
        )

    for relative, expected in ACCEPTED_JSON_DIGESTS.items():
        actual = _canonical_json_sha256(root / relative)
        if actual != expected:
            errors.append(f"accepted Phase-5 evidence content changed: {relative}")

    manifest_path = root / "configs" / "phase5_real_formal_pilot_v5.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative, expected in manifest.get("historical_artifacts_frozen", {}).items():
        path = root / relative
        if not path.is_file():
            errors.append(f"formal-v5 registered artifact moved or missing: {relative}")
        elif _sha256(path) != expected:
            errors.append(f"formal-v5 registered artifact changed: {relative}")

    phase7_status = _phase7_status(root)
    if phase7_status != "absent":
        for relative in (
            "docs/phase7/README.md",
            "docs/phase7/holdout_protocol.md",
            "configs/phase7/holdout_candidate_pool.json",
            "configs/phase7/holdout_manifest.json",
        ):
            if not (root / relative).is_file():
                errors.append(f"Phase-7 namespace is incomplete: {relative}")
    phase7_linked = "docs/phase7/" in readme
    phase7_named = bool(re.search(r"\bPhase 7[AB]?\b", readme, flags=re.IGNORECASE))
    if phase7_status == "accepted" and not phase7_linked:
        errors.append("Phase 7 is accepted but README has no Phase-7 evidence link")
    if phase7_status != "accepted" and (phase7_linked or phase7_named):
        errors.append("README claims or links Phase 7 before Phase 7 is accepted")

    return errors


def main() -> int:
    errors = check_repository()
    if errors:
        print("research consistency check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("research consistency check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

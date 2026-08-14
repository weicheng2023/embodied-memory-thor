from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_phase6_required_documents_exist() -> None:
    required = (
        ROOT / "README.md",
        ROOT / "PROJECT_SCORECARD.md",
        DOCS / "architecture.md",
        DOCS / "report.md",
        DOCS / "failure_cases.md",
        DOCS / "application_abstract.md",
        DOCS / "phase5_formal_results.md",
    )
    assert all(path.is_file() for path in required)


def test_application_abstract_is_copy_ready_and_120_to_180_words() -> None:
    text = _read(DOCS / "application_abstract.md")
    match = re.search(
        r"## Copy-ready English version \((\d+) words\)\s+(.*?)\s+## Claim boundary",
        text,
        flags=re.DOTALL,
    )
    assert match is not None
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", match.group(2))
    assert 120 <= len(words) <= 180
    assert int(match.group(1)) == len(words)


def test_report_contains_required_research_sections_and_claim_boundary() -> None:
    text = _read(DOCS / "report.md")
    for heading in (
        "## Motivation",
        "## Research question",
        "## System design",
        "## Tasks and experimental panels",
        "## Metrics",
        "## Results",
        "## Failure analysis",
        "## Limitations",
        "## Future work",
        "## Conclusion",
    ):
        assert heading in text
    assert "not a state-of-the-art method" in text
    assert re.search(r"No\s+significance test", text)
    assert "54/54" in text


def test_architecture_and_failure_analysis_cover_required_components() -> None:
    architecture = _read(DOCS / "architecture.md")
    assert "```mermaid" in architecture
    for component in (
        "Environment layer",
        "PlannerRequest",
        "Memory provider",
        "ActionExecutor",
        "State-based success checker",
        "Evidence layer",
    ):
        assert component in architecture

    failures = _read(DOCS / "failure_cases.md")
    assert failures.count("| Target not visible") == 1
    assert "Valid interaction rejected by simulator" in failures
    assert "Stale memory does not always yield an explicit miss" in failures
    assert "GUI fails while simulator works" in failures


def test_scorecard_is_conservative_complete_and_sums_to_91() -> None:
    text = _read(ROOT / "PROJECT_SCORECARD.md")
    assert "Final score: **91/100 (A level)**" in text
    scores = [
        (14, 15),
        (14, 15),
        (14, 15),
        (18, 20),
        (13, 15),
        (9, 10),
        (9, 10),
    ]
    assert sum(score for score, _ in scores) == 91
    for score, maximum in scores:
        assert f"{score}/{maximum}" in text
    assert "Why this is not scored higher" in text

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_research_consistency.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("research_consistency", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_repository_is_research_consistent() -> None:
    checker = _load_checker()
    assert checker.check_repository(ROOT) == []


def test_abstract_word_count_uses_documented_rule() -> None:
    checker = _load_checker()
    text = """# Abstract

## Copy-ready English version (4 words)

Memory-guided agents re-find objects.

## Claim boundary
"""
    assert checker.abstract_word_count(text) == (4, 4)


def test_supervisor_section_isolated_from_later_sections() -> None:
    checker = _load_checker()
    text = """## Research presentation package

- report

## Historical material

- PROJECT_SCORECARD.md
"""
    section = checker.markdown_section(text, "Research presentation package")
    assert "report" in section
    assert "PROJECT_SCORECARD.md" not in section

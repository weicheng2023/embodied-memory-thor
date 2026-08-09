"""Non-destructive runtime diagnostics for Embodied-Memory-THOR.

The checks in this module inspect local capability without starting an
AI2-THOR controller, downloading a Unity build, or exposing secret values.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class CheckResult:
    """Result of one environment capability check."""

    name: str
    status: str
    message: str
    required_for: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable representation."""

        return asdict(self)


@dataclass(frozen=True)
class EnvironmentReport:
    """Complete set of local capability checks and a recommendation."""

    checks: tuple[CheckResult, ...]
    recommendation: str

    @property
    def strict_ready(self) -> bool:
        """Whether all optional real-environment capabilities are available."""

        return all(check.status == "PASS" for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "checks": [check.to_dict() for check in self.checks],
            "strict_ready": self.strict_ready,
            "recommendation": self.recommendation,
        }


def _python_check() -> CheckResult:
    version = platform.python_version()
    supported = sys.version_info >= (3, 10)
    return CheckResult(
        name="Python",
        status="PASS" if supported else "FAIL",
        message=f"{version} ({'supported' if supported else 'requires Python 3.10+'})",
        required_for="all modes",
    )


def _ai2thor_check() -> CheckResult:
    installed = importlib.util.find_spec("ai2thor") is not None
    return CheckResult(
        name="AI2-THOR package",
        status="PASS" if installed else "WARN",
        message="installed" if installed else "not installed; mock mode remains available",
        required_for="real environment only",
    )


def _controller_check() -> CheckResult:
    try:
        spec = importlib.util.find_spec("ai2thor.controller")
    except (ImportError, ModuleNotFoundError, AttributeError, ValueError) as exc:
        return CheckResult(
            name="AI2-THOR Controller",
            status="WARN",
            message=f"not importable ({type(exc).__name__}); mock mode remains available",
            required_for="real environment only",
        )

    return CheckResult(
        name="AI2-THOR Controller",
        status="PASS" if spec is not None else "WARN",
        message="importable" if spec is not None else "not importable; mock mode remains available",
        required_for="real environment only",
    )


def _secret_check(environ: Mapping[str, str]) -> CheckResult:
    configured = bool(environ.get("OPENAI_API_KEY", "").strip())
    return CheckResult(
        name="OpenAI-compatible API key",
        status="PASS" if configured else "WARN",
        message="configured (value hidden)" if configured else "not configured; mock planner will be used",
        required_for="real LLM planner only",
    )


def _base_url_check(environ: Mapping[str, str]) -> CheckResult:
    configured = bool(environ.get("OPENAI_BASE_URL", "").strip())
    return CheckResult(
        name="OpenAI-compatible base URL",
        status="PASS",
        message="custom endpoint configured (value hidden)" if configured else "not set; default provider endpoint may be used",
        required_for="custom LLM endpoints only",
    )


def _display_check(environ: Mapping[str, str]) -> CheckResult:
    system = platform.system()
    in_ci = any(environ.get(name) for name in ("CI", "GITHUB_ACTIONS", "TF_BUILD"))

    if in_ci:
        status = "WARN"
        message = "CI environment detected; a graphical display is not assumed"
    elif system == "Windows":
        session = environ.get("SESSIONNAME", "").strip()
        status = "PASS"
        message = f"Windows session detected{f' ({session})' if session else ''}; rendering still requires runtime verification"
    elif system == "Darwin":
        status = "PASS"
        message = "macOS session detected; rendering still requires runtime verification"
    elif environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY"):
        status = "PASS"
        message = "DISPLAY or WAYLAND_DISPLAY is set; rendering still requires runtime verification"
    else:
        status = "WARN"
        message = "no display variable detected; use mock mode or configure a virtual display"

    return CheckResult(
        name="Graphical display hint",
        status=status,
        message=message,
        required_for="real environment rendering only",
    )


def collect_environment_report(environ: Mapping[str, str] | None = None) -> EnvironmentReport:
    """Collect diagnostics without launching AI2-THOR or making network calls."""

    effective_environ = os.environ if environ is None else environ
    checks = (
        _python_check(),
        _ai2thor_check(),
        _controller_check(),
        _secret_check(effective_environ),
        _base_url_check(effective_environ),
        _display_check(effective_environ),
    )

    by_name = {check.name: check for check in checks}
    real_env_ready = all(
        by_name[name].status == "PASS"
        for name in ("Python", "AI2-THOR package", "AI2-THOR Controller", "Graphical display hint")
    )
    llm_ready = by_name["OpenAI-compatible API key"].status == "PASS"

    if real_env_ready and llm_ready:
        recommendation = "Real AI2-THOR and LLM capabilities appear available; verify them at runtime in later phases."
    elif real_env_ready:
        recommendation = "AI2-THOR appears available. Use a mock planner until an API key is configured."
    else:
        recommendation = "Continue with the planned mock environment; install or configure optional capabilities when needed."

    return EnvironmentReport(checks=checks, recommendation=recommendation)


def format_human_report(report: EnvironmentReport) -> str:
    """Format diagnostics for terminal users."""

    lines = ["Embodied-Memory-THOR Environment Check", ""]
    for check in report.checks:
        lines.append(f"[{check.status}] {check.name}: {check.message}")
        lines.append(f"       Required for: {check.required_for}")
    lines.extend(("", "Recommendation:", report.recommendation))
    return "\n".join(lines)

#!/usr/bin/env python3
"""Authorize and execute one fresh privacy-safe formal-v4 matrix."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.formal_v2 import (  # noqa: E402
    REAL_EPISODE_COUNT,
    build_public_manifest,
    collect_public_runtime_bindings,
    sha256_file,
    validate_precommit,
)


DEFAULT_AUTHORIZATION = (
    PROJECT_ROOT / "configs" / "phase5_real_formal_execution_v4.json"
)
AUTHORIZATION_VERSION = "phase5-real-thor-formal-execution-authorization-v4"
BASE_PROTOCOL_VERSION = "phase5-real-thor-pilot-v4"
READINESS_EVIDENCE_VERSION = "phase5-real-thor-formal-readiness-v4-result-v1"
AUTHORIZATION_EXECUTOR = "scripts/run_phase5_real_formal_execution_v4.py"


def _implementation() -> object:
    path = PROJECT_ROOT / "scripts" / "run_phase5_real_formal_pilot_v2.py"
    spec = importlib.util.spec_from_file_location("phase5_real_formal_v4_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen formal-v4 executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project_file(relative: str) -> Path:
    path = (PROJECT_ROOT / relative).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("authorization source is outside the project") from exc
    return path


def load_authorized_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("formal-v4 authorization must be a mapping")
    allowed = {
        "authorization_version",
        "authorization_executor",
        "authorization_executor_sha256",
        "base_config",
        "base_config_sha256",
        "readiness_evidence",
        "readiness_evidence_sha256",
        "readiness_code_revision",
        "readiness_manifest_digest",
        "formal_execution_authorized",
        "authorization_scope",
        "matrix_contract_override_allowed",
    }
    if set(map(str, raw)) != allowed:
        raise ValueError("formal-v4 authorization has unexpected fields")
    if raw.get("authorization_version") != AUTHORIZATION_VERSION:
        raise ValueError("formal-v4 authorization version mismatch")
    if raw.get("formal_execution_authorized") is not True:
        raise ValueError("formal-v4 execution is not explicitly authorized")
    if raw.get("matrix_contract_override_allowed") is not False:
        raise ValueError("formal-v4 authorization cannot override the matrix")
    if raw.get("authorization_executor") != AUTHORIZATION_EXECUTOR:
        raise ValueError("formal-v4 authorization executor path mismatch")

    executor_path = _project_file(str(raw["authorization_executor"]))
    if sha256_file(executor_path) != str(raw["authorization_executor_sha256"]):
        raise ValueError("formal-v4 authorization executor changed")
    base_path = _project_file(str(raw["base_config"]))
    if sha256_file(base_path) != str(raw["base_config_sha256"]):
        raise ValueError("formal-v4 readiness base config changed")
    base = json.loads(base_path.read_text(encoding="utf-8"))
    if base.get("protocol_version") != BASE_PROTOCOL_VERSION:
        raise ValueError("formal-v4 readiness base protocol mismatch")
    if base.get("formal_execution_authorized") is not False:
        raise ValueError("formal-v4 readiness base must remain disabled")

    evidence_path = _project_file(str(raw["readiness_evidence"]))
    if sha256_file(evidence_path) != str(raw["readiness_evidence_sha256"]):
        raise ValueError("formal-v4 readiness evidence changed")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if (
        evidence.get("evidence_version") != READINESS_EVIDENCE_VERSION
        or evidence.get("readiness_passed") is not True
        or evidence.get("episode_count") != REAL_EPISODE_COUNT
        or evidence.get("required_metric_count") != 64
        or evidence.get("private_runtime_join_passed") is not True
        or evidence.get("private_runtime_material_serialized") is not False
        or evidence.get("formal_execution_authorized_during_readiness") is not False
        or evidence.get("code_revision") != raw.get("readiness_code_revision")
        or evidence.get("manifest_digest") != raw.get("readiness_manifest_digest")
    ):
        raise ValueError("formal-v4 readiness evidence does not authorize execution")

    effective = deepcopy(dict(base))
    effective["formal_execution_authorized"] = True
    effective["authorization"] = {
        "authorization_version": raw["authorization_version"],
        "authorization_executor_sha256": raw["authorization_executor_sha256"],
        "base_config_sha256": raw["base_config_sha256"],
        "readiness_evidence_sha256": raw["readiness_evidence_sha256"],
        "readiness_code_revision": raw["readiness_code_revision"],
        "readiness_manifest_digest": raw["readiness_manifest_digest"],
        "matrix_contract_override_allowed": False,
    }
    validate_precommit(effective, root=PROJECT_ROOT)
    return effective


def prepare_authorized_run(
    *, authorization_path: Path, output_dir: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], object]:
    if output_dir.exists():
        raise ValueError("formal-v4 output directory already exists")
    config = load_authorized_config(authorization_path)
    implementation = _implementation()
    head, upstream, dirty = implementation._git_state()
    if dirty or head != upstream:
        raise ValueError("formal-v4 execution requires a clean pushed HEAD")
    bindings = collect_public_runtime_bindings(config, root=PROJECT_ROOT)
    manifest = build_public_manifest(config, code_revision=head, bindings=bindings)
    readiness = implementation.build_readiness(config=config, manifest=manifest)
    if readiness.get("readiness_passed") is not True:
        raise ValueError("formal-v4 runtime readiness did not pass")
    output_dir.mkdir(parents=True)
    implementation._write_json(output_dir / "formal_manifest.json", manifest)
    implementation._write_json(output_dir / "readiness.json", readiness)
    return config, manifest, readiness, implementation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=DEFAULT_AUTHORIZATION)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        output_dir = args.output_dir.expanduser().resolve()
        config, manifest, readiness, implementation = prepare_authorized_run(
            authorization_path=args.authorization.expanduser().resolve(),
            output_dir=output_dir,
        )
        result = implementation.execute_formal(
            config=config,
            manifest=manifest,
            readiness=readiness,
            output_dir=output_dir,
        )
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"phase5_real_formal_execution_v4_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if (
        result.get("matrix_complete") is True
        and result.get("integrity_valid") is True
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())

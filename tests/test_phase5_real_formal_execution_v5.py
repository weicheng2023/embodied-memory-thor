from __future__ import annotations

import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = ROOT / "configs" / "phase5_real_formal_execution_v5.json"
BASE = ROOT / "configs" / "phase5_real_formal_pilot_v5.json"
READINESS = ROOT / "docs" / "evidence" / "phase5_real_formal_readiness_v5.json"


def _module() -> object:
    path = ROOT / "scripts" / "run_phase5_real_formal_execution_v5.py"
    spec = importlib.util.spec_from_file_location("phase5_formal_v5_authorization_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v5_authorization_only_flips_execution_and_adds_audit_binding() -> None:
    module = _module()
    base = json.loads(BASE.read_text(encoding="utf-8"))
    effective = module.load_authorized_config(AUTHORIZATION)  # type: ignore[attr-defined]
    assert base["formal_execution_authorized"] is False
    assert effective["formal_execution_authorized"] is True
    stripped = deepcopy(effective)
    stripped["formal_execution_authorized"] = False
    authorization = stripped.pop("authorization")
    assert stripped == base
    assert authorization["matrix_contract_override_allowed"] is False
    assert effective["episode_count"] == 54
    assert effective["metric_schema_version"] == "phase5-real-thor-metrics-v6"
    assert effective["panels"][1]["runtime_set"] == (
        "phase5-r2-frozen-runtime-set-v3"
    )


def test_v5_authorization_binds_readiness_revision_digest_and_72_metrics() -> None:
    auth = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    evidence = json.loads(READINESS.read_text(encoding="utf-8"))
    assert auth["readiness_code_revision"] == evidence["code_revision"]
    assert auth["readiness_manifest_digest"] == evidence["manifest_digest"]
    assert evidence["readiness_passed"] is True
    assert evidence["required_metric_count"] == 72
    assert evidence["prior_episode_reuse"] is False
    assert evidence["formal_execution_authorized_during_readiness"] is False


def test_v5_authorization_rejects_tampered_manifest_binding() -> None:
    module = _module()
    tampered = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    tampered["readiness_manifest_digest"] = "0" * 64
    with tempfile.TemporaryDirectory() as temporary_dir:
        path = Path(temporary_dir) / "tampered.json"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        try:
            module.load_authorized_config(path)  # type: ignore[attr-defined]
        except ValueError as exc:
            assert "does not authorize" in str(exc)
        else:
            raise AssertionError("tampered v5 readiness binding was accepted")


def test_v5_authorization_public_material_contains_no_private_runtime_data() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in (
        AUTHORIZATION, BASE, READINESS,
    ))
    for forbidden in (
        '"start_pose"', '"target_point"', '"anchor_id"', '"objectId"',
        "Book|", "Cup|", "CoffeeMachine|", "TeleportFull", "PlaceObjectAtPoint",
    ):
        assert forbidden not in text


def test_v5_launcher_has_fresh_output_and_clean_pushed_gates() -> None:
    source = (
        ROOT / "scripts" / "run_phase5_real_formal_execution_v5.py"
    ).read_text(encoding="utf-8")
    assert "if output_dir.exists():" in source
    assert "if dirty or head != upstream:" in source
    assert "implementation.execute_formal" in source
    assert "--execute" in source

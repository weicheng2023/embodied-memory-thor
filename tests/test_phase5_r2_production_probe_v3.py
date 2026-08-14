from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from embodied_memory_thor.phase5.frozen_r2_v2 import load_frozen_r2_runtime_v2


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r2_production_integration_probe_v3.json"


def _module() -> object:
    path = ROOT / "scripts" / "run_phase5_r2_production_probe_v3.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_probe_v3_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_v3_is_excluded_fixed_order_and_public_safe() -> None:
    module = _module()
    legacy = module._legacy()  # type: ignore[attr-defined]
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    module.validate_probe_config(config, legacy)  # type: ignore[attr-defined]
    assert config["runtime_set_version"] == "phase5-r2-frozen-runtime-set-v2"
    assert config["configuration_id"] == "FloorPlan6_R2_fixed_start_001"
    assert config["variants"] == ["no_memory", "short_memory_k2", "object_memory"]
    assert config["included_in_formal_aggregate"] is False
    assert config["episode_reuse_from_v2"] is False
    serialized = json.dumps(config, sort_keys=True)
    for forbidden in ('"x"', '"y"', '"z"', "objectId", "TeleportFull", "Cup|", "CoffeeMachine|"):
        assert forbidden not in serialized


def test_probe_v3_frozen_hashes_and_runtime_match() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for relative, expected in config["historical_artifacts_frozen"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    runtime = load_frozen_r2_runtime_v2(config["configuration_id"])
    public = runtime.configuration.public_reference()
    assert public["private_configuration_set_digest"] == config[
        "private_configuration_set_digest"
    ]
    assert runtime.subgoal_route.action_sequence_digest == config[
        "subgoal_route_action_sequence_digest"
    ]
    assert runtime.fallback_route.action_sequence_digest == config[
        "fallback_route_action_sequence_digest"
    ]


def test_probe_v3_patches_only_runtime_loader_and_config_validation() -> None:
    module = _module()
    legacy = module._legacy()  # type: ignore[attr-defined]
    original_runner = legacy.ThorEpisodeRunner
    original_audit = legacy._audit_episode
    legacy.load_frozen_r2_runtime = load_frozen_r2_runtime_v2
    assert legacy.load_frozen_r2_runtime is load_frozen_r2_runtime_v2
    assert legacy.ThorEpisodeRunner is original_runner
    assert legacy._audit_episode is original_audit

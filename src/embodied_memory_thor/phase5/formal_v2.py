"""Privacy-preserving public manifest for the real 54-cell Phase 5 pilot."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from embodied_memory_thor.phase5.protocol import (
    PHASE5_REQUIRED_METRICS,
    PHASE5_VARIANTS,
)
from embodied_memory_thor.phase5.search import load_frozen_search_route


REAL_MANIFEST_SCHEMA_VERSION = "phase5-real-thor-manifest-v2"
REAL_PROTOCOL_VERSION = "phase5-real-thor-pilot-v2"
REAL_METRIC_SCHEMA_VERSION = "phase5-real-thor-metrics-v3"
REAL_MANIFEST_SCHEMA_VERSION_V3 = "phase5-real-thor-manifest-v3"
REAL_PROTOCOL_VERSION_V3 = "phase5-real-thor-pilot-v3"
REAL_METRIC_SCHEMA_VERSION_V4 = "phase5-real-thor-metrics-v4"
REAL_MANIFEST_SCHEMA_VERSION_V4 = "phase5-real-thor-manifest-v4"
REAL_PROTOCOL_VERSION_V4 = "phase5-real-thor-pilot-v4"
REAL_METRIC_SCHEMA_VERSION_V5 = "phase5-real-thor-metrics-v5"
REAL_MANIFEST_SCHEMA_VERSION_V5 = "phase5-real-thor-manifest-v5"
REAL_PROTOCOL_VERSION_V5 = "phase5-real-thor-pilot-v5"
REAL_METRIC_SCHEMA_VERSION_V6 = "phase5-real-thor-metrics-v6"
REAL_PANEL_ORDER = ("r1_stable", "r2_stable", "r1_stale")
REAL_EPISODE_COUNT = 54
REAL_CONFIGURATION_COUNT_PER_PANEL = 6
REAL_MAX_STEPS = 2048
REAL_REQUIRED_METRICS = tuple(
    dict.fromkeys(
        PHASE5_REQUIRED_METRICS
        + (
            "stale_record_recovery_count",
            "intervention_count",
            "intervention_failure_count",
            "setup_completed",
            "setup_failure_reason",
            "shared_search_entry_recovery_policy",
            "shared_search_entry_recovery_action_limit",
            "shared_search_entry_departure_action_count",
            "shared_search_entry_recovery_action_count",
            "shared_search_entry_recovery_pending_action_count",
            "shared_search_entry_recovery_record_failure_count",
        )
    )
)
REAL_REQUIRED_METRICS_V4 = tuple(
    dict.fromkeys(
        REAL_REQUIRED_METRICS
        + (
            "book_distraction_policy",
            "shared_search_entry_alignment_policy",
            "shared_search_entry_alignment_action_limit",
        )
    )
)
REAL_REQUIRED_METRICS_V5 = tuple(
    dict.fromkeys(
        REAL_REQUIRED_METRICS_V4
        + (
            "invalid_planner_decision_count",
            "target_lock_policy",
            "target_lock_interaction_recovery_action_limit",
            "target_lock_interaction_recovery_retry_limit",
            "target_lock_canonical_pickup_horizon_degrees",
            "target_lock_interaction_recovery_action_count",
            "target_lock_interaction_recovery_attempt_count",
            "target_lock_terminal_failure_count",
        )
    )
)
REAL_REQUIRED_METRICS_V6 = tuple(
    dict.fromkeys(
        REAL_REQUIRED_METRICS_V5
        + (
            "shared_route_action_recovery_policy",
            "shared_route_action_recovery_attempt_limit",
            "shared_route_action_recovery_action_limit",
            "shared_route_action_recovery_attempt_count",
            "shared_route_action_recovery_action_count",
            "shared_route_action_recovered_failure_count",
            "shared_route_action_recovery_terminal_failure_count",
            "shared_route_action_recovery_pending_action_count",
        )
    )
)

_PUBLIC_FORBIDDEN_KEYS = {
    "anchor_id",
    "candidate_order",
    "destination_pose",
    "objectId",
    "private_registry",
    "reachable_positions",
    "start_pose",
    "support_id",
    "target_point",
}
_PUBLIC_FORBIDDEN_VALUES = (
    "Book|",
    "CoffeeMachine|",
    "Cup|",
    "PlaceObjectAtPoint",
    "TeleportFull",
)


class FormalManifestError(ValueError):
    """Raised when a formal precommit or manifest violates its boundary."""


def _contract_versions(config: Mapping[str, Any]) -> tuple[str, str, str]:
    protocol = str(config.get("protocol_version", ""))
    if protocol == REAL_PROTOCOL_VERSION:
        return (
            REAL_MANIFEST_SCHEMA_VERSION,
            REAL_PROTOCOL_VERSION,
            REAL_METRIC_SCHEMA_VERSION,
        )
    if protocol == REAL_PROTOCOL_VERSION_V3:
        return (
            REAL_MANIFEST_SCHEMA_VERSION_V3,
            REAL_PROTOCOL_VERSION_V3,
            REAL_METRIC_SCHEMA_VERSION_V4,
        )
    if protocol == REAL_PROTOCOL_VERSION_V4:
        return (
            REAL_MANIFEST_SCHEMA_VERSION_V4,
            REAL_PROTOCOL_VERSION_V4,
            REAL_METRIC_SCHEMA_VERSION_V5,
        )
    if protocol == REAL_PROTOCOL_VERSION_V5:
        return (
            REAL_MANIFEST_SCHEMA_VERSION_V5,
            REAL_PROTOCOL_VERSION_V5,
            REAL_METRIC_SCHEMA_VERSION_V6,
        )
    raise FormalManifestError("unsupported real formal protocol version")


def required_metrics_for(config: Mapping[str, Any]) -> tuple[str, ...]:
    metric_version = str(config.get("metric_schema_version", ""))
    if metric_version == REAL_METRIC_SCHEMA_VERSION_V6:
        return REAL_REQUIRED_METRICS_V6
    if metric_version == REAL_METRIC_SCHEMA_VERSION_V5:
        return REAL_REQUIRED_METRICS_V5
    if metric_version == REAL_METRIC_SCHEMA_VERSION_V4:
        return REAL_REQUIRED_METRICS_V4
    return REAL_REQUIRED_METRICS


def stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _walk_forbidden(value: Any, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            child = f"{path}.{key}" if path else key
            if key in _PUBLIC_FORBIDDEN_KEYS:
                violations.append(child)
            violations.extend(_walk_forbidden(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_walk_forbidden(item, f"{path}[{index}]"))
    return violations


def validate_precommit(
    config: Mapping[str, Any],
    *,
    root: str | Path,
    check_hashes: bool = True,
) -> None:
    errors: list[str] = []
    try:
        manifest_version, protocol_version, metric_version = _contract_versions(
            config
        )
    except FormalManifestError:
        manifest_version = protocol_version = metric_version = ""
        errors.append("protocol_version")
    expected_scalars = {
        "manifest_schema_version": manifest_version,
        "protocol_version": protocol_version,
        "metric_schema_version": metric_version,
        "episode_count": REAL_EPISODE_COUNT,
        "configuration_count_per_panel": REAL_CONFIGURATION_COUNT_PER_PANEL,
        "max_steps_per_episode": REAL_MAX_STEPS,
    }
    for key, expected in expected_scalars.items():
        if config.get(key) != expected:
            errors.append(key)
    if tuple(config.get("variants", ())) != PHASE5_VARIANTS:
        errors.append("variants")
    if config.get("readiness_only_authorized") is not True:
        errors.append("readiness_only_authorized")
    if protocol_version in {
        REAL_PROTOCOL_VERSION_V3,
        REAL_PROTOCOL_VERSION_V4,
        REAL_PROTOCOL_VERSION_V5,
    } and config.get(
        "book_distraction_policy"
    ) != "phase5-book-distraction-v4":
        errors.append("book_distraction_policy")
    if protocol_version in {REAL_PROTOCOL_VERSION_V4, REAL_PROTOCOL_VERSION_V5} and config.get(
        "target_lock_policy"
    ) != "phase5-shared-target-lock-v2":
        errors.append("target_lock_policy")
    if protocol_version == REAL_PROTOCOL_VERSION_V5 and config.get(
        "route_action_recovery_policy"
    ) != "phase5-shared-route-action-recovery-v1":
        errors.append("route_action_recovery_policy")

    output = config.get("output_policy", {})
    if not isinstance(output, Mapping):
        errors.append("output_policy")
    else:
        expected_output = {
            "mode": "formal",
            "save_frames": False,
            "trace_html": False,
            "visualize": False,
            "save_evaluator_debug": False,
            "included_in_formal_aggregate": True,
        }
        for key, expected in expected_output.items():
            if output.get(key) != expected:
                errors.append(f"output_policy:{key}")

    panels = config.get("panels", [])
    if not isinstance(panels, list) or len(panels) != len(REAL_PANEL_ORDER):
        errors.append("panels")
    else:
        if tuple(str(row.get("panel", "")) for row in panels) != REAL_PANEL_ORDER:
            errors.append("panel_order")
        for row in panels:
            ids = row.get("configuration_ids", []) if isinstance(row, Mapping) else []
            if (
                not isinstance(ids, list)
                or len(ids) != REAL_CONFIGURATION_COUNT_PER_PANEL
                or len(set(map(str, ids))) != REAL_CONFIGURATION_COUNT_PER_PANEL
            ):
                errors.append(f"panel_configuration_ids:{row.get('panel')}")
        if len(panels) == 3 and panels[0].get("configuration_ids") != panels[2].get(
            "configuration_ids"
        ):
            errors.append("r1_panels_not_matched")

    controller = config.get("controller_settings", {})
    if not isinstance(controller, Mapping) or stable_digest(controller) != stable_digest(
        {
            "width": 300,
            "height": 300,
            "quality": "Low",
            "gridSize": 0.25,
            "snapToGrid": True,
            "rotateStepDegrees": 90,
            "fieldOfView": 90,
            "renderDepthImage": False,
            "renderInstanceSegmentation": False,
        }
    ):
        errors.append("controller_settings")

    if _walk_forbidden(config):
        errors.append("public_precommit_private_keys")
    serialized = json.dumps(config, ensure_ascii=False, sort_keys=True)
    if any(token in serialized for token in _PUBLIC_FORBIDDEN_VALUES):
        errors.append("public_precommit_private_values")

    if check_hashes:
        project_root = Path(root)
        frozen = config.get("historical_artifacts_frozen", {})
        if not isinstance(frozen, Mapping) or not frozen:
            errors.append("historical_artifacts_frozen")
        else:
            for relative, expected in frozen.items():
                path = project_root / str(relative)
                if not path.is_file() or sha256_file(path) != str(expected):
                    errors.append(f"historical_artifact:{relative}")
    if errors:
        raise FormalManifestError("invalid formal precommit: " + ",".join(errors))


def collect_public_runtime_bindings(
    config: Mapping[str, Any], *, root: str | Path
) -> dict[str, dict[str, Any]]:
    """Resolve only public configuration and action-route material."""

    project_root = Path(root)
    r1_set = json.loads(
        (project_root / "configs" / "phase5_r1_frozen_anchor_set_v1.json")
        .read_text(encoding="utf-8")
    )
    r2_set_v2 = json.loads(
        (project_root / "configs" / "phase5_r2_frozen_runtime_v2.json")
        .read_text(encoding="utf-8")
    )
    r2_set_v3 = json.loads(
        (project_root / "configs" / "phase5_r2_frozen_runtime_v3.json")
        .read_text(encoding="utf-8")
    )
    r1_rows = {
        str(row["configuration_id"]): row
        for row in r1_set.get("scenes", [])
        if isinstance(row, Mapping)
    }
    r2_rows_v2 = {
        str(row["configuration_id"]): row
        for row in r2_set_v2.get("configurations", [])
        if isinstance(row, Mapping)
    }
    r2_rows_v3 = {
        str(row["configuration_id"]): row
        for row in r2_set_v3.get("configurations", [])
        if isinstance(row, Mapping)
    }
    bindings: dict[str, dict[str, Any]] = {}
    for panel in config["panels"]:
        runtime_set = str(panel["runtime_set"])
        for configuration_id in panel["configuration_ids"]:
            key = str(configuration_id)
            if key in bindings:
                continue
            if runtime_set == "phase5-r1-frozen-six-anchor-set-v1":
                if key not in r1_rows:
                    raise FormalManifestError(f"missing public R1 runtime: {key}")
                row = r1_rows[key]
                route = load_frozen_search_route(
                    str(row["search_route_id"]),
                    path=project_root / "configs" / "phase5_search_routes.json",
                )
                bindings[key] = {
                    "runtime_set": runtime_set,
                    "configuration_id": key,
                    "scene": str(row["scene"]),
                    "private_set_digest": str(r1_set["private_anchor_set_digest"]),
                    "search_route_id": route.route_id,
                    "search_route_action_sequence_digest": (
                        route.action_sequence_digest
                    ),
                }
            elif runtime_set == "phase5-r2-frozen-runtime-set-v2":
                if key not in r2_rows_v2:
                    raise FormalManifestError(f"missing public R2 runtime: {key}")
                row = r2_rows_v2[key]
                bindings[key] = {
                    "runtime_set": runtime_set,
                    "configuration_id": key,
                    "scene": str(row["scene"]),
                    "private_set_digest": str(
                        r2_set_v2["private_configuration_set_digest"]
                    ),
                    "subgoal_route_id": str(row["subgoal_route_id"]),
                    "subgoal_route_action_sequence_digest": str(
                        row["subgoal_route_action_sequence_digest"]
                    ),
                    "search_route_id": str(row["fallback_route_id"]),
                    "search_route_action_sequence_digest": str(
                        row["fallback_route_action_sequence_digest"]
                    ),
                }
            elif runtime_set == "phase5-r2-frozen-runtime-set-v3":
                if key not in r2_rows_v3:
                    raise FormalManifestError(f"missing public R2 runtime-v3: {key}")
                row = r2_rows_v3[key]
                bindings[key] = {
                    "runtime_set": runtime_set,
                    "configuration_id": key,
                    "scene": str(row["scene"]),
                    "private_set_digest": str(
                        r2_set_v3["private_configuration_set_digest"]
                    ),
                    "subgoal_route_id": str(row["subgoal_route_id"]),
                    "subgoal_route_action_sequence_digest": str(
                        row["subgoal_route_action_sequence_digest"]
                    ),
                    "search_route_id": str(row["fallback_route_id"]),
                    "search_route_action_sequence_digest": str(
                        row["fallback_route_action_sequence_digest"]
                    ),
                }
            else:
                raise FormalManifestError(f"unsupported runtime set: {runtime_set}")
    return bindings


def build_public_manifest(
    config: Mapping[str, Any],
    *,
    code_revision: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if len(code_revision) != 40:
        raise FormalManifestError("formal code revision must be a full Git SHA")
    episodes: list[dict[str, Any]] = []
    for panel in config["panels"]:
        for configuration_id in panel["configuration_ids"]:
            binding = bindings.get(str(configuration_id))
            if not isinstance(binding, Mapping):
                raise FormalManifestError(
                    f"missing public runtime binding: {configuration_id}"
                )
            if binding.get("runtime_set") != panel.get("runtime_set"):
                raise FormalManifestError(
                    f"runtime-set mismatch: {configuration_id}"
                )
            for variant in config["variants"]:
                episode = {
                    "episode_index": len(episodes) + 1,
                    "panel": str(panel["panel"]),
                    "task": str(panel["task"]),
                    "condition": str(panel["condition"]),
                    "runtime_set": str(panel["runtime_set"]),
                    "configuration_id": str(configuration_id),
                    "scene": str(binding["scene"]),
                    "memory": str(variant),
                    "planner": "deterministic",
                    "max_steps": int(config["max_steps_per_episode"]),
                    "metric_schema_version": str(config["metric_schema_version"]),
                    **deepcopy(dict(config["output_policy"])),
                    "search_route_id": str(binding["search_route_id"]),
                    "search_route_action_sequence_digest": str(
                        binding["search_route_action_sequence_digest"]
                    ),
                }
                episode["book_distraction_policy"] = (
                    str(config.get("book_distraction_policy"))
                    if str(episode["task"]) == "thor_book_reacquire_k2"
                    and config.get("book_distraction_policy") is not None
                    else "phase5-book-distraction-v1"
                )
                if config.get("protocol_version") in {
                    REAL_PROTOCOL_VERSION_V4,
                    REAL_PROTOCOL_VERSION_V5,
                }:
                    episode["target_lock_policy"] = str(
                        config["target_lock_policy"]
                    )
                if config.get("protocol_version") == REAL_PROTOCOL_VERSION_V5:
                    episode["route_action_recovery_policy"] = str(
                        config["route_action_recovery_policy"]
                    )
                if "subgoal_route_id" in binding:
                    episode["subgoal_route_id"] = str(binding["subgoal_route_id"])
                    episode["subgoal_route_action_sequence_digest"] = str(
                        binding["subgoal_route_action_sequence_digest"]
                    )
                episodes.append(episode)
    manifest = {
        "manifest_schema_version": str(config["manifest_schema_version"]),
        "protocol_version": str(config["protocol_version"]),
        "metric_schema_version": str(config["metric_schema_version"]),
        "code_revision": code_revision,
        "working_tree_dirty": False,
        "episode_count": len(episodes),
        "configuration_count_per_panel": REAL_CONFIGURATION_COUNT_PER_PANEL,
        "variants": list(PHASE5_VARIANTS),
        "panels": list(REAL_PANEL_ORDER),
        "execution_order": str(config["execution_order"]),
        "controller_settings": deepcopy(dict(config["controller_settings"])),
        "required_metrics": list(required_metrics_for(config)),
        "private_runtime_material_serialized": False,
        "episodes": episodes,
    }
    manifest["manifest_digest"] = stable_digest(manifest)
    validate_public_manifest(manifest)
    return manifest


def validate_public_manifest(manifest: Mapping[str, Any]) -> None:
    errors: list[str] = []
    try:
        manifest_version, protocol_version, metric_version = _contract_versions(
            manifest
        )
    except FormalManifestError:
        manifest_version = protocol_version = metric_version = ""
        errors.append("protocol_version")
    expected = {
        "manifest_schema_version": manifest_version,
        "protocol_version": protocol_version,
        "metric_schema_version": metric_version,
        "working_tree_dirty": False,
        "episode_count": REAL_EPISODE_COUNT,
        "configuration_count_per_panel": REAL_CONFIGURATION_COUNT_PER_PANEL,
        "private_runtime_material_serialized": False,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            errors.append(key)
    if tuple(manifest.get("variants", ())) != PHASE5_VARIANTS:
        errors.append("variants")
    if tuple(manifest.get("panels", ())) != REAL_PANEL_ORDER:
        errors.append("panels")
    if tuple(manifest.get("required_metrics", ())) != required_metrics_for(manifest):
        errors.append("required_metrics")
    episodes = manifest.get("episodes", [])
    if not isinstance(episodes, list) or len(episodes) != REAL_EPISODE_COUNT:
        errors.append("episodes")
    else:
        if [row.get("episode_index") for row in episodes] != list(
            range(1, REAL_EPISODE_COUNT + 1)
        ):
            errors.append("episode_indexes")
        for panel in REAL_PANEL_ORDER:
            rows = [row for row in episodes if row.get("panel") == panel]
            ids = {str(row.get("configuration_id", "")) for row in rows}
            if len(rows) != 18 or len(ids) != 6:
                errors.append(f"panel_matrix:{panel}")
            for configuration_id in ids:
                variants = [
                    row.get("memory")
                    for row in rows
                    if row.get("configuration_id") == configuration_id
                ]
                if tuple(variants) != PHASE5_VARIANTS:
                    errors.append(f"variant_order:{panel}:{configuration_id}")
        stable_ids = {
            row["configuration_id"]
            for row in episodes
            if row.get("panel") == "r1_stable"
        }
        stale_ids = {
            row["configuration_id"]
            for row in episodes
            if row.get("panel") == "r1_stale"
        }
        if stable_ids != stale_ids:
            errors.append("r1_match")
    digest_payload = deepcopy(dict(manifest))
    digest = str(digest_payload.pop("manifest_digest", ""))
    if stable_digest(digest_payload) != digest:
        errors.append("manifest_digest")
    forbidden_paths = _walk_forbidden(manifest)
    if forbidden_paths:
        errors.append("private_keys:" + "|".join(forbidden_paths[:3]))
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    if any(token in serialized for token in _PUBLIC_FORBIDDEN_VALUES):
        errors.append("private_values")
    if errors:
        raise FormalManifestError("invalid public formal manifest: " + ",".join(errors))


def compact_result_row(
    *,
    episode: Mapping[str, Any],
    summary: Mapping[str, Any],
    integrity_errors: Sequence[str],
) -> dict[str, Any]:
    """Keep a coordinate-free formal progress row for later aggregation."""

    return {
        "episode_index": int(episode["episode_index"]),
        "panel": str(episode["panel"]),
        "configuration_id": str(episode["configuration_id"]),
        "memory": str(episode["memory"]),
        "book_distraction_policy": summary.get("book_distraction_policy"),
        "success": summary.get("success"),
        "steps": summary.get("steps"),
        "target_reacquisition_action_count": summary.get(
            "target_reacquisition_action_count"
        ),
        "translation_action_count": summary.get("translation_action_count"),
        "translation_distance_meters": summary.get(
            "translation_distance_meters"
        ),
        "search_rotation_count": summary.get("search_rotation_count"),
        "repeated_viewpoint_visit_count": summary.get(
            "repeated_viewpoint_visit_count"
        ),
        "memory_guided_action_count": summary.get("memory_guided_action_count"),
        "invalid_action_count": summary.get("invalid_action_count"),
        "invalid_planner_decision_count": summary.get(
            "invalid_planner_decision_count"
        ),
        "target_lock_policy": summary.get("target_lock_policy"),
        "target_lock_interaction_recovery_action_count": summary.get(
            "target_lock_interaction_recovery_action_count"
        ),
        "target_lock_interaction_recovery_attempt_count": summary.get(
            "target_lock_interaction_recovery_attempt_count"
        ),
        "target_lock_terminal_failure_count": summary.get(
            "target_lock_terminal_failure_count"
        ),
        "shared_search_entry_recovery_action_count": summary.get(
            "shared_search_entry_recovery_action_count"
        ),
        "shared_route_action_recovery_attempt_count": summary.get(
            "shared_route_action_recovery_attempt_count"
        ),
        "shared_route_action_recovery_action_count": summary.get(
            "shared_route_action_recovery_action_count"
        ),
        "shared_route_action_recovered_failure_count": summary.get(
            "shared_route_action_recovered_failure_count"
        ),
        "shared_route_action_recovery_terminal_failure_count": summary.get(
            "shared_route_action_recovery_terminal_failure_count"
        ),
        "shared_search_entry_alignment_policy": summary.get(
            "shared_search_entry_alignment_policy"
        ),
        "shared_search_entry_alignment_action_count": summary.get(
            "shared_search_alignment_action_count"
        ),
        "shared_search_coverage_action_count": summary.get(
            "shared_search_coverage_action_count"
        ),
        "short_memory_evicted_before_reacquisition": summary.get(
            "short_memory_evicted_before_reacquisition"
        ),
        "old_viewpoint_miss_count": summary.get("old_viewpoint_miss_count"),
        "stale_record_recovery_count": summary.get(
            "stale_record_recovery_count"
        ),
        "information_boundary_passed": summary.get(
            "information_boundary_passed"
        ),
        "integrity_errors": list(integrity_errors),
    }

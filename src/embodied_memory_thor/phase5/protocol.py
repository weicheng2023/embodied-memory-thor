"""Frozen Phase 5 pilot manifest and qualification contracts."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence


PHASE5_PROTOCOL_VERSION = "phase5-v1"
PHASE5_METRIC_SCHEMA_VERSION = "phase5-metrics-v2"
PHASE5_MANIFEST_SCHEMA_VERSION = "phase5-manifest-v1"
PHASE5_VARIANTS = ("no_memory", "short_memory_k2", "object_memory")
PHASE5_PANELS = ("r1_stable", "r2_stable", "r1_stale")
FORMAL_CONFIGURATION_COUNT = 6
FORMAL_EPISODE_COUNT = 54

PHASE5_REQUIRED_METRICS = (
    "success",
    "steps",
    "target_reacquisition_action_count",
    "translation_action_count",
    "translation_distance_meters",
    "search_rotation_count",
    "repeated_viewpoint_visit_count",
    "invalid_action_count",
    "failed_interaction_count",
    "failure_taxonomy",
    "memory_retrieval_count",
    "useful_memory_retrieval_count",
    "memory_guided_action_count",
    "shared_search_alignment_action_count",
    "shared_search_coverage_action_count",
    "shared_search_route_entry_mismatch_count",
    "shared_search_route_exhausted_count",
    "shared_search_action_failure_count",
    "target_visible_event_count",
    "target_lock_entered_count",
    "target_lock_pickup_attempt_count",
    "transient_visibility_loss_count",
    "local_recovery_action_count",
    "target_reacquired_after_loss_count",
    "picked_after_target_lock",
    "target_lock_failed_reason",
    "short_memory_evicted_before_reacquisition",
    "stale_memory_use_count",
    "old_viewpoint_miss_count",
    "fallback_action_count_after_stale_miss",
    "stale_rediscovery_step",
    "memory_correction_step",
    "information_boundary_passed",
    "total_planning_latency_seconds",
    "total_action_latency_seconds",
    "total_artifact_capture_latency_seconds",
    "total_episode_latency_seconds",
)


@dataclass(frozen=True)
class QualificationRecord:
    """One retained candidate result, including failed/skipped candidates."""

    task: str
    candidate_order: int
    configuration_id: str
    scene: str
    passed: bool
    start_pose: Mapping[str, Any]
    rejection_reasons: tuple[str, ...] = ()
    qualification_evidence: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.task not in {"r1", "r2"}:
            raise ValueError(f"unsupported qualification task: {self.task}")
        if self.candidate_order < 1:
            raise ValueError("candidate_order must be positive")
        if not self.configuration_id.strip() or not self.scene.strip():
            raise ValueError("configuration_id and scene must be non-empty")
        if not isinstance(self.start_pose, Mapping) or not self.start_pose:
            raise ValueError("start_pose must be a non-empty mapping")
        if self.passed and self.rejection_reasons:
            raise ValueError("passing records cannot contain rejection reasons")
        if not self.passed and not self.rejection_reasons:
            raise ValueError("failed records must retain at least one rejection reason")


def qualification_digest(records: Sequence[QualificationRecord]) -> str:
    canonical = json.dumps(
        [asdict(record) for record in records],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def select_first_passing(
    records: Iterable[QualificationRecord],
    *,
    task: str,
    count: int = FORMAL_CONFIGURATION_COUNT,
) -> tuple[QualificationRecord, ...]:
    """Select the first distinct passing candidates in declared ascending order."""

    if count <= 0:
        raise ValueError("count must be positive")
    materialized = tuple(records)
    if not materialized:
        raise ValueError(f"no qualification records supplied for {task}")
    for record in materialized:
        record.validate()
        if record.task != task:
            raise ValueError(f"mixed task record: expected {task}, got {record.task}")
    orders = [record.candidate_order for record in materialized]
    if orders != sorted(orders) or len(orders) != len(set(orders)):
        raise ValueError("qualification records must retain unique ascending candidate_order")

    selected: list[QualificationRecord] = []
    seen_ids: set[str] = set()
    seen_starts: set[str] = set()
    for record in materialized:
        if not record.passed:
            continue
        start_signature = json.dumps(
            {"scene": record.scene, "start_pose": record.start_pose},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        if record.configuration_id in seen_ids or start_signature in seen_starts:
            raise ValueError(
                f"passing candidate is not distinct: {record.configuration_id}"
            )
        seen_ids.add(record.configuration_id)
        seen_starts.add(start_signature)
        selected.append(record)
        if len(selected) == count:
            return tuple(selected)
    raise ValueError(f"{task} has only {len(selected)} distinct passing configurations; {count} required")


def build_formal_manifest(
    *,
    r1_records: Sequence[QualificationRecord],
    r2_records: Sequence[QualificationRecord],
    code_revision: str,
    working_tree_dirty: bool,
    controller_settings: Mapping[str, Any],
) -> dict[str, Any]:
    """Freeze the complete matched 54-episode matrix before outcomes exist."""

    if working_tree_dirty:
        raise ValueError("formal Phase 5 manifest requires a clean working tree")
    if not code_revision.strip() or code_revision == "unavailable":
        raise ValueError("formal Phase 5 manifest requires an available code revision")
    r1_selected = select_first_passing(r1_records, task="r1")
    r2_selected = select_first_passing(r2_records, task="r2")

    episodes: list[dict[str, Any]] = []
    panel_specs = (
        ("r1_stable", "thor_book_reacquire_k2", "stable", r1_selected),
        ("r2_stable", "thor_cup_after_coffee_subgoal", "stable", r2_selected),
        ("r1_stale", "thor_book_reacquire_k2", "stale_r1", r1_selected),
    )
    for panel, task_name, condition, configurations in panel_specs:
        for record in configurations:
            for variant in PHASE5_VARIANTS:
                episodes.append(
                    {
                        "episode_index": len(episodes) + 1,
                        "panel": panel,
                        "task": task_name,
                        "condition": condition,
                        "configuration_id": record.configuration_id,
                        "scene": record.scene,
                        "start_pose": deepcopy(dict(record.start_pose)),
                        "memory": variant,
                        "mode": "formal",
                        "save_frames": False,
                        "visualize": False,
                        "save_evaluator_debug": False,
                        "included_in_formal_aggregate": True,
                    }
                )

    manifest = {
        "manifest_schema_version": PHASE5_MANIFEST_SCHEMA_VERSION,
        "protocol_version": PHASE5_PROTOCOL_VERSION,
        "metric_schema_version": PHASE5_METRIC_SCHEMA_VERSION,
        "code_revision": code_revision,
        "working_tree_dirty": False,
        "controller_settings": deepcopy(dict(controller_settings)),
        "variants": list(PHASE5_VARIANTS),
        "panels": list(PHASE5_PANELS),
        "short_memory_capacity": 2,
        "qualification": {
            "selection_rule": "first_six_distinct_passing_in_declared_ascending_order",
            "r1_all_records_digest": qualification_digest(r1_records),
            "r2_all_records_digest": qualification_digest(r2_records),
            "r1_selected_ids": [record.configuration_id for record in r1_selected],
            "r2_selected_ids": [record.configuration_id for record in r2_selected],
        },
        "required_metrics": list(PHASE5_REQUIRED_METRICS),
        "episodes": episodes,
    }
    validate_formal_manifest(manifest)
    return manifest


def validate_formal_manifest(manifest: Mapping[str, Any]) -> None:
    errors: list[str] = []
    if manifest.get("manifest_schema_version") != PHASE5_MANIFEST_SCHEMA_VERSION:
        errors.append("manifest_schema_version")
    if manifest.get("protocol_version") != PHASE5_PROTOCOL_VERSION:
        errors.append("protocol_version")
    if manifest.get("working_tree_dirty") is not False:
        errors.append("working_tree_dirty")
    if tuple(manifest.get("variants", ())) != PHASE5_VARIANTS:
        errors.append("variants")
    if tuple(manifest.get("panels", ())) != PHASE5_PANELS:
        errors.append("panels")
    if tuple(manifest.get("required_metrics", ())) != PHASE5_REQUIRED_METRICS:
        errors.append("required_metrics")

    episodes = manifest.get("episodes", [])
    if not isinstance(episodes, list) or len(episodes) != FORMAL_EPISODE_COUNT:
        errors.append("episode_count")
    else:
        expected_indexes = list(range(1, FORMAL_EPISODE_COUNT + 1))
        if [episode.get("episode_index") for episode in episodes] != expected_indexes:
            errors.append("episode_indexes")
        for panel in PHASE5_PANELS:
            panel_rows = [row for row in episodes if row.get("panel") == panel]
            ids = {str(row.get("configuration_id", "")) for row in panel_rows}
            variants = {str(row.get("memory", "")) for row in panel_rows}
            if len(panel_rows) != 18 or len(ids) != 6 or variants != set(PHASE5_VARIANTS):
                errors.append(f"panel_matrix:{panel}")
            for configuration_id in ids:
                cell_variants = [
                    row.get("memory")
                    for row in panel_rows
                    if row.get("configuration_id") == configuration_id
                ]
                if sorted(cell_variants) != sorted(PHASE5_VARIANTS):
                    errors.append(f"unmatched_variants:{panel}:{configuration_id}")
        r1_stable_ids = {
            row["configuration_id"] for row in episodes if row.get("panel") == "r1_stable"
        }
        r1_stale_ids = {
            row["configuration_id"] for row in episodes if row.get("panel") == "r1_stale"
        }
        if r1_stable_ids != r1_stale_ids:
            errors.append("r1_stale_not_matched")
        for row in episodes:
            if (
                row.get("mode") != "formal"
                or row.get("save_frames") is not False
                or row.get("visualize") is not False
                or row.get("save_evaluator_debug") is not False
            ):
                errors.append(f"formal_output_policy:{row.get('episode_index')}")
                break
    if errors:
        raise ValueError("invalid Phase 5 formal manifest: " + ",".join(errors))

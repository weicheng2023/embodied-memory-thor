# Phase 7B Recent-Memory Horizon Protocol

## Research question

Phase 7B asks whether R1 reacquisition behavior changes when exact
recent-observation capacity crosses the target-retention horizon, and whether
structured persistent object memory shows behavior not explained solely by a
longer recent window.

This is a narrow mechanism study, not a new benchmark and not an extension of
the Phase-5 matrix. Object memory still differs from recent memory in
representation and retrieval, so the design does not claim complete causal
isolation of every memory property.

## Configuration set

The study reuses the six hash-bound Phase-7A R1-stable configurations and their
shared action-only routes: FloorPlan308 through FloorPlan313. These
configurations are no longer holdout outcomes; Phase 7B uses them as a fixed
paired mechanism panel. No Phase-7A episode row is reused.

The configuration source, evaluator-only registry, and route registry are
bound by SHA-256 in `configs/phase7/memory_horizon_manifest.json`. The planner
still cannot access target IDs, evaluator start poses, coordinates, reachable
graphs, or qualification details.

## Memory conditions

Each configuration runs all five conditions, in this order:

1. `no_memory`;
2. `recent_memory_k2`;
3. `recent_memory_k4`;
4. `recent_memory_k8`;
5. `object_memory`.

`RecentObservationMemory(k)` retains visible records from exactly the last K
planner-safe observations. K=2, K=4, and K=8 use the same provider class,
representation, retrieval logic, planner, task, route, recovery policy, action
space, and evaluator. Only K changes within this family.

The historical Phase-5 `short_memory_k2` constructor and label remain intact.
Before outcomes, fixture tests must show that the new K=2 provider matches its
historical observation, retrieval, ordering, eviction, and snapshot semantics.
The optional persistent-snapshot baseline is excluded to avoid adding another
representation and retrieval confound.

## Fresh execution and fixed budgets

All 6 configurations x 5 variants = 30 episodes run fresh from one clean,
pushed revision at annotated tag `phase7b-memory-horizon-matrix-v1`. The
maximum remains 2,048 actions. The preregistered success thresholds remain 18,
72, and 2,048 actions, matching Phase 7A and deriving from the accepted
formal-v5 R1 maximum rather than Phase-7B outcomes.

No images, GUI, optional AI planner, prior-episode reuse, or Phase-5 aggregate
inclusion is allowed.

## Retention checkpoint and metrics

The retention checkpoint is the first planner request after distraction whose
task stage is `reacquire_book` or `pickup_book`. After the episode, the runner
reads the already-written ordinary trace. The evaluator-known selected target
ID is used only to reduce the trace to the following public scalars and never
enters a planner request. The runner records only:

- whether the selected target Book record was present in retrieved planner
  memory;
- its last-seen step and age in evaluated actions;
- recent-memory capacity and retained observation count.

This post-hoc extraction cannot affect an action. Public evidence contains no
record ID, object ID, coordinate, observation payload, or reachable graph.

Retain eventual and budgeted success, total and reacquisition actions,
translation count/distance, search rotations, repeated viewpoints,
memory-guided actions, retrieval count, target-retention state, invalid and
failed interactions, recovery counts, and information-boundary status.

## Analysis

Analysis is descriptive and paired by configuration. Report each variant's
retention count and cost summaries, plus paired differences and
better/tie/worse counts for:

- K=2, K=4, K=8, and object memory versus no memory;
- object memory versus K=8.

The recent-memory capacity curve is interpreted only within the common recent
provider. Object-versus-K8 differences may motivate hypotheses about structured
persistence but do not isolate representation from retrieval. No significance
test or broad-generalization claim is preregistered for six configurations.

## Stop, retry, and invalidation rules

- One retry is allowed only for infrastructure failure before observation zero.
- Any failure after observation zero remains an outcome.
- No configuration-specific start, camera, route, target-lock, collision, or
  recovery repair is permitted after the first outcome.
- Planner leakage, provider/capacity mismatch, source or digest drift, missing
  retention checkpoints or required metrics, mixed revisions, or a general
  defect changing task semantics invalidates the full version.
- An invalidated version is retained; a successor is frozen and all 30 cells
  rerun. Favorable rows are never reused selectively.

## Freeze sequence

1. Commit and test this protocol, manifest, generalized provider, runner, and
   aggregator before outcomes.
2. Merge normally and create the annotated matrix tag.
3. Run the full 30-cell matrix once from the clean tagged revision.
4. Aggregate only a complete, integrity-valid matrix.
5. Publish evidence under the Phase-7 namespace without changing Phase-5
   canonical files.

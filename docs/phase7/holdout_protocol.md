# Phase 7A Untouched Holdout Protocol

## Purpose and interpretation

Phase 7A asks whether the existing three memory conditions retain useful
behavior on a deterministically selected holdout set without repair after
comparative outcomes are observed. It uses the R1 stable Book-reacquisition task
because Phase 5 found only a small conditional gain there and because the task
does not require stale relocation anchors.

"Untouched" has a precise, limited meaning here: no candidate in the ordered
pool has been used for a comparative memory-variant outcome, and no Phase-7
scene-specific repair is permitted after outcomes begin. The layouts are not
claimed to be wholly unseen. An earlier Phase-5 coordinate-free presence census
and route-construction prescreen touched this scene family; that prior contact is
disclosed in the candidate-pool file.

## Feasibility decision

The historical Phase-5 runner requires a per-scene action route. Reusing that
requirement unchanged would make a new scene depend on manual route engineering
and would not support the intended holdout interpretation. Phase 7A therefore
adds the smallest generic successor policy before outcomes:

- a deterministic evaluator-only start selector chooses the first pickupable
  Book and first normalized interactable pose satisfying fixed gates;
- a deterministic target-independent route builder consumes only reachable
  positions, the selected start pose, and fixed parameters;
- every memory variant receives the same action-only route, target-lock,
  recovery policy, action space, task, evaluator, and step limit;
- Book identity, start coordinates, reachable graphs, and candidate trial
  details never enter planner requests, memory records, or ordinary traces.

The generic policy may fail on a holdout scene. Such failure is evidence, not a
reason for scene-specific tuning.

## Candidate order and exclusions

The frozen candidate pool is `configs/phase7/holdout_candidate_pool.json`.
Candidates are processed in listed order. Formal-v5 scenes and earlier
Phase-5 R1 native/route qualification scenes are excluded. The target is the
first six distinct scenes passing the fixed eligibility filter. A rejection
does not change later ranking and is retained with a coordinate-free reason.

## Pre-outcome eligibility filter

Eligibility may use evaluator-only metadata but runs no memory variant and no
post-distraction reacquisition outcome. For each scene, using fresh resets where
stated:

1. select the lexicographically first pickupable Book by `objectId`;
2. request interactable poses and normalize/sort them by
   `(x, z, rotation, horizon, standing, y)`;
3. test at most the first 32 poses in that order;
4. require `TeleportFull`, initial visibility, and a native `PickupObject` probe
   to pass on a fresh-reset trial;
5. on another fresh reset, require the fixed Phase-5 distraction-v4 action
   template to leave Book out of view;
6. construct the generic route without target/object inputs and require at most
   1,984 route actions;
7. accept the first pose passing all gates, or reject the scene with the first
   fixed classification after all 32 poses fail.

Eligibility does not execute the constructed fallback route, rank scenes by
route length, inspect memory behavior, save images, or run comparative episodes.

## Generic route policy

Policy version: `phase7a-generic-budgeted-visual-fallback-v1`.

- grid size: 0.25 m;
- deterministic grid-bin size: 3 grid steps;
- one deterministic representative per occupied bin;
- representatives joined by deterministic shortest cardinal paths;
- at each viewpoint: four cardinal observations at horizon 0 degrees and four
  at +30 degrees;
- route action ceiling: 1,984, reserving 64 of the 2,048 episode actions for
  distraction, entry/recovery, target approach, and pickup;
- no line-of-sight completeness claim;
- no Book identity/position, outcome, memory, or variant input.

Construction-ineligible scenes are rejected before the matrix. A route/native
failure during an outcome episode remains a result and is not repaired.

## Variants and ordering

Each accepted configuration runs, in order:

1. `no_memory`;
2. `short_memory_k2`;
3. `object_memory`.

No K=4/K=8 condition is part of Phase 7A. All variants share the deterministic
planner and the same generic route and recovery mechanisms. The only intended
difference is the memory provider.

## Outcomes and fixed budgets

Retain eventual task success under the 2,048-action ceiling, total evaluated
actions, target-reacquisition actions, translation actions/distance, search
rotations, repeated viewpoints, recovery counts, invalid actions,
memory-guided actions, K=2 eviction, route execution status, and information-
boundary status.

Formal-v5 R1 stable had a maximum of 9 total actions across all variants. Before
viewing Phase-7 outcomes, Phase 7A defines:

- `success_at_18`: success within `2 x 9` actions;
- `success_at_72`: success within `8 x 9` actions;
- eventual success: success within 2,048 actions.

These thresholds are deterministic multiples of the accepted Phase-5 maximum,
not chosen from holdout performance.

Analysis is descriptive and paired by accepted configuration: values and
object-minus-no-memory differences, plus better/tie/worse counts. Six
configurations do not justify broad generalization or significance claims.

## Retry, stop, and repair rules

- A launch/infrastructure failure before an episode obtains observation zero may
  receive one fresh-reset retry; both attempts are logged.
- A failure after observation zero is an outcome, not a retry opportunity.
- Missing metrics, information leakage, variant capability mismatch, source or
  digest drift, or a general defect that changes task semantics invalidates the
  full matrix version.
- After the first comparative outcome, no scene-specific start, camera, route,
  collision, target-approach, or recovery change is permitted.
- If a genuine general defect invalidates the matrix, retain it, freeze a new
  version, and rerun every cell from the beginning.

## Freeze sequence

1. Commit and tag the candidate pool, generic policy, runner, metrics, tests, and
   this protocol before eligibility.
2. Run only the fixed eligibility filter and retain the first six passes.
3. Commit the exact selected starts, action-only routes, rejected reasons,
   digests, and final matrix manifest; tag that matrix before outcomes.
4. Run the complete 18-cell matrix from the tagged clean revision.
5. Publish new evidence under `docs/evidence/phase7/` and results under
   `docs/phase7/`; do not edit Phase-5 result files.

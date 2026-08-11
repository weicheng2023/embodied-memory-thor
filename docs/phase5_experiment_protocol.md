# Phase 5 Real AI2-THOR Memory Comparison Protocol

Status: protocol v1 frozen before comparison runs. Phase 5A1 implementation has
started with offline-only memory-provider and parity tests; no Phase 5 episode or
comparison has run.

Implementation checkpoint: the runner now accepts `no_memory`, exact
`short_memory_k2`, and `object_memory`. The K=2 provider retains only the latest
two planner-safe observation snapshots, uses the same visible-derived record
schema as object memory, and falls back through the same planner path when the
target record is evicted. This checkpoint is infrastructure only. The separate R1
candidate `thor_book_reacquire_k2` now uses the frozen shared sequence
`RotateRight -> LookDown -> LookUp`; offline traces prove continuous hiddenness,
observation-0 K=2 eviction, and common no/short fallback. Real scene qualification
must still verify these properties before a three-variant dry run.

## Research question

In matched partially observable AI2-THOR tasks, does persistent visible-history
object memory reduce target reacquisition effort relative to a capable no-memory
search policy and exact-K short-term memory?

The deterministic metadata planner is the reference. The comparison isolates
memory access; it is not a test of pixel perception, LLM quality, privileged
navigation, or physical robotics.

## Evidence boundary

The formal pilot may provide E3 repeated real-simulator evidence only for its
tested tasks and configurations. With six matched configurations, results remain
descriptive: report paired differences, means, medians, ranges, and counts of
improvements/ties/regressions without claiming statistical significance or broad
generalization.

## Execution gates

### 5A — implementation and qualification

- Put no memory, exact `K=2` short memory, and persistent object memory behind one
  shared planner/task/search policy.
- Add the second task, stale intervention, metrics, aggregation, and audits.
- Qualify candidate kitchen scenes in ascending order using an evaluator-only
  availability/solvability route, retaining every skipped scene and reason.
- Freeze the first six distinct passing configurations before variant results.

Scene qualification is setup QA, not a memory comparison. Full metadata may
establish availability and fixed setup poses but never enters planner input.

### 5B — one engineering dry run

Run one qualified configuration under all three variants. Inspect fairness,
fallback behavior, provenance, metrics, and leakage. Exclude this run from formal
aggregates and stop if variants differ by anything except memory access.

### 5C — formal matrix

Run the complete manifest from one clean Git revision. A validity correction
requires a new protocol version and complete matched rerun; never selectively
rerun unfavorable episodes.

## Tasks and conditions

The R1 implementation name is `thor_book_reacquire_k2`. The accepted one-turn
Phase 4 `thor_book_reacquire` remains unchanged and is not a comparison task.

### R1 stable — Book reacquisition

Setup establishes a visible pickupable Book as `observation:0`. At least three
declared intermediate transitions hide Book and evict it from K=2 memory. The
evaluated goal is visible reacquisition and `PickupObject`.

### R2 stable — ordered Cup/CoffeeMachine task

Offline implementation checkpoint: `thor_cup_after_coffee_subgoal` now has an
ordered progress audit, shared observation-only CoffeeMachine search/toggle path,
Cup retrieval/fallback path, exact-K eviction test, and explicit failure when no
qualified visible Cup start is supplied. Real scene/start qualification remains
mandatory before the engineering dry run.

Setup establishes a visible pickupable Cup. The agent must reach and toggle a
CoffeeMachine while Cup is out of view, then reacquire and pick up Cup. The
provisional object pair must pass six-configuration qualification; any replacement
uses a documented availability rule before comparisons, never observed outcomes.

### R1 stale — hidden Book relocation

After Book leaves view and before retrieval reaches the planner, an evaluator-only
supported simulator action moves it to a frozen valid point. The intervention is
matched across variants, separately logged, outside the planner action space, and
never included in planner input or memory update. Object memory must be able to
visit the old viewpoint, detect a miss, use shared fallback, rediscover Book, and
correct its record from a new visible observation.

## Fair variants

Every ordinary variant receives the same current visible observation, task state,
inventory, action schemas, deterministic planner, systematic fallback, controller
settings, setup, intervention, evaluator, limits, and metrics.

- `no_memory`: no historical observations, visible sets, object locations, or
  memory records; it retains only shared task/control state and performs the full
  frozen systematic search.
- `short_memory_k2`: exactly the last two completed post-action planner-safe
  observations/outcomes; absent retrieval falls back identically to no memory.
- `object_memory`: persistent visible-only spatial records with object/camera pose,
  step, source observation, and stale status; absent/stale retrieval uses the same
  fallback.

Oracle/full-state navigation is separate solvability QA and excluded from ordinary
aggregates.

## Frozen pilot target

| Panel | Configurations | Variants | Episodes |
| --- | ---: | ---: | ---: |
| R1 stable | 6 | 3 | 18 |
| R2 stable | 6 | 3 | 18 |
| R1 stale | 6 | 3 | 18 |
| Total | — | — | 54 |

The configurations must be genuinely different scene/start situations. Repeating
one deterministic reset is not independent evidence.

## Metrics

Primary outcomes:

- success and evaluated action steps;
- actions from first hidden milestone to visible target rediscovery;
- translation actions/distance, search rotations, and repeated viewpoint visits.

Integrity and memory outcomes:

- invalid/failed actions and failure taxonomy;
- information-boundary, memory-provenance, ordered-subgoal, and intervention audits;
- retrieval/useful-retrieval and memory-guided action counts;
- K=2 eviction, stale use, old-viewpoint miss, fallback, rediscovery, and correction.

Performance separates planner, simulator action, setup, artifact, and total episode
latency. Setup is never included in evaluated steps or path metrics.

## Image and information rules

Desktop/window screenshots are prohibited. Formal runs use `save_frames=false`,
`visualize=false`, and evaluator-debug off. Lightweight shape/hash/brightness
statistics may inspect the simulator's in-memory RGB array only as rendering QA;
RGB remains outside the metadata planner.

Planner traces must contain no hidden objects, full metadata, intervention
destination, reachable-position map, or evaluator goal detail. Full evaluator and
intervention records use separate labeled files.

## Stop rules

Stop the matrix if:

- hidden/evaluator state leaks into a planner or memory record;
- variants differ in non-memory capability;
- setup/intervention enters planner metrics;
- a task fails solvability QA;
- K semantics or fallback differ between variants;
- stale relocation leaks or asymmetrically simplifies the task;
- code/manifest changes mid-run;
- outputs are missing, unparsable, or unmatched.

Retain invalidated artifacts and reasons. Increment the protocol and rerun every
matched episode after a validity correction.

## Gate before formal comparisons

Formal Phase 5 results require:

- accepted deterministic Phase 4 evidence;
- two tasks and three variants passing unit/parity tests;
- inspected capable no-memory search;
- offline stale miss/recovery acceptance;
- completed scene qualification with the frozen first-six rule;
- inspected one-configuration three-variant engineering dry run;
- a committed manifest on a clean revision.

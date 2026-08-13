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

Phase 5A4 offline checkpoint originally froze metric schema
`phase5-metrics-v1`; the shared target-lock checkpoint extends it as
`phase5-metrics-v2` and is now enforced
against runner summaries. Qualification records retain both passes and rejected
candidates in unique ascending order, and code selects exactly the first six
distinct passes. The manifest builder expands these into the matched 54-cell
matrix, binds one Git revision, disables formal visual/debug output, and refuses
a dirty worktree. These are protocol mechanisms, not completed real-scene
qualification or experiment evidence.

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

Offline implementation checkpoint: an injected evaluator-only intervention fires
after the frozen third distraction transition, logs only to a separate private
file, and cannot leak its native action/destination through planner `last_action`.
Visible-history viewpoint miss, `suspected_stale` exclusion, shared fallback,
rediscovery, and fresh-record correction pass offline. The real AI2-THOR 5.0.0
action and valid destination remain unqualified and unfrozen.

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

Machine-readable schema: `phase5-metrics-v2`. The formal manifest lists every
required summary key and validation fails if its matrix or output policy changes.

Primary outcomes:

- success and evaluated action steps;
- actions from first hidden milestone to visible target rediscovery;
- translation actions/distance, search rotations, and repeated viewpoint visits.

Integrity and memory outcomes:

- invalid/failed actions and failure taxonomy;
- information-boundary, memory-provenance, ordered-subgoal, and intervention audits;
- shared-route alignment/coverage actions, entry mismatch, exhaustion, and
  frozen-action failure;
- target-visible events, target-lock entries/pickup attempts, transient losses,
  bounded local-recovery actions, reacquisitions, post-lock pickup, and the
  terminal target-lock failure reason;
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

## Stale relocation qualification gate

The first real probe will use evaluator-only
`GetSpawnCoordinatesAboveReceptacle` followed by `PlaceObjectAtPoint`, as paired
by the official iTHOR interactive-physics API. The pure A4 probe contract checks:
query success and candidates; placement success; the same target surviving; a
material move; immediate and old-viewpoint hiddenness; and two stable samples.
The record is private and excluded from planner metrics. The API remains a
candidate until the installed AI2-THOR 5.0.0 default-agent runtime passes it.

Probe v1 qualification finding: after excluding the Book's original support,
`anywhere=false` produced no spawn coordinates across 42 distance-ranked
receptacles, so no placement occurred. Probe v2 therefore follows the documented
off-camera use case: it restricts candidates to declared open support types and
uses evaluator-only `anywhere=true`. It also retains every query result on the
failure path. The failed v1 artifact remains excluded from comparison evidence.

Probe v2 qualification finding: off-camera query succeeded on the first ranked
CounterTop and returned 441 coordinates, but the farthest-point rule chose an
edge coordinate whose Book-sized spawn volume intersected a Wall. Native
placement failed, the Book did not move, and reset reproducibility passed. Probe
v3 replaces only this flawed selector with a tested center-biased point at least
0.5 m from the old Book location. It does not use `forceAction` and retains v2 as
a failed qualification artifact.

Probe v3 qualification result: its center-biased point was not against a wall,
but a Pan on the CounterTop intersected the Book-sized spawn area. Native
placement again failed, the Book stayed at its old visible location, and scene
reset reproducibility passed. The API pair is therefore **not qualified** and the
formal stale panel remains blocked. Do not keep trying points online. The earlier
idea of one manually selected v4 point is superseded by the frozen multi-candidate
anchor qualification protocol below. `forceAction` remains prohibited.

## Pre-qualified relocation anchor protocol

The v1-v3 failures show that an API-returned coordinate is only a candidate, not
evidence that the Book can safely occupy it. Phase 5 therefore does not select or
query a destination during a formal stale episode. Before any comparison, an
evaluator-only qualification batch creates frozen **relocation anchors**.

### Frozen candidate and acceptance rule

For each declared R1 configuration, candidate surfaces and coordinates are
ordered deterministically before placement outcomes are known. Geometry using
the Book footprint, support bounds, and evaluator obstacle AABBs may reject
obviously unsafe candidates. The remaining candidates are tried with the actual
Book in that fixed order, resetting the scene before every trial. Every rejection
and native error is retained. The first anchor satisfying every gate is the
configuration's primary anchor; no agent outcome is observed when choosing it.

An anchor passes only if:

- `PlaceObjectAtPoint` succeeds without `forceAction` or a collision error;
- the same Book object ID still exists and moved by the frozen minimum distance;
- it is not visible from the frozen old viewpoint;
- its expected support relation is valid and its Book footprint does not overlap
  a non-support obstacle;
- it is not moving and its position remains within tolerance over three `Pass`
  samples;
- the frozen common observation-only fallback can rediscover and pick up it
  within the shared action limit;
- a reset restores the original configuration, and the anchor placement passes
  again from a fresh reset.

A scene/configuration with no passing candidate is rejected with all reasons. It
cannot enter the first-six pool. Qualification can test multiple candidates only
under this precommitted order; this is physical/solvability QA, not adaptive
retrying inside a formal episode.

### Frozen artifacts and information boundary

The private anchor registry binds `anchor_id`, scene/start configuration, exact
Book and receptacle IDs, xyz point, intervention milestone, qualification
protocol, AI2-THOR version, controller settings, trial evidence, and code
revision. It is evaluator-only. The ordinary formal manifest contains only the
opaque `anchor_id` and private-registry digest, never xyz coordinates. Coordinates
may appear only in the private qualification registry and `intervention.jsonl`.

Planner requests, memory records, ordinary `episode.jsonl`, action history, and
fallback state must contain neither the anchor coordinates nor query results.
The evaluator resolves the opaque ID and executes exactly one placement in each
formal stale episode. All three variants in a matched configuration use the same
anchor. If placement fails, the matched triplet stops and is invalidated; the
runner must not query a new point or switch to a reserve anchor.

This is a controlled intervention, not an attempt to make object memory look
better: anchors are selected only for physical validity, old-view hiddenness,
and common-policy solvability, before variant outcomes exist. Stable and stale
claims remain limited to the frozen qualified configurations.

### Anchor qualification implementation checkpoint

`phase5-anchor-qualification-v1` implements the private candidate plan, Book
footprint/support-bound/obstacle-AABB filter, deterministic first-pass rule,
three-sample stability audit, reset replay, private registry digest, and ordinary
coordinate-free summary. It also builds a deterministic DFS grid-coverage route
from reachable positions without receiving a target type, target ID, anchor ID,
support, or destination. This corrects the earlier weak fallback that only
rotated at one viewpoint.

The qualification script writes and hashes the complete candidate order before
the first native placement outcome, resets before every candidate, tests at most
the frozen first 12 geometry-safe candidates, and retains all failures. The
coverage audit permits at most 160 primitive actions and then uses the shared
visible-target approach/pickup policy. These are qualification constants, not
post-outcome choices.

Passing this script alone will not unblock the stale formal panel: the exact
qualified coverage route must subsequently be integrated into all three formal
variants and pass parity/leakage tests before the engineering dry run.

First frozen anchor-batch result (`5d163a6`, FloorPlan1): geometry retained 147
of 2,205 queried candidates. In the frozen first 12, three native placements
failed and nine passed placement, same-object, old-view hiddenness, support,
overlap, and stability gates. None was rediscovered within the v1 route's 160
action cap. The failure is retained; no anchor was frozen.

Route audit showed why: the complete DFS-with-scan route contained 1,091 actions,
so its frozen cap covered only an early prefix. Batch v2 replaces it before the
next run with target-independent 0.75 m spaced scan waypoints connected by
deterministic shortest grid paths. It rejects the entire plan before placement
if the complete route exceeds the new frozen 240-action cap. No target, support,
candidate, placement outcome, or anchor coordinate participates in route
construction.

Second frozen anchor-batch result (`d2fd052`): route v2 contained 210 actions,
19 target-independent scan waypoints, and nominally covered all 162 reachable
nodes within 0.75 m. All nine physically valid candidates were rediscovered at
search action 20. They then failed pickup because the shared visible-target
policy demanded 1-degree alignment despite 90-degree rotations: it overshot a
Book near the camera edge, lost visibility, and the qualification audit kept an
obsolete `pickup_book` stage. No anchor was frozen.

Batch v3 corrects these shared-capability defects without anchor input. A visible
distant target within the camera half-FOV (45 degrees) is approached directly
instead of receiving a guaranteed-overshoot 90-degree turn; the audit recomputes
`pickup_book` versus `reacquire_book` from each current visible observation. The
memory-navigation tolerance remains unchanged. The change is common to every
variant and passed the complete offline regression before another batch.

Third frozen anchor-batch result (`8165c87`): candidate 4 became
`FloorPlan1_R1_stale_Book_anchor_001`. Candidates 1-3 retained their native
placement failures. Candidate 4 passed native placement, same-Book identity,
minimum movement, old-view invisibility, expected support, zero non-support AABB
overlap, three stable samples, target-independent rediscovery at search action
20, pickup at action 22, fresh-reset placement replay, and reset restoration.
The coordinate-free summary passed a field audit.

The exact point is frozen only in the local, Git-ignored
`configs/evaluator_only/phase5_anchor_registry.json`; ordinary GitHub evidence
records the opaque ID and digests. The registry deliberately
sets `formal_use_allowed=false`: one anchor qualification does not complete the
six-configuration pool, and the exact 210-action route still requires formal
three-variant integration plus parity/leakage acceptance.

### Exact route integration checkpoint

The coordinate-free public route is now frozen as
`FloorPlan1_R1_fixed_start_001_coverage_v2` in
`configs/phase5_search_routes.json`. Its 210 primitive actions have action-only
digest `00f638bd2ae07bac41ad176fcd221ad94f0e2241440946ce34a0f894a4a51ba8`
and bind back to the retained qualification-route digest. The public artifact
contains only `MoveAhead`, `RotateLeft`, and `RotateRight` codes: no Book ID,
anchor ID, support, destination, world coordinate, or reachable-position list.

The runner exposes one action at a time through a strictly whitelisted
`shared_search` planner field. The deterministic planner must execute that exact
action, and any route action failure invalidates the episode instead of skipping,
replanning, or querying hidden state. Route progress and route-entry failures are
ordinary metrics. All evaluated actions, including route-entry alignment, remain
inside the episode step count.

The route was qualified from the planner-safe observation-0 agent pose. A shared
controller may retain only that agent pose as task/control state; it retains no
object observation or target position. A no/short-memory agent that is still at
the post-distraction heading performs the required fixed alignment action. An
object-memory agent that has already returned to observation 0 after a stale miss
can enter coverage directly. In both cases coverage starts at action index 0 from
the same pose, and the coverage action sequence is identical.

Offline acceptance executes the same route through `no_memory`, exact K=2, and
object memory under one matched stale fixture. All three used coverage indexes
0, 1, and 2 with identical actions before rediscovery; planner-input audits
passed, ordinary traces contained no intervention destination or anchor fields,
and a negative route-action test produced a hard failure. The Phase 5 related
suite passed 33/33 and the complete offline regression passed 93/93. These are software parity/leakage checks, not real-THOR
comparison evidence.

This clears the earlier route-integration blocker only. The local registry stays
`formal_use_allowed=false` because five more distinct R1 configurations, all R2
qualification, and the excluded real three-variant engineering dry run remain.
No formal stable or stale comparison has run.

### Kitchen-only first-six feasibility blocker

A metadata-only census on clean revision `4bd8261` inspected all 30 kitchen
scenes (`FloorPlan1`-`FloorPlan30`) before any further anchor trial. Every scene
reset successfully and returned reachable positions. All 30 contained at least
one pickupable Cup and one toggleable CoffeeMachine, so R2 has a sufficient
presence-level candidate pool. Presence is not full R2 qualification.

R1 failed the pool-size assumption: only `FloorPlan1` and `FloorPlan7` contained
a pickupable Book; the other 28 were rejected at object availability. Therefore
a kitchen-only R1 pool cannot yield six distinct scene configurations, even
before visibility, setup, relocation-anchor, fallback, or pickup gates. No
additional anchor placement was attempted after this finding.

The protocol must now make one pre-outcome choice before qualification resumes:
expand the ordered R1 pool to another declared scene family, or reduce/replace
the six-configuration design. Repeating unqualified starts or silently changing
the target is prohibited. The coordinate-free census record is retained in
`docs/evidence/phase5_kitchen_scene_census.json`.

### R1 scene-family decision and precommitted census order

R1 retains Book rather than choosing a kitchen object after observing the
kitchen census. Its versioned candidate pool is now declared in
`configs/phase5_r1_scene_pool.json`: living rooms `FloorPlan201`-`FloorPlan230`
in ascending order, followed by bedrooms `FloorPlan301`-`FloorPlan330` in
ascending order. The presence census must inspect all 60 candidates and preserve
that order. Later task qualification may freeze only the first six distinct
passing configurations under the existing first-six rule.

The census is evaluator-only setup QA. Its public record may retain scene-level
counts but no object IDs or coordinates. Passing requires a pickupable Book, at
least one declared open support, and at least one reachable position. It cannot
establish initial visibility, safe relocation, fallback coverage, pickup success,
or memory improvement. R2 remains in kitchens and is compared only within its
own matched panel; R1/R2 absolute task costs are not treated as a controlled
cross-scene comparison.

The clean census at revision `62e6831` completed all 60 resets without error.
Thirty-five scenes passed the presence gate (7 living rooms and 28 bedrooms), so
the expanded six-scene pool is feasible. The frozen first six presence candidates
are `FloorPlan201`, `FloorPlan202`, `FloorPlan203`, `FloorPlan209`,
`FloorPlan213`, and `FloorPlan224`. None exposes Book in the default reset view,
so presence does not qualify a start. The next gate uses evaluator-only
`GetInteractablePoses`, then requires native `TeleportFull`, visible Book, and
native `PickupObject` success under a predeclared deterministic pose order. Exact
poses and object IDs remain private.

Start qualification at clean revision `12978db` passed all six candidates. For
each scene, the first pose under the declared order passed native teleport,
current-view visibility, and native Book pickup. Exact poses are retained only
in the ignored evaluator registry; the public record contains counts and pose
digests.

The next target-independent route-length gate exposed a rejection before any
anchor placement. Under the already frozen 240-action maximum, only
`FloorPlan202` passed at 225 actions. The other five required 330, 630, 368,
369, and 386 actions respectively. Those scenes remain presence/start evidence
but cannot enter the fully qualified first six under the current fallback
contract. Qualification stopped without raising the cap, changing scan spacing,
or trying relocation anchors. The existing declared-order rule should next
screen later presence candidates for start and route eligibility, retaining all
rejections; changing the route contract would instead require a new protocol
version and fresh qualification.

The remaining-candidate prescreen is fixed before execution: inspect all 29
presence candidates after positions 1-6 in their existing declared order. Each
candidate uses the same maximum of 32 deterministically sorted interactable-pose
trials and the unchanged target-independent route-v2 builder with the unchanged
240-action limit. Start or route rejection is retained and the batch continues;
no anchor placement or agent episode is permitted during this prescreen.

The clean-revision batch at `a3da5aa` completed all 29 remaining candidates
without runtime error. All 29 passed the visible-and-pickupable start gate; 24
also fit the unchanged 240-action route limit. Together with the earlier
`FloorPlan202` pass, the declared pool contains 25 route-eligible candidates.
The first six route-eligible scenes in the original order are `FloorPlan202`,
`FloorPlan301`, `FloorPlan302`, `FloorPlan303`, `FloorPlan304`, and
`FloorPlan305`. They are the next anchor candidates, not yet fully qualified
configurations. The remaining-batch route rejections are FloorPlan229 (302),
FloorPlan309 (388), FloorPlan311 (311), FloorPlan323 (281), and FloorPlan325
(307); the earlier five route rejections also remain retained.

### FloorPlan202 anchor qualification exposes a fallback-capability blocker

Anchor qualifier v4 binds each scene to its private start pose via a public pose
digest, regenerates the target-independent route, and refuses to place Book if
the route digest or action count differs from the prescreen contract. The public
candidate contract contains no exact pose, object ID, support, or destination.
The generalized implementation passed 8/8 focused tests and 96/96 full offline
tests before the real trial.

The first frozen scene, FloorPlan202, then failed all first 12 anchor candidates
on clean revision `36720ae`. This was not a placement failure: all 12 passed
native placement, meaningful movement, old-view hiddenness, stability, support/
overlap checks, and reset restoration. Eight were never visually rediscovered
by the complete 225-action route. Four became visible at route action 197, but
one successful approach step lost visibility; the shared policy then performed
19 in-place rotations and never picked Book. No environment action failed.

Qualification stopped before FloorPlan301 and before any memory episode. The
result shows that target-independent geometric coverage and a 240-action bound
are insufficient qualification for a capable visual fallback. Trying later
anchors or scenes without correcting this common baseline would waste compute
and risk selection bias. Any correction must be target-independent at route
construction time, shared by all memory variants, versioned, tested offline, and
requalified from the first declared scene.

### Shared target-lock/local-recovery offline checkpoint

`phase5-shared-target-lock-v1` fixes only the second FloorPlan202 failure class:
a target that was visible during common fallback, followed by a local approach
that lost visibility. The original target-independent route remains unchanged.
When a pickupable Book or Cup appears in the current planner-safe observation,
the route pauses and the helper first issues `PickupObject` using only that
observation's visible object ID. A distance/angle-related failure permits at most
six bounded approach actions. If an ordinary action loses the visible target,
the helper attempts at most 12 ordinary local-recovery actions; a successful
`MoveAhead` is reversed with `MoveBack` first, followed by a bounded symmetric
look/rotation scan. Every recovery action is followed by a new safe observation,
and visible reacquisition returns immediately to pickup/approach.

The policy never consumes the anchor point, relocation destination, private
registry, complete metadata, or evaluator action. Its planner directive is
strictly whitelisted and cannot coexist with a `shared_search` directive. The
same helper, budgets, and ordinary action space apply to `no_memory`,
`short_memory_k2`, and `object_memory`; it is not a memory treatment. The
qualification script is versioned `phase5-anchor-batch-v5`, and coordinate-free
target-lock fields are aggregated into the `phase5-metrics-v2` summary:
`target_visible_event_count`, `target_lock_entered_count`,
`target_lock_pickup_attempt_count`, `transient_visibility_loss_count`,
`local_recovery_action_count`, `target_reacquired_after_loss_count`,
`picked_after_target_lock`, and `target_lock_failed_reason`.

Offline acceptance covers immediate pickup, distance-failure approach, loss and
`MoveBack` reacquisition, exhausted recovery, non-recoverable failure cooldown,
never-visible route parity, all-three-variant runner parity, ordinary-trace
leakage, coordinate-free aggregation, and preservation of the old FloorPlan202
evidence. Ten focused tests and all 106 repository tests pass, together with a
compile check. These fixtures are capability/parity evidence only.

No AI2-THOR process, memory comparison, new scene, anchor batch, or image was
started for this checkpoint. The optional FloorPlan202 candidate-4 diagnostic
was deliberately skipped because the batch qualifier cannot safely address only
candidate 4 without a broader selector change. The old 0/12 FloorPlan202 result
remains authoritative real evidence. A future bounded real diagnostic may test
whether transient recovery is repaired, but even success would not by itself
qualify an anchor or unlock the stale panel.

The authorized bounded follow-up added `--diagnostic-candidate-order` without
changing ordinary first-12 qualification behavior. On clean revision `e5c3533`,
exactly one real probe selected FloorPlan202 fixed-start candidate 4. It ran no
memory agent, saved no image, performed no fresh-reset replay, and prohibited
anchor freezing. Placement and reset restoration passed; the unchanged common
route exposed Book after action 197, and target lock immediately picked it up at
action 198 with no failed action. Consequently transient loss and local recovery
counts were both zero. The old candidate-4 failure path is removed by pickup
priority, but real-THOR evidence for the loss-recovery branch is still absent.
The coordinate-free record is
`docs/evidence/phase5_floorplan202_candidate4_target_lock_diagnostic.json`.

### Downward visual-coverage route v3 precommit

The remaining FloorPlan202 blocker is visual discovery, not target interaction.
The retained v2 route had 22 scan waypoints, 88 yaw rotations, and no look
action. Adding a full second horizon at every waypoint would exceed the frozen
240-action bound. V3 instead selects one target-independent relative 30-degree
downward adjustment: `LookDown` once before the unchanged route and `LookUp` once
after it. It does not inspect target type, candidate order, support, placement
outcome, anchor, or memory state.

The public FloorPlan202-only v3 contract fixes 227 actions and digest
`44aca36a89a7c8556a30a42a898d81105c7c47509059658e8952beabbe583a2a`.
The original six-scene v2 contract remains untouched. `LookDown` and `LookUp`
are added to the same strictly validated shared-route channel available to all
future variants. Before any full requalification, the first real diagnostic is
fixed as candidate 1, the earliest candidate that v2 never saw. Passing that
diagnostic permits FloorPlan202 requalification from the frozen beginning;
failure stops route-v3 work for analysis. This is a protocol decision, not a
result.

The candidate-1 diagnostic passed on clean `6a83736`: discovery at action 26,
pickup at 27, and zero failed actions. The ensuing full FloorPlan202 run selected
candidate 1 after physical QA, fallback pickup, fresh-reset replay, and reset
restoration all passed. The public coordinate-free result is
`docs/evidence/phase5_floorplan202_downward_route_v3_anchor_qualification.json`.
No memory agent or image was used.

Do not propagate v3 to FloorPlan301-305. Its single `LookDown` is a relative
camera action; frozen starts use different initial horizons. Thus identical v3
codes would not create an identical absolute scan layer across configurations
and may fail at a camera limit. This cross-scene protocol issue was found before
any later placement trial. A successor must compute a bounded alignment from the
planner-safe initial `cameraHorizon` to one predeclared absolute horizon, use no
target/anchor input, restore the initial horizon on route exhaustion, and pass
the same action-only parity/leakage contract. If one route policy is required
across the first six, qualification restarts from FloorPlan202 under that version.

### Absolute-horizon route v4 precommit

V4 declares one absolute scan horizon of `0` degrees. The route builder consumes
only the initial planner-safe `cameraHorizon`; it never receives a target,
candidate, support, anchor, placement outcome, or memory record. It converts the
initial horizon to ordinary 30-degree look actions, then restores it with the
exact inverse sequence after route exhaustion. Frozen starts at -30, 0, 30, and
60 degrees align with 1, 0, 1, and 2 actions. The maximum setup-plus-restoration
overhead is four, so even a 225-action base remains 229 under the unchanged 240
limit.

All memory variants use the same v4 route object and action-only shared-search
channel within a matched configuration. Offline tests audit action equality and
verify that planner requests contain no target point, anchor ID, candidate order,
private registry, or relocation destination. The FloorPlan202 v4 contract is
fixed at 227 actions with digest
`cb82c0057aa6d9a89d9493745c3ccc8db2047ebfae78e9fb65af022495777cae`.
Real order is fixed: candidate-1 diagnostic, full FloorPlan202 requalification,
then and only then FloorPlan301. No v4 real result exists at this checkpoint.
V4 offline acceptance is 30/30 focused and 113/113 complete.

The mandatory FloorPlan202 v4 replay has now passed on clean revision
`68c58b6`. Candidate 1 was discovered at action 26 and picked at action 27 with
zero failed ordinary actions. Full qualification then selected the same first
candidate after physical placement QA, shared fallback pickup, fresh-reset
replay, and reset restoration all passed. The coordinate-free record is
`docs/evidence/phase5_floorplan202_absolute_route_v4_anchor_qualification.json`.

Before a later scene performs any placement, its v4 action sequence must be
precommitted by a route-only QA run. That run may use evaluator-only frozen start
and reachable positions to construct the target-independent route, but it runs
no placement and no memory agent. Its public summary exposes only digests,
counts, the absolute horizon, and pass/fail state; the exact route remains in an
ignored evaluator-only file. A coordinate-free contract derived from this run
must be committed from a clean revision before the scene's candidate-1 probe.

FloorPlan301 route-only QA passed on clean revision `2cbe010`: one alignment
action and one inverse restoration action produced a 108/240-action v4 route
with digest
`09e3d64b7adb1afe2df76c573211a60caad4435ab4e1f84433d1d168191cd30b`.
No placement, anchor selection, image, or memory agent ran. The coordinate-free
contract is now frozen before its candidate-1 diagnostic.

The FloorPlan301 candidate-1 diagnostic then stopped before placement on clean
revision `a350eed`. AI2-THOR successfully returned 882 Desk placement
coordinates, but the current conservative square-footprint filter rejected all
882 as crossing the support boundary, leaving no candidate 1. No placement,
fallback action, anchor, image, or memory agent ran. Route v4 remains passed;
the blocker is the geometry model, which uses the Book's longest horizontal
half-extent on both axes and therefore cannot represent a rotated rectangular
Book on this narrow support. Do not try another candidate or FloorPlan302 under
the current version. The coordinate-free stop record is
`docs/evidence/phase5_floorplan301_candidate1_geometry_stop.json`.

### Axis-aware rectangular footprint v2 precommit

The geometry successor is fixed as
`phase5-axis-aware-rectangular-footprint-v2`. It reads the target Book's current
world-axis AABB and preserves separate X and Z half-extents plus the unchanged
0.02 m margin. It does not search rotations, inspect native placement outcomes,
or choose an orientation that makes a candidate pass. `PlaceObjectAtPoint`
retains the current object orientation; the existing native placement,
collision, support-parent, stability, old-view hiddenness, fallback, replay, and
reset-restoration gates remain authoritative after this geometric prefilter.

Candidate ordering remains support rank, then geometry clearance, then XYZ, and
is still hashed before the first placement action. The geometry plan is
evaluator-only and never enters planner input or memory. Offline acceptance must
cover both orientations of a rectangular Book on a narrow support, stable
ordering, private-field exclusion, all prior route-v4 tests, and the complete
repository regression. Because this prefilter changes the admitted set and can
therefore change frozen candidate order, qualification and the private registry
advance to v2. The common sequence must restart at FloorPlan202 under v2; its
route-v4 contract is unchanged. Only after the new FloorPlan202 candidate-1
diagnostic and full qualification pass may FloorPlan301 restart from candidate
1. FloorPlan302 remains gated on the complete FloorPlan301 result.

On clean revision `a2b3629`, offline acceptance passed 15/15 focused geometry
tests and 115/115 complete repository tests. FloorPlan202 qualification v2 then
passed both candidate-1 diagnostic and full requalification; candidate 1
remained the first passing anchor, and native placement, fallback pickup,
fresh-reset replay, and reset restoration passed.

FloorPlan301 qualification v2 still produced zero admitted candidates. The
single Desk query succeeded with 882 coordinates, but all 882 crossed the
support boundary after applying the Book's preserved-orientation rectangular
footprint and frozen safety margin. Thus the square approximation was a real
model defect but not the whole FloorPlan301 blocker. No candidate trial,
placement, fallback action, anchor, image, or memory agent ran. Stop before
FloorPlan302. Continuing now requires an explicit pre-outcome protocol decision
about the admitted support set or safety margin, not another geometry retry.

### Read-only first-six support census precommit

The next gate is frozen as `phase5-r1-support-census-v1` over FloorPlan202 and
FloorPlan301-305. The predeclared, lexicographically ordered candidate types are
Bed, CoffeeTable, CounterTop, Desk, DiningTable, Dresser, Shelf, and SideTable.
This includes every previous open-support type plus Book-plausible bedroom and
living-room supports; it is declared before the census result.

The census may reset scenes, read evaluator metadata, call
`GetReachablePositions`, and call `GetSpawnCoordinatesAboveReceptacle` only to
count availability. It discards returned coordinates, verifies that exact
object-state digests remain unchanged across spawn queries, and isolates
expected `lastAction` changes by resetting before the next scene. It cannot
place or pick an object, execute fallback, freeze an anchor, run a memory agent,
invoke force action, or save an image.

The v3 policy candidate admits a predeclared semantic Book support only when it
appears as a receptacle and produces a positive read-only spawn query in at
least one inspected scene. Placement outcomes are not inputs, and the candidate
remains non-formal until the public census is reviewed. The 0.02 m margin and
route-v4 remain unchanged. No FloorPlan301 qualification follows automatically.

The single authorized real batch ran on clean revision `1db67c2` and stopped in
FloorPlan202. CoffeeTable returned 143 spawn coordinates; Shelf and SideTable
queries failed; the other declared types were absent in that scene. More
importantly, the exact evaluator object-state digest differed before and after
the spawn-query sequence. The batch therefore raised
`unexpected_state_mutation` and did not reset or inspect FloorPlan301-305.

These FloorPlan202-only counts are incomplete diagnostic evidence, not a valid
support-policy recommendation. The automatically listed CoffeeTable candidate
remains explicitly non-formal and must not be treated as an admitted v3 set.
No new census run, FloorPlan301 qualification, or FloorPlan302 work is permitted
without a revised, precommitted mutation-isolation protocol and new authority.
The coordinate-free failure record is
`docs/evidence/phase5_r1_support_census.json`; raw details remain ignored under
`outputs/phase5_r1_support_census_v1_1db67c2/`.

### FloorPlan202 mutation-isolation precommit

The follow-up is restricted to FloorPlan202 and four reset-isolated trials.
Every trial resets and executes five `Pass` actions before its first digest.
The natural-settling control executes five more `Pass` actions before its second
digest. The remaining trials query exactly one CoffeeTable, one Shelf, or one
SideTable respectively, record state immediately, and reset before continuing.
No other scene or receptacle type is allowed.

Two state views are frozen before execution. The strict digest covers exact
object identity, pose, parentage, `isMoving`, and logical flags. The logical
digest excludes pose and `isMoving`. Anonymous comparison metrics report object
counts, changed field categories, maximum position displacement, and maximum
rotation-component change. Position changes above 0.001 m, rotation-component
changes above 0.1 degrees, identity changes, parent changes, or logical flag
changes are material. Metadata ordering and `lastAction` are absent from both
digests.

Case A requires a materially stable baseline and at least one query-specific
material change. Case B covers natural settling or strict-only/sub-threshold
change with no query-specific material mutation. A failed query is recorded but
its immediate state effect remains measurable. Only `Pass` and
`GetSpawnCoordinatesAboveReceptacle` are permitted; no placement, pickup,
fallback, memory, image, force action, FloorPlan301, or later scene is allowed.

The clean `6f21829` probe supports Case B. The Pass-only baseline changed its
strict digest before any support query, while its logical digest remained
identical. It showed sub-millimetre position settling and `isMoving` changes.
The original comparator also exposed a representation bug: direct Euler
subtraction treated a crossing near 0/360 degrees as 359.9888 degrees. The
post-run comparator is corrected to circular angular distance and covered by an
offline regression; the original measured evidence is retained rather than
silently rewritten.

CoffeeTable query succeeded with 143 coordinates; Shelf and SideTable queries
failed. All three isolated attempts retained identical logical digests and had
no identity, parentage, or above-threshold pose change. Their maximum position
changes were 0.0000357, 0.0000333, and 0.0000542 m, respectively, and their
maximum rotation-component changes were below 0.027 degrees. Therefore no
query-specific substantive mutation was observed. The old census stop was
caused by a digest that was too sensitive to natural physics settling,
`isMoving`, and angular representation—not evidence that the query changed the
scene materially.

This result does not itself restart the census or authorize FloorPlan301. A
future census protocol should use logical digests plus circular, thresholded
pose comparisons and retain query failure categories. No other scene was
started in this probe.

### Support census v2 precommit

V2 retains the frozen FloorPlan202/301-305 scene order and the eight predeclared
support types. It settles every reset with five `Pass` actions. Reachability is
counted once per scene; every individual receptacle query then runs in its own
fresh reset, followed by immediate tolerant state comparison and another reset.
No query result can contaminate a later query.

The shared evaluator-only state audit uses logical digests, circular angular
distance, a 0.001 m position threshold, and a 0.1 degree rotation-component
threshold. Strict digest changes and `isMoving` transitions remain diagnostic
counts but do not fail the census. Identity, parentage, logical flags, or
above-threshold pose changes are material and stop the batch. Failed queries are
retained as error categories and simply cannot satisfy the positive-spawn gate.

The v3 candidate rule remains pre-outcome: a declared semantic Book support is
admitted only if it exists as a receptacle, has a positive reset-isolated spawn
query in at least one frozen scene, and produces zero material query mutations.
Placement outcomes, visibility, coordinates, and memory results are not policy
inputs. Margin and route-v4 remain unchanged. The policy stays non-formal until
the complete public census is recorded and separately frozen.

Pre-run acceptance passed 18/18 focused census/isolation/compatibility tests and
133/133 complete repository tests (executed in four result-safe batches). The
shared state-audit module, v2 config, v2 script, public privacy audit, old-v1
evidence compatibility, and all route-v4 tests passed. No simulator process was
started for this checkpoint.

### Support census v2 execution stop

The clean-revision v2 batch started FloorPlan202, FloorPlan301, and
FloorPlan302, then stopped before FloorPlan303-305. FloorPlan202 and
FloorPlan301 had no material mutation under the frozen tolerant comparator.
FloorPlan302 produced repeated 0.261-0.551 degree rotation-component changes,
above the predeclared 0.1 degree threshold, while logical identity, object
identity, and parentage remained unchanged and position changes stayed below
0.000104 m. Because no FloorPlan302 Pass-only control was precommitted, this
result cannot distinguish natural settling from query-specific mutation. The
census is incomplete and no support-policy-v3 recommendation exists.

Post-run review also found a protocol mismatch: census v2 called
`GetSpawnCoordinatesAboveReceptacle` with `anywhere=false`, whereas the existing
qualification path calls the same query with `anywhere=true`. This explains why
partial query availability cannot be compared directly with qualification and
prevents using the partial counts to revise the support set. It does not change
or reinterpret the retained simulator result.

No placement, pickup, fallback route, memory agent, or image ran. FloorPlan301
qualification cannot restart. The next gate is a separately precommitted
FloorPlan302 mutation-isolation probe, followed by a census revision whose query
parameter is explicitly aligned with qualification. Thresholds must not be
changed from this outcome alone. Public evidence is retained at
`docs/evidence/phase5_r1_support_census_v2.json`. The post-run evidence test
passed 6/6 and complete offline regression passed 134/134.

### FloorPlan302 matched-action mutation-isolation precommit

The successor isolation protocol is restricted to FloorPlan302. It first
verifies the previously observed receptacle census: one Bed, one Desk, five
Shelves, and two SideTables. It then runs three independently reset natural
controls and nine independently reset query trials. Every trial receives five
settling `Pass` actions followed by exactly one measured action: a sixth `Pass`
for a control or one `GetSpawnCoordinatesAboveReceptacle` call for a query.
Thus the pre/post comparison spans one simulator action in both groups.

Each of the nine receptacles is queried once in deterministic type/object order,
with a fresh reset before and after. Queries explicitly use `anywhere=true`,
matching `qualify_phase5_anchors.py`. The original 0.001 m and 0.1 degree
thresholds are unchanged. No coordinate enters public evidence.

Case A requires every natural control to remain materially stable and at least
one query to produce material change. Case B requires material natural-control
variation and every query to stay inside the anonymous maximum position,
rotation, logical, and identity envelope observed in the controls. A query that
exceeds a material control envelope yields a mixed/inconclusive result, not
query causality. If neither group changes materially, the result is no material
change. Ordinary failed queries remain measured trials.

The aligned census successor is frozen separately as
`phase5-r1-support-census-v3`: it preserves all six scenes, all eight support
types, five settling actions, one query per reset, comparator thresholds,
selection rule, 0.02 m margin, and route-v4. Its only behavioral protocol change
from v2 is explicit `anywhere=true`, aligned with qualification. Census v3 must
not run before the committed FloorPlan302 isolation result is reviewed.

This precommit authorizes no other scene, placement, pickup, fallback, memory
agent, image, or census run. Focused compile/tests passed 15/15 before complete
regression; complete offline regression then passed 143/143.

### FloorPlan302 mutation-isolation execution stop

The only authorized real probe ran on clean revision `b8a1b70`. All three
matched one-`Pass` controls were material under the frozen 0.1 degree threshold:
their maximum rotation-component changes were 0.469, 0.605, and 0.316 degrees.
The anonymous natural-control envelope therefore reached 0.605 degrees and
0.0001041 m. There were no identity, parentage, or logical-state changes.

All nine reset-isolated `anywhere=true` queries succeeded and were measured.
Eight stayed within the control envelope. Shelf ordinal 4 returned a positive
query and reached 0.712 degrees and 0.0001186 m, exceeding the three-control
envelope without identity or logical change. Under the precommitted rule this is
`mixed_material_variation_inconclusive`: neither Case A nor Case B is supported.
The difference is small relative to the observed natural spread, but the result
must not be relabelled after seeing it.

Census v3 did not run and is not authorized by this mixed result. No other
scene, placement, pickup, fallback, memory agent, image, or coordinate exposure
occurred. Thresholds remain unchanged. Further attribution would require a new
pre-outcome protocol with stronger replication or paired/randomized controls;
it is a new gate, not an automatic rerun. Public evidence is
`docs/evidence/phase5_floorplan302_support_mutation_isolation.json`. Post-run
evidence tests passed 8/8 and complete offline regression passed 144/144.

### FloorPlan302 Shelf-4 paired attribution precommit

The stronger control is a bounded post-hoc diagnostic of the only v1 envelope
exceedance, Shelf ordinal 4 in FloorPlan302. It cannot retroactively turn that
selected case into confirmatory task evidence. The design freezes 12 independent
pairs (24 total fresh-reset trials). Each trial has five settling `Pass` actions
and exactly one measured action. Within each pair there is one `anywhere=true`
Shelf-4 query and one `Pass` control; the order alternates query/pass and
pass/query, producing six pairs of each order. Every trial resets immediately.

The two continuous endpoints are the anonymous maximum rotation-component and
position deltas already used by the tolerant audit. Practical-effect margins
remain 0.1 degrees and 0.001 m. For each endpoint, analysis uses the 12 paired
query-minus-control differences and a one-sided 97.5% Student-t bound
(`df=11`, `t=2.200985`). This is Bonferroni-corrected across two endpoints for a
familywise alpha of 0.05. Median, minimum, maximum, and positive-difference
counts are reported as non-decision sensitivity diagnostics so a mean driven by
one extreme pair remains visible.

A query-specific material effect is supported only if query-only logical or
identity change occurs, or a corrected lower paired bound exceeds a frozen
practical margin. No material query effect is supported only if both corrected
upper bounds remain below their margins and there is no logical/identity
change. All other complete results remain inconclusive. Failed queries are
incomplete; control logical/identity changes block causal attribution.

The probe preserves the same scene, exact selected support ordinal,
`anywhere=true` qualification alignment, and action boundary. It authorizes no
census v3, other scene, placement, pickup, fallback, memory agent, image, or
coordinate exposure. Only after offline compile, statistical/order/privacy
tests, complete regression, and a clean pushed commit may the single real probe
run. Census v3 remains blocked regardless until the paired result is separately
reviewed. Pre-run focused acceptance passed 9/9 and complete offline regression
passed 153/153.

### FloorPlan302 Shelf-4 paired attribution result

The only authorized paired probe ran on clean revision `1e7f05b`. All 12
`anywhere=true` queries succeeded; 12 matched `Pass` controls also completed.
All 24 trials used fresh resets, one measured followup action, and the frozen
balanced six/six order. No identity or logical-state change occurred.

For maximum position delta, the paired query-minus-control mean was
0.00000433 m and the corrected one-sided upper bound was 0.00002130 m, well
below the frozen 0.001 m margin. Thus no material query effect is supported for
position. For rotation, the paired mean was 0.02636 degrees, median was exactly
0, and 5/12 differences were positive. Its corrected interval was
[-0.05334, 0.10606] degrees. The lower bound does not support a positive
material effect, but the upper bound exceeds the frozen 0.1 degree margin by
0.00606 degrees, so a below-margin conclusion is also not supported.

The frozen overall classification is therefore
`paired_attribution_inconclusive`. Post-hoc order diagnostics show mean rotation
differences of 0.00910 degrees for query/pass and 0.04362 degrees for pass/query;
these are non-decision diagnostics and do not change classification. The result
is consistent with noisy natural settling but does not prove that explanation.

Census v3 did not run and remains blocked. No other scene, placement, pickup,
fallback, memory agent, image, or coordinate exposure occurred. Do not append
samples to this observed fixed-N analysis. If further attribution is worth the
compute, the next gate must precommit an independent no-peeking replication
cohort and its combination/decision rule before execution. Public evidence is
`docs/evidence/phase5_floorplan302_shelf4_paired_attribution.json`. Post-run
focused evidence tests passed 10/10 and complete offline regression passed
154/154.

### Shelf-4 independent replication precommit

The next attribution gate is a new fixed-N cohort, not an extension or pooled
analysis of the observed 12 pairs. It remains a post-hoc diagnostic of the
previously selected FloorPlan302 Shelf ordinal 4 and cannot become formal task
selection evidence. The prior cohort is used only for sample-size planning;
its observations do not enter the replication mean, variance, interval, or
classification.

The independent cohort freezes 24 pairs (48 fresh-reset trials), with 12
query/pass and 12 pass/query pairs in alternating balanced order. Every trial
has five settling `Pass` actions and exactly one measured action. Queries remain
`anywhere=true` and qualification-aligned. All 48 trials complete in memory
before any private/public output or statistical result is written; interim
analysis, optional extension, and partial-cohort output are prohibited.

Endpoints, margins, multiplicity correction, and decision semantics are
unchanged. With 24 pairs, the corrected one-sided 97.5% t bound uses `df=23`
and `t=2.068657610419041`. The prior cohort's observed rotation difference SD
of 0.12543 degrees implies an anticipated half-width of 0.05297 degrees. If its
0.02636-degree mean repeated, the anticipated upper bound would be 0.07933
degrees. These are planning quantities only, not evidence in the new decision.

The replication alone can support a material effect, support both endpoints
below their practical margins, or remain inconclusive under the existing
logical/identity/failure rules. A below-margin replication makes census v3
eligible only for a separate committed review; the probe never launches it.
Any other result stops. No other scene, placement, pickup, fallback, memory
agent, image, force action, coordinate exposure, or census run is authorized.

Focused pre-run acceptance passed 7/7, including fixed-N independence,
sample-size recomputation, AB/BA balance, target/action scope, privacy, and a
failure-path assertion proving that an incomplete cohort writes no output.
Complete offline regression passed 161/161.

### Shelf-4 independent replication result and census-v3 review

The fixed-N independent cohort ran on clean revision `7736996`. All 24 pairs
(48 fresh-reset trials) completed before output; all 24 `anywhere=true` queries
succeeded. Order was balanced, each trial had one measured action, no interim
analysis/output occurred, and the prior 12 pairs were not pooled or used for
classification. No logical or identity change occurred.

Replication-only rotation means were 0.23785 degrees for query and 0.24466
degrees for control. The paired query-minus-control mean was -0.00681 degrees,
median 0, and only 1/24 differences was positive. Its corrected upper bound was
0.00232 degrees, below the 0.1-degree practical margin. Position's paired mean
was effectively zero and corrected upper bound was 0.00000000772 m, below the
0.001 m margin. The frozen classification is therefore
`no_material_query_effect_supported` for the independent diagnostic. This does
not remove the post-hoc Shelf-4 selection caveat or turn it into task evidence.

The result makes a census successor eligible for design review, but the current
census v3 cannot run. Its code still flags a query whenever one immediate pose
delta exceeds the absolute threshold, without a matched Pass adjustment. The
replication's control mean rotation delta alone was 0.24466 degrees, so v3 would
still confuse known natural settling with causal query mutation and likely
reproduce a false stop.

Census v3 was not run. No other scene, placement, pickup, fallback, memory
agent, image, force action, or coordinate exposure occurred. The next gate is a
precommitted census successor that compares query effects against matched
natural controls (or an equivalently justified causal separation) before any
multi-scene census. Public evidence is
`docs/evidence/phase5_floorplan302_shelf4_independent_replication.json`.
Post-run evidence tests passed 8/8 and complete offline regression passed
162/162.

### Paired-causal support census successor precommit

The blocked absolute-threshold census v3 is superseded by
`phase5-r1-support-census-paired-causal-v4`. The frozen scene sequence is the
six-scene set FloorPlan202 and FloorPlan301-FloorPlan305, not every numeric
scene between 202 and 305. The eight semantic support types and order remain
unchanged.

Every exact receptacle query is one matched pair: a fresh reset, five settling
`Pass` actions, and one qualification-aligned `anywhere=true` spawn query; plus
a separate fresh reset, the same settling actions, and one measured `Pass`.
Pair order alternates query/pass and pass/query within each scene. No trial
reuses another trial's state.

The decision ignores each trial's absolute pose change. It uses only positive
query-minus-matched-Pass excess, with unchanged 0.001 m position and 0.1 degree
rotation thresholds. Query-only identity or logical changes are causal
failures. A matched-Pass identity or logical change is a background-integrity
failure. Query API failure remains negative availability evidence unless it
also produces a causal state effect.

Only reset, `Pass`, `GetReachablePositions`, and
`GetSpawnCoordinatesAboveReceptacle` are in scope. Placement, pickup, fallback,
memory, images, force actions, coordinates in public evidence, and policy use
before a complete pass remain prohibited. A complete pass may produce only a
non-formal support-policy-v3 candidate; formal recommendation requires a
separate committed freeze before FloorPlan301 candidate 1. Successor-specific
offline tests passed 8/8, the adjacent focused regression passed 24/24, and the
complete offline regression passed 170/170.

### Paired-causal support census result and stop

The real successor ran on clean pushed revision `3b5e8d7` and stopped under its
frozen rule. FloorPlan202 completed 3/3 pairs and FloorPlan301 completed 9/9
pairs without a causal or control-integrity flag. FloorPlan302 completed only
3/9 expected pairs: Bed ordinal 1, Desk ordinal 1, then Shelf ordinal 1. The
Shelf pair was scene pair ordinal 3 in query-then-pass order.

The Shelf query succeeded and returned 441 coordinates, which were counted and
discarded. Its maximum rotation change was 0.261734 degrees while the matched
Pass control's was 0, giving 0.261734 degrees positive excess above the frozen
0.1-degree threshold. Position excess was 0.00005188 m, below 0.001 m. Neither
trial changed object identity or logical state, and the Pass control did not
fail its integrity gate.

The protocol classification is `causal_material_query_effect`, so the census is
incomplete and failed. This single pair is a stopping-rule exceedance, not a
replicated estimate of a stable query effect; natural stochastic variation
remains a plausible alternative explanation. FloorPlan303-305 were not
started. No support-policy candidate or formal policy is available, and
FloorPlan301 candidate 1 remains prohibited.

No placement, pickup, fallback, memory agent, image, or force action ran. Any
future investigation must be independently precommitted and replicated;
neither adding trials to this observed run nor relaxing its threshold is
allowed. Public evidence is
`docs/evidence/phase5_r1_support_census_paired_causal_v4.json`. Post-run focused
evidence tests passed 9/9 and the complete offline regression passed 171/171.

### Formal support policy v3 and qualification v3 precommit

The failed causal census is retained but is no longer the decision basis for
semantic support admission. Its valid conclusion is narrower: spawn-coordinate
queries cannot be treated as reliably read-only under the one-pair mutation
gate. It does not show that Shelf, or any other queried type, cannot physically
support a Book. Excluding Shelf after observing its stop would be post-outcome
selection, so no type is added or removed based on census v4.

Support policy v3 freezes the same eight types declared before that outcome:
Bed, CoffeeTable, CounterTop, Desk, DiningTable, Dresser, Shelf, and SideTable.
An instance is eligible for candidate generation only when fresh-reset metadata
marks it `receptacle=true`. This is semantic eligibility, not anchor acceptance.
Spawn-query success, mutation, coordinate count, and native placement outcomes
do not decide type admission.

Qualification v3 assigns spawn queries one evaluator-only role: generate
candidate coordinates before native QA. Every exact support query starts from
its own reset and frozen setup, uses `anywhere=true`, and executes exactly one
query. Its post-query state is never passed to another query, route planning,
geometry planning, or placement. After the final query, another clean reset and
setup provide the metadata used for route and geometry planning.

The unchanged axis-aware geometry v2 filter then freezes candidate order before
native outcomes. Each selected candidate must still pass native placement
without force, same-target/material-move, old-view invisibility, support,
overlap, three-sample stability, common target-independent fallback pickup,
fresh-reset placement replay, and reset restoration. The route remains
absolute-horizon v4 and the 0.02 m margin remains unchanged.

Formal stale episodes may use only a frozen opaque anchor; they never execute a
spawn query or receive support IDs, coordinates, candidate order, or query
results. Policy v3 is formal only for evaluator-side anchor qualification and
does not itself qualify any scene. Qualification and private registry versions
advance to v3; geometry stays v2. FloorPlan301 must restart at geometry
candidate 1 and stop on any failure before full qualification or later scenes.
The frozen machine-readable policy is
`configs/phase5_r1_support_policy_v3.json`. Focused offline acceptance passed
18/18 and the complete offline regression passed 174/174; no new simulator
outcome exists at this checkpoint.

### FloorPlan301 qualification-v3 launch-input stop

The first attempt on clean `1b9b8d3` stopped during local input validation. The
command supplied the earlier six-scene start-qualification registry, whose rows
cover the first kitchen presence cohort and do not include FloorPlan301. The
loader therefore found zero matching passing rows and raised before constructing
`ThorEnv`.

This is not a FloorPlan301 simulator or candidate result. No scene reset,
support query, candidate plan, placement, pickup, fallback, replay, memory
agent, image, or anchor occurred. Read-only inspection identified the already
retained remaining-candidate prescreen registry as the source whose FloorPlan301
start digest matches the public route contract. Per the stop-on-problem rule,
the command was not retried. The next gate remains the same diagnostic geometry
candidate 1 with the corrected retained input after explicit continuation.
Coordinate-free evidence is
`docs/evidence/phase5_floorplan301_support_policy_v3_launch_stop.json`. Focused
evidence tests passed 19/19 and the complete offline regression passed 175/175.

### FloorPlan301 support-policy-v3 geometry stop

The corrected diagnostic ran on clean revision `596e1c2` with the retained
FloorPlan301 start whose digest matches the public route contract. Qualification
v3 issued eight `anywhere=true` support queries, each behind its own reset and
setup: one Desk, one Dresser, and six Shelf instances. All eight queries
succeeded. They returned 882, 441, and 2,646 coordinates respectively, for
3,969 total; coordinates remain private and are represented publicly only by
type-level counts.

A final clean reset preceded route and geometry construction. Query state was
not reused. The unchanged axis-aware geometry-v2 filter rejected all 3,969
points as `book_footprint_crosses_support_boundary`: Desk 882, Dresser 441, and
Shelf 2,646. Therefore geometry candidate 1 did not exist. The diagnostic
selector stopped before any native candidate trial.

This shows that expanding semantic support eligibility and isolating query
state did not solve FloorPlan301 under the preserved Book orientation, AABB
footprint, and 0.02 m margin. It is a geometry feasibility stop, not a placement
or fallback failure. No placement, pickup, fallback, replay, memory agent,
image, anchor, full qualification, or later scene ran. Do not try another
candidate, loosen the margin, rotate the Book, or continue the batch without a
new precommitted protocol decision. Coordinate-free evidence is
`docs/evidence/phase5_floorplan301_support_policy_v3_geometry_stop.json`.
Focused evidence tests passed 20/20 and complete regression passed 176/176.

### Native-first anchor qualification v4 precommit

Scheme B is selected. The semantic support set remains policy v3 and is not
rerun through a spawn-query mutation census. Qualification v3 was still only a
partial implementation of B because its AABB boundary prediction could veto a
coordinate before the native simulator evaluated it. Qualification v4 removes
that veto while retaining the diagnostic calculation.

Each support query remains fresh-reset isolated and a final clean reset still
precedes route and candidate planning. Candidate hard exclusions are limited to
non-numeric coordinates, duplicates for the same support, and movement below
0.5 m. The unchanged axis-aware footprint, 0.02 m margin, signed edge clearance,
and predicted support-occupant overlaps become advisory pre-outcome ranking
features only. They cannot establish success or failure.

The complete order is frozen before native outcomes: predicted-clear first,
then fewer predicted overlaps, descending signed edge clearance, support rank,
and xyz. The normal qualifier runs the frozen first 12 candidates, retaining
every failure, until the first fully qualified anchor or exhaustion. Each trial
starts from reset/setup. Native placement without force, same-Book move,
old-view invisibility, stability, actual support relation, post-placement
overlap, common fallback pickup, fresh-reset replay, and reset restoration are
the sole acceptance gates.

Book rotation, margin changes, memory agents, images, later scenes, and dynamic
queries during formal episodes remain prohibited. Qualification/registry
advance to v4; the geometry diagnostic remains v2 and the new candidate policy
is `phase5-native-first-advisory-ranking-v1`. The executable contract is
`configs/phase5_r1_native_qualification_v4.json`. A clean pushed precommit is
required before the one FloorPlan301 native batch.
Focused native-first acceptance passed 22/22 and the complete offline regression
passed 178/178. No v4 simulator outcome exists at this checkpoint.

### FloorPlan301 native-first qualification-v4 result

The clean `548c7ce` batch completed its frozen 12-candidate prefix. All 3,969
numeric, materially moved coordinates remained native-eligible; advisory
diagnostics predicted zero clear points, 3,969 boundary crossings, and 1,890
support-occupant overlaps. The frozen order's first 12 all came from Shelf.

All 12 native `PlaceObjectAtPoint` calls ran from fresh reset/setup without
force or Book rotation. All failed with the same categorized simulator error:
the spawn area was blocked by a scene wall. The Book did not move, so physical
QA failed and fallback/replay were correctly skipped. Reset restoration passed
12/12. No anchor was frozen.

This exhausts v4 exactly as declared and cannot be extended with candidate 13.
It confirms that native outcome, not AABB prediction, is the acceptance
authority. It also exposes a coverage defect in the pre-outcome prefix: all 12
trials used Shelf, leaving Desk and Dresser untested. Any continuation must
precommit support-type-balanced sampling; it cannot hand-pick a favorable point
or reinterpret this failed cohort. No memory, image, later scene, or formal
episode ran. Public evidence is
`docs/evidence/phase5_floorplan301_native_qualification_v4.json`.
Result-focused tests passed 23/23 and the complete offline regression passed
179/179.

### Type-balanced native qualification-v5 precommit

Qualification v5 is a new engineering qualification cohort, not candidate 13
or an extension of v4. The failed v4 cohort is retained unchanged and cannot be
pooled with v5. Its only protocol-level lesson is that a globally ranked prefix
did not cover the present semantic support types; no candidate is selected or
discarded because of its v4 native outcome.

Candidate generation, hard exclusions, and advisory within-type ranking remain
v4. Before native trials, candidates are partitioned by semantic support type.
Present types are traversed round-robin in the predeclared policy-v3 order:
Bed, CoffeeTable, CounterTop, Desk, DiningTable, Dresser, Shelf, SideTable.
Within each type, the v4 advisory rank is preserved. FloorPlan301 has Desk,
Dresser, and Shelf coordinates, so a complete 12-candidate prefix allocates four
positions to each type.

The frozen prefix still stops at the first fully qualified anchor or at 12
failures. Every trial starts from reset/setup. No force action, Book rotation,
margin change, outcome-dependent reordering, memory agent, image, later scene,
or formal episode is authorized. Native placement and all existing physical,
fallback, replay, and restoration gates remain unchanged. The executable
contract is `configs/phase5_r1_native_qualification_v5.json`; qualification and
private registry advance to v5, candidate ranking to
`phase5-native-first-type-balanced-ranking-v2`, while support policy v3,
geometry diagnostic v2, and route v4 remain fixed. A clean tested pushed
precommit is required before the one FloorPlan301 v5 batch.
Focused v5 acceptance passed 25/25 and the complete offline regression passed
181/181. No v5 simulator outcome exists at this checkpoint.

### FloorPlan301 type-balanced qualification-v5 result

The clean `d3e8ca1` run exhausted the independent v5 prefix exactly as
precommitted. Candidate types followed Desk, Dresser, Shelf four times, so all
three support types present in the candidate plan received equal coverage.
Native placement passed 0/12: ten attempts were categorized as scene-wall
spawn-area blocks and two as existing-object spawn-area blocks. The Book did
not move materially in any trial.

Because physical placement failed, common fallback and fresh-reset replay were
correctly skipped for all candidates. Reset restoration passed 12/12. No
forceAction, Book rotation, memory agent, image, anchor, formal episode, or
later scene was used. This result removes the v4 Shelf-only coverage defect as
an explanation: FloorPlan301 remained infeasible across Desk, Dresser, and
Shelf under the frozen native API, orientation, and candidate rules.

The v5 cohort is closed and must not be extended or pooled with v4. Moving to
FloorPlan302 is not yet authorized because the current protocol serializes later
scenes behind FloorPlan301. A new pre-outcome scene-level rule must state when a
fully exhausted scene is recorded as failed and skipped in declared scene order.
Public coordinate-free evidence is
`docs/evidence/phase5_floorplan301_native_qualification_v5.json`.
Result-focused tests passed 26/26 and the complete offline regression passed
182/182.

### FloorPlan302 scene-successor qualification-v6 precommit

The scene-level rule is now explicit. A scene may be recorded as failed and
skipped only when its independently frozen, support-type-balanced 12-candidate
prefix completes without an anchor and with no fatal error, query failure,
route failure, or reset-restoration failure. Runtime and integrity failures stop
the sequence and cannot be treated as scene infeasibility. FloorPlan301 v5
satisfies the exhausted-failure condition, so the declared successor is
FloorPlan302; no later scene may be selected instead.

Qualification/registry advance to v6 solely to bind this scene transition.
Support policy v3, type-balanced candidate ranking v2, within-type ranking v1,
geometry diagnostic v2, route v4, the 12-trial limit, native acceptance gates,
fresh resets, privacy, and all action prohibitions remain unchanged. The
FloorPlan301 outcome does not influence FloorPlan302 candidate ordering.

Before any FloorPlan302 spawn query or placement, run route-only absolute
horizon v4 construction from its already retained private start. The public
route count and digest must be committed on a clean revision and then bound into
a scene-specific candidate contract. A route mismatch or action count above 240
stops. The executable transition contract is
`configs/phase5_r1_native_qualification_v6_floorplan302.json`.
Focused transition tests passed 27/27 and the complete offline regression
passed 183/183. No FloorPlan302 route, query, or placement has run yet.

### FloorPlan302 absolute-horizon route-v4 result

The route-only gate passed on clean `a9ce79f` with 61 actions under the 240
limit and absolute scan horizon 0 degrees. Its digest is
`8844fb4f2424b3b143ffcf2de8c58f249ab5ba35206289a0e11d4b60f1e9400a`.
The builder used reachable positions and the retained start, but no Book,
anchor, support, or candidate coordinate input. No support query, placement,
memory agent, or image ran.

The coordinate-free binding is
`configs/phase5_r1_anchor_candidates_absolute_v4_floorplan302.json` and public
evidence is
`docs/evidence/phase5_floorplan302_absolute_route_v4_precommit.json`. The next
gate is offline acceptance plus a clean pushed commit. Only then may the one
FloorPlan302 v6 qualification batch begin.
Route-contract tests passed 28/28 and the complete offline regression passed
184/184.

### FloorPlan302 native qualification-v6 result

The clean `90a1ec7` run rebuilt the exact 61-action route digest and then
qualified its first balanced candidate, a Bed candidate. Native placement moved
the same Book 2.007788 m, hid it from the old viewpoint, remained stable across
three Pass samples, produced the expected support relation, and produced no
non-support overlap. The shared target-independent fallback rediscovered the
Book at action 20 and picked it up at action 21; all 21 actions succeeded.

Fresh-reset placement replay and reset restoration both passed. The opaque
FloorPlan302 anchor was therefore frozen in the evaluator-only registry. No
memory agent, image, force action, Book rotation, formal episode, or later scene
ran. This proves one real THOR relocation anchor and capable common fallback;
it does not prove memory improvement. Public coordinate-free evidence is
`docs/evidence/phase5_floorplan302_native_qualification_v6.json`.
Result-focused tests passed 29/29 and the complete offline regression passed
185/185.

### FloorPlan303 qualification-v7 precommit

The audited sequence state is now two passing anchors, FloorPlan202 and
FloorPlan302, plus the cleanly exhausted FloorPlan301 failure. After either an
audited terminal pass or an integrity-clean exhausted failure, the protocol
advances exactly one route-eligible scene in declared order until six distinct
anchors qualify. Thus FloorPlan303 is the only next scene; the FloorPlan302
success does not select or rank its candidates.

Qualification/registry v7 bind the transition. All type-balanced candidate,
native placement, physical QA, common fallback, replay, restoration, privacy,
and action-boundary rules are unchanged. Before any support query or placement,
FloorPlan303 requires a clean coordinate-free absolute-horizon route-v4 result,
tested and pushed. This contract authorizes neither FloorPlan304 nor a memory
agent. Its executable definition is
`configs/phase5_r1_native_qualification_v7_floorplan303.json`.
Focused transition tests passed 30/30 and the complete offline regression
passed 186/186. No FloorPlan303 route, query, or placement has run yet.

### FloorPlan303 route-v4 floating-boundary stop

The clean `37b7b8f` route-only attempt stopped before a route was constructed.
The retained start requested camera horizon 60 degrees. After a successful
TeleportFull, AI2-THOR reported `60.00001525878906`, and route-v4's strict
`> 60.0` validation raised `initial camera horizon is outside the supported
range`. The excess is approximately 0.000015 degrees.

A reset/Teleport-only diagnostic reproduced the exact value without support
queries or placement. Therefore this is normal simulator floating-point drift
at a declared valid boundary, not a failed start or scene. No route, support
query, placement, memory agent, image, anchor, or later scene exists from this
attempt. FloorPlan303 and FloorPlan304 remain blocked. The next revision must
precommit a small bounded horizon normalization/tolerance, add the observed
real value to offline tests, and rerun route-only from the beginning. Public
evidence is
`docs/evidence/phase5_floorplan303_route_v4_float_boundary_stop.json`.
Stop-evidence tests passed 31/31 and the complete offline regression passed
187/187.

### Route-v4.1 bounded horizon-tolerance precommit

The fix is restricted to numerical normalization at the absolute-horizon route
builder boundary. A reported horizon may snap to its nearest 30-degree ordinary
action grid point only when the absolute deviation is at most 0.001 degrees.
The real FloorPlan303 value `60.00001525878906` therefore normalizes to 60.
Values 60.5 and 61 remain beyond tolerance/range and must fail. Supported range
and the bounded LookUp/LookDown action count do not change.

For exact-grid starts, route serialization remains byte-for-byte compatible:
FloorPlan202 retains digest
`cb82c0057aa6d9a89d9493745c3ccc8db2047ebfae78e9fb65af022495777cae`
and FloorPlan302 retains
`8844fb4f2424b3b143ffcf2de8c58f249ab5ba35206289a0e11d4b60f1e9400a`.
Only a route that actually applies normalization is labeled absolute-horizon
v4.1 and records the policy/tolerance. Route inputs remain reachable positions,
start pose, and fixed scan settings; planner requests receive only the existing
opaque action directive and never target, anchor, support, or coordinate data.

The executable policy is
`configs/phase5_route_v4_1_horizon_tolerance.json`. It requires focused tests,
full regression, clean commit, and push before restarting FloorPlan303
route-only. Native qualification remains blocked until that route-only gate
passes.
Focused route-v4.1 tests passed 34/34 and the complete offline regression
passed 190/190. The real FloorPlan303 route-only rerun has not started.

### FloorPlan303 route-v4.1 pass

The clean `acf6420` route-only rerun succeeded. The observed
`60.00001525878906` horizon normalized to 60 within the frozen 0.001-degree
tolerance. Two LookUp actions aligned to the 0-degree scan horizon, two
LookDown actions restored the start, and the complete route used 100 of 240
allowed actions. Its digest is
`5d4de455b78ab05f17038cb7b5cf4dbc63c736d4b0c0fdf40e733545319c4254`.

No target or anchor input, support query, placement, memory agent, or image was
used. Public evidence is
`docs/evidence/phase5_floorplan303_absolute_route_v4_1_precommit.json`; the
coordinate-free binding is
`configs/phase5_r1_anchor_candidates_absolute_v4_1_floorplan303.json`. Native
qualification v7 remains blocked until the new contract passes offline tests
and is committed and pushed.
Route-contract tests passed 35/35 and the complete offline regression passed
191/191.

### FloorPlan303 native qualification-v7 result

Only after the committed route-v4.1 pass, the clean `9a79fc6` native run began.
Its first balanced candidate, a Bed candidate, passed every gate. The same Book
moved 1.241027 m, became invisible from the old viewpoint, stayed stable for
three samples, established the expected support relation, and introduced no
non-support overlap. The common target-independent fallback rediscovered the
Book at action 68 and picked it up at action 69 with no failed action.

Fresh-reset placement replay and reset restoration passed, so one opaque
FloorPlan303 anchor was frozen. No memory agent, image, force action, Book
rotation, formal episode, or FloorPlan304 run occurred. R1 therefore has three
qualified scenes: FloorPlan202, FloorPlan302, and FloorPlan303; FloorPlan301
remains a retained clean failure. This is anchor/fallback evidence, not memory
improvement evidence. Public evidence is
`docs/evidence/phase5_floorplan303_native_qualification_v7.json`.
Result-focused tests passed 36/36 and the complete offline regression passed
192/192.

### FloorPlan304 qualification-v7 scene-transition precommit

The audited sequence now contains qualified anchors in FloorPlan202,
FloorPlan302, and FloorPlan303, with FloorPlan301 retained as a cleanly
exhausted failure. The unchanged scene-order rule therefore admits only
FloorPlan304 next; prior native outcomes do not select or rank its candidates.

FloorPlan304 reuses qualification/registry v7, the type-balanced 12-candidate
maximum, fresh-reset query isolation, native placement and physical QA, common
fallback, replay, restoration, privacy, and action prohibitions. Its first gate
is route-only QA under the already frozen absolute-horizon v4.1 policy. That run
may use reachable positions and the retained evaluator-only start pose, but no
support query, placement, target/anchor input, memory agent, or image. A passing
coordinate-free route digest/count must be tested, committed, and pushed before
exactly one native qualification-v7 batch may start. This transition authorizes
neither FloorPlan305 nor any memory variant. The executable contract is
`configs/phase5_r1_native_qualification_v7_floorplan304.json`.
Focused transition tests passed 37/37 and the complete offline regression
passed 193/193. No FloorPlan304 THOR process has been started.

### FloorPlan304 route-v4.1 pass

The clean `7495931` route-only run passed. Its observed start horizon was
30.000003814697266 degrees and normalized to 30 under the frozen 0.001-degree
tolerance. One LookUp action aligned the scan to 0 degrees and one LookDown
action restored the start horizon. The complete route used 127 of 240 actions;
its digest is
`6892b381c8957171367a3513d278ddbb5300b039dae50ed998a684bed0a3679b`.

No target/anchor input, support query, placement, memory agent, or image was
used. Public evidence is
`docs/evidence/phase5_floorplan304_absolute_route_v4_1_precommit.json`; the
coordinate-free binding is
`configs/phase5_r1_anchor_candidates_absolute_v4_1_floorplan304.json`.
Exactly one native qualification-v7 batch remains blocked until this contract
is committed and pushed. FloorPlan305 is not allowed. Route-contract tests
passed 38/38 and the complete offline regression passed 194/194.

## Gate before formal comparisons

Formal Phase 5 results require:

- accepted deterministic Phase 4 evidence;
- two tasks and three variants passing unit/parity tests;
- inspected capable no-memory search;
- offline stale miss/recovery acceptance;
- completed scene qualification with the frozen first-six rule;
- inspected one-configuration three-variant engineering dry run;
- a committed manifest on a clean revision.

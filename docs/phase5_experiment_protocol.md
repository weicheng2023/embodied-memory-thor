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

### FloorPlan304 native qualification-v7 stop

Only after `59b9f02` was pushed, the one authorized native batch ran its full
12-candidate balanced prefix: six Bed and six Shelf trials. The process
completed with no fatal exception and reset restoration passed 12/12. The six
Bed placements all passed physical QA, including 2.313--2.898 m movement,
old-view invisibility, three-sample stability, expected support, and zero
non-support overlap. Yet their shared fallback executions all failed at route
action 109 because a LaundryHamper blocked the coverage move. The six Shelf
placements were rejected because an existing object occupied the spawn area.
No replay ran because every trial had already failed either physical placement
or fallback.

Consequently, FloorPlan304 cannot be labeled a cleanly exhausted infeasible
scene: route execution failure is explicitly outside the predecessor-skip
condition. No anchor was frozen, the R1 count remains 3/6, and FloorPlan305 is
still blocked. No memory agent, image, force action, Book rotation, or later
scene ran. Before any rerun or successor scene, the repeated fallback route
failure requires a separately preregistered diagnosis and protocol decision.
Public coordinate-free evidence is
`docs/evidence/phase5_floorplan304_native_qualification_v7.json`.
Result-focused tests passed 39/39 and the complete offline regression passed
195/195.

### FloorPlan304 paired route-mutation diagnostic precommit

The stop evidence admits one diagnosis, not a recovery or scene transition.
From separate fresh resets, both conditions receive the retained start and the
same frozen route. The original-scene control performs four Pass actions before
route replay. The intervention performs frozen Bed candidate 1 placement plus
three Pass actions. This matches the number of pre-route environment steps and
reproduces the original placement stability delay. Route actions are replayed
directly so a visible original Book cannot trigger target lock or pickup.

The decision is fixed in advance. A baseline route failure marks FloorPlan304's
route invalid and stops. A baseline pass plus placement failure isolates a
placement-induced state effect and stops pending a separately preregistered,
general obstacle-recovery fallback. Both full routes passing means only that
the prior block was not reproduced and allows continuation with FloorPlan304
candidate 1; it does not erase the retained negative result. Any placement or
contract mismatch invalidates the diagnostic. No support query, new candidate,
recovery action, planner, memory, image, or FloorPlan305 is allowed. The
executable contract is
`configs/phase5_floorplan304_route_mutation_diagnostic_v1.json`.
Diagnostic-focused tests passed 42/42 and the complete offline regression
passed 198/198. No real paired diagnostic has run yet.

### FloorPlan304 paired route-mutation diagnostic result

The clean `336fa40` diagnostic was valid and did not produce good news. In the
original scene after four matched Pass actions, route steps 1--108 succeeded
and step 109, a coverage `MoveAhead`, failed because a LaundryHamper blocked
the agent. After frozen Bed candidate 1 placement and three matched Pass
actions, placement succeeded, route steps 1--108 again succeeded, and the same
step 109 failed for the same blocker.

The LaundryHamper was not moving in either condition and its recorded drift was
below one micrometer. No non-Book object changed by more than 1 mm between the
two pre-route conditions. This isolates the failure to the frozen route's
runtime traversability and rejects Book placement as its cause. The earlier
route-only evidence remains valid only as construction/digest/horizon/bound QA;
that tool did not execute all constructed actions.

By the preregistered decision rule, FloorPlan304 is marked route-failed and the
work stops. A general obstacle-recovery policy was neither chosen nor executed;
such a change would require separate preregistration. FloorPlan305 remains
blocked. Public evidence is
`docs/evidence/phase5_floorplan304_route_mutation_diagnostic_v1.json`.
Result-focused tests passed 43/43 and the complete offline regression passed
199/199.

### Route-execution gate v1 and sequential completion rule

FloorPlan304 is now formally classified `route_execution_ineligible`: its route
is deterministically constructible within the action bound, but its valid
fresh-reset no-placement baseline cannot execute through action 109. This
classification is distinct from FloorPlan301's native-candidate exhaustion and
permits advancing to FloorPlan305 under a new explicit rule.

For every remaining scene in the retained route-construction-eligible order,
the gates are sequential. First construct the absolute-horizon route and bind
its digest/count. Second, from a fresh reset and retained start, run four Pass
actions and execute every route action directly, with no planner, placement,
support query, recovery, memory, or image. Third, only a complete baseline pass
with successful reset restoration may authorize native qualification. The
native loader validates scene, digest, count, restoration, and no-placement
fields from public baseline evidence before it can create the environment.

An ordinary baseline route action failure is skippable only when the frozen
contract and reset restoration remain valid and no fatal error occurs. Contract
mismatch, launch/reset/precondition/restoration failure, or exception stops the
sequence. No obstacle recovery is enabled in v1. The declared order begins at
FloorPlan305 and continues through the retained route-eligible registry until
six distinct R1 anchors qualify. Current qualified count remains 3/6. The
executable policy is `configs/phase5_r1_route_execution_gate_v1.json`.
Gate-focused tests passed 46/46 and the complete offline regression passed
202/202. No FloorPlan305 environment has been started.

### FloorPlan305 route construction and baseline execution pass

On clean `00fd480`, the construction gate produced a 115/240-action compatible
absolute-horizon-v4 route with digest
`ee28505764f148e0e5b209810333e40cf84cd12d3259c5bc1113918da00dca09`.
The separately reset baseline satisfied its visible-Book/stability precondition,
ran four Pass controls, executed all 115 route actions successfully, and passed
reset restoration. Thus FloorPlan305 is route-execution-eligible.

Neither gate ran a support query, placement, planner, recovery, memory agent,
or image. Public evidence is
`docs/evidence/phase5_floorplan305_absolute_route_v4_precommit.json` and
`docs/evidence/phase5_floorplan305_baseline_route_execution_v1.json`. The native
contract `configs/phase5_r1_anchor_candidates_absolute_v4_floorplan305.json`
machine-requires the baseline pass. Native qualification remains blocked until
these files are committed and pushed. Gate/result tests passed 47/47 and the
complete offline regression passed 203/203.

### FloorPlan305 native qualification-v7 pass

Only after the route and baseline pass contract was pushed as `60aca71`, native
qualification ran. The first balanced candidate, a Bed candidate, passed all
gates. The same Book moved 2.855426 m, was hidden from its old view, remained
stable, retained the expected support relation, and introduced no non-support
overlap. Common fallback rediscovered it at action 38 and picked it up at 39;
all actions succeeded. Fresh-reset replay and reset restoration also passed, so
the opaque anchor was frozen.

No memory agent, image, force action, Book rotation, formal episode, or later
scene ran. The qualified R1 set is now FloorPlan202, FloorPlan302,
FloorPlan303, and FloorPlan305 (4/6). Public evidence is
`docs/evidence/phase5_floorplan305_native_qualification_v7.json`. FloorPlan306
is the next retained route-construction-eligible scene and must independently
pass construction plus baseline execution before native work.
Result-focused tests passed 48/48 and the complete offline regression passed
204/204.

### FloorPlan306 route construction and baseline execution pass

On clean `344e70a`, the absolute-horizon route constructed at 150/240 actions
with digest
`31b9037b881994ab80dc97f732e6b37ae95a330629d112831f78781fd5d3207f`.
The fresh-reset baseline then passed its four controls, executed all 150 route
actions, and passed reset restoration. It used no support query, placement,
planner, recovery, memory, or image. Public route/baseline evidence and the
machine-gated FloorPlan306 native contract are prepared; native remains blocked
until offline tests, commit, and push.
Gate/result tests passed 49/49 and the complete offline regression passed 205/205.

### FloorPlan306 native qualification-v7 pass

After the baseline-gated contract was pushed as `d475fee`, candidate 1 (Bed)
fully qualified. Book movement was 3.492891 m; invisibility, stability, expected
support, and zero-overlap gates passed. Fallback rediscovered at action 94 and
picked up at 95 with no failed action. Replay and reset restoration passed and
the opaque anchor was frozen. No memory, image, or later scene ran. R1 is 5/6;
FloorPlan307 is next under construction plus baseline execution gates. Public
evidence is `docs/evidence/phase5_floorplan306_native_qualification_v7.json`.
Result-focused tests passed 50/50 and the complete offline regression passed
206/206.

### FloorPlan307 route construction and baseline execution pass

On clean `ff72e77`, FloorPlan307 constructed a 113/240-action route with digest
`ce1cdda7f8fbf30eaf8f37efce4a52a9a6b48a47c93111023b433ecddf6845eb`.
The start horizon already matched the scan horizon. The fresh-reset baseline
passed four controls, all 113 route actions, and reset restoration. It ran no
query, placement, planner, recovery, memory, or image. Public evidence and a
machine-gated native contract are prepared; test/commit/push precede native.
Gate/result tests passed 51/51 and the complete offline regression passed 207/207.

### FloorPlan307 pass and six-anchor completion

After `55cf276` was pushed, FloorPlan307's first balanced Bed candidate passed.
Book movement was 3.627789 m; old-view invisibility, stability, expected support,
and zero-overlap gates passed. Fallback rediscovered at action 39 and picked up
at 40 with no failed action. Replay and reset restoration passed.

The declared stop condition is now met. The six qualified scenes, in selection
order, are FloorPlan202, FloorPlan302, FloorPlan303, FloorPlan305,
FloorPlan306, and FloorPlan307. FloorPlan301 is retained as native-candidate-
ineligible; FloorPlan304 is retained as route-execution-ineligible. No
FloorPlan308 environment was started. The public frozen manifest is
`configs/phase5_r1_frozen_anchor_set_v1.json`; the merge utility validates the
six source registries and writes coordinates only to an ignored evaluator-only
output. This completes anchor infrastructure, not a memory-agent comparison.

The evaluator-only merge then validated all six source registry digests,
scene identities, public qualification passes, and one unique anchor per scene.
Its private digest is
`423cf8ef98d73b56d836edbda83563cf4ebdc0604063e1ccf9530f876f781d92`.
The merged file remains Git-ignored and planner-invisible. Public completion
evidence is `docs/evidence/phase5_r1_frozen_six_anchor_set_v1.json`.
Completion tests passed 55/55 and the complete offline regression passed 211/211.

### Production R1 runtime and excluded integration probe precommit

The final six anchors and their qualified search routes are now available to
the ordinary runner through a strict public/private join. Public configuration
rows contain only `configuration_id`, scene, opaque anchor and route IDs, and
SHA-256 digests. The evaluator-only loader verifies the merged private-set
digest, start-pose digest, source qualification-route digest, and action-only
route digest before it can create a runtime.

The frozen start is a private `TeleportFull` action after reset and before
planner observation 0. Its action, coordinates, and exact Book ID are written
only to `evaluator_setup.jsonl`; the reset event's safe last-action fields are
copied into observation 0 so `TeleportFull` cannot leak into planner input. The
post-teleport agent pose and visible objects remain the real observation. In the
stale condition, one private `PlaceObjectAtPoint` fires only after successful
distraction transition 3 while the exact Book is hidden. Its destination and
native action appear only in `intervention.jsonl`; ordinary post-action fields
remain those of the agent action.

Before any real variant result, the first frozen scene, FloorPlan202, is fixed
as `phase5-r1-production-integration-probe-v1`: R1 stale, variants in declared
no-memory/K=2/object-memory order, maximum 260 evaluated actions, formal runner
mode, no frames, HTML, live view, or evaluator debug, stop on the first episode
or integrity failure, and `included_in_formal_aggregate=false`. This is narrower
than Phase 5B because R2 six-configuration real qualification remains incomplete.
Even a fully passing triplet proves only that the R1 production setup, stale
intervention, route, logging, and metrics work together; it cannot unlock or be
pooled into the 54-episode formal matrix.

Offline acceptance found and corrected the `TeleportFull` last-action leak,
then passed 18/18 focused tests and 215/215 full regression tests. No real memory
variant had run when this contract was frozen.

#### V1 label-audit invalidation and v2 correction

The first real v1 triplet on clean `a364289` was behaviorally complete: every
variant succeeded in 31 steps, ordinary information-boundary audits passed,
no/K=2 shared the same route, and object memory produced one stale use, one
old-viewpoint miss, 26 shared fallback actions, and one visible-derived record
correction. These values are retained as engineering diagnostics only.

The post-run evidence audit found that generic per-episode manifests used
`evidence_status=formal_acceptance_candidate` even though the enclosing probe
correctly set `included_in_formal_aggregate=false`. This is an evidence-label
ambiguity, not a behavior or information-leak failure. V1 is therefore not the
final probe evidence. V2 changes no scene, start, intervention, route, variant
order, planner, memory, max steps, output policy, stopping rule, or metric. It
only requires each episode manifest and summary to say
`included_in_formal_aggregate=false`, identify the integration-probe purpose,
and use `evidence_status=excluded_engineering_probe`. After commit/push, the
whole triplet must be rerun; individual v1 episodes cannot be reused.
The v2 label gate passes 18/18 focused tests and 215/215 full regression tests;
the real rerun still requires a clean committed and pushed revision.

The clean `1b97aab` v2 rerun passed 3/3 with zero metric, privacy, route, or
evidence-label errors. All three finished in 31 steps. No memory and K=2 shared
the same one entry-alignment plus 26 route actions. Object memory used one stale
record, detected one old-viewpoint miss, executed the same 26-action fallback,
and refreshed the record at step 30 before pickup at step 31. The equality is
reported as-is; this stale negative probe does not support a memory-speed claim.
The accepted public record is
`docs/evidence/phase5_r1_production_integration_probe_v2.json`. It remains
excluded from formal aggregation and does not satisfy the R2 requirement.

## Gate before formal comparisons

Formal Phase 5 results require:

- accepted deterministic Phase 4 evidence;
- two tasks and three variants passing unit/parity tests;
- inspected capable no-memory search;
- offline stale miss/recovery acceptance;
- completed scene qualification with the frozen first-six rule;
- inspected one-configuration three-variant engineering dry run;
- a committed manifest on a clean revision.

### R2 real-scene qualification protocol precommit

R2 cannot use the earlier placeholder policy of rotating until a
CoffeeMachine happens to appear. Each admitted kitchen configuration requires
two frozen public action-only routes with different, explicit evidence roles:

- `task_subgoal_navigation`: evaluator qualification may use the selected
  CoffeeMachine interactable pose to construct this route. The public/runtime
  form contains only primitive navigation actions and digests, discloses
  `qualification_goal_input_used=true`, and exposes no object ID, coordinate,
  destination pose, or reachable-position graph to the planner. All memory
  variants receive the identical route.
- `target_independent_fallback`: constructed from the clean post-subgoal pose
  and reachable graph without Cup position or ID. It retains
  `qualification_goal_input_used=false` and
  `target_or_anchor_input_used=false`. No-memory and an evicted K=2 memory use
  this capable fallback; object memory may instead return toward its visible-
  derived last-seen Cup viewpoint.

The subgoal route is executed to completion even if a CoffeeMachine becomes
visible early. A frozen route action failure, entry mismatch, exhaustion, or
missing visible CoffeeMachine at completion invalidates the episode; the
runner cannot silently fall back to ad-hoc rotations. The common planner-safe
target-lock policy handles currently visible Cup pickup for every variant.

Qualification is evaluator-only and runs no memory variant. For one scene it
selects the first pickupable Cup and first initially-off toggleable
CoffeeMachine by sorted object ID, queries interactable poses on separate fresh
resets, and freezes at most 12 rank-balanced pose pairs before observing native
outcomes. A pair passes only if: the start Cup is visible/pickupable and the
CoffeeMachine is initially hidden; every subgoal navigation action succeeds;
Cup is continuously hidden for at least K=2 final post-action observations and
is still hidden at toggle; native `ToggleObjectOn` succeeds; the target-
independent fallback plus common target lock rediscovers and picks Cup; the
whole chain passes an identical fresh-reset replay; and reset restoration
returns Cup visible, CoffeeMachine off, and inventory empty. First fully
qualified wins. Failed candidates are retained. Public output is coordinate-
free and remains `formal_use_allowed=false` until a later runtime integration
gate.

The first launch is restricted to FloorPlan1. It must run from a clean committed
and pushed revision and stops before FloorPlan2 regardless of pass/fail. Offline
dual-route, planner-boundary, ordered-task, and route-builder tests pass 23/23,
and the complete offline regression passes 220/220;
no real R2 qualification has run at this precommit checkpoint.

#### FloorPlan1 start-pose stop

The first clean real launch on pushed `aa6e08d` stopped before candidate-plan
construction. The first pickupable Cup selected by sorted object ID had no
standing pose in the successful `GetInteractablePoses` result. Therefore zero
of 12 possible pose pairs were frozen and zero candidate trials ran. No route,
CoffeeMachine toggle, fallback, target lock, memory variant, image, or later
scene ran.

This is a start-selection protocol failure, not a negative result about memory
or the ordered task. The kitchen presence census proves only that at least one
pickupable Cup exists, not that the first object-ID Cup has a standing
interactable pose. A retry is prohibited until one of these materially
different rules is pre-registered: scan sorted Cup instances and select the
first with a standing interactable pose, or admit and validate non-standing
starts. The conservative recommended revision is the first rule because it
preserves standing navigation and changes target selection only by an
evaluator-side feasibility predicate. Public stop evidence is
`docs/evidence/phase5_floorplan1_r2_start_pose_stop.json`.

#### R2 start-selection revision v2

The conservative revision is adopted. On a fresh scene reset, enumerate every
pickupable Cup in ascending `objectId` order. For each Cup, perform exactly one
`GetInteractablePoses` query after its own fresh reset, retain the result in an
evaluator-only audit, and select the first Cup with at least one normalized
standing pose. Stop checking later Cups as soon as one passes. Query failure is
fatal rather than silently skipped. If no Cup passes, the scene is classified
as lacking a standing-interactable Cup start.

This feasibility selection occurs before route-pair construction and cannot
use route execution, CoffeeMachine interaction, fallback, pickup, or memory
outcomes. All subsequent candidate pairs are built only for the selected Cup;
the previous 12-pair ordering and every downstream gate remain unchanged.
Exact Cup IDs and per-Cup query results remain evaluator-only. The public
summary exposes only aggregate selection/qualification status.

After offline tests and full regression, v2 must be committed and pushed. Only
FloorPlan1 may then be rerun, with no memory variants. A FloorPlan1 success may
advance the existing scene-order protocol; a failure must first be classified
before deciding whether it is a scene-skippable failure or a protocol defect.

Offline v2 selection tests cover sorted-ID order, one fresh reset per Cup,
skipping a zero-standing-pose Cup, stopping at the first passing Cup, retaining
the all-fail audit, and treating query failure as fatal. The complete offline
regression passes 223/223. No real v2 rerun has started at this checkpoint.

The clean pushed `b1f42ec` v2 rerun checked the complete FloorPlan1 pickupable
Cup set: one Cup, one successful pose query, and zero returned poses. It again
stopped with zero candidate pairs and zero task trials. Under the v2 rule this
is now a scene-level eligibility result,
`scene_start_ineligible_no_standing_cup`, with `scene_skip_allowed=true`.
FloorPlan1 cannot supply an R2 configuration under the standing-start protocol,
but the protocol itself behaved as registered. No route, toggle, fallback,
target lock, memory variant, image, or later scene ran. Public evidence is
`docs/evidence/phase5_floorplan1_r2_v2_scene_start_ineligible.json`.

The qualifier may now accept only the kitchen family FloorPlan1-FloorPlan30,
while orchestration remains strictly ascending and one scene at a time. A
scene-start-ineligible result permits advancing exactly to the next kitchen
scene after its evidence and range gate are committed and pushed. Other fatal
errors remain `qualification_invalid_requires_review` and cannot be skipped;
candidate exhaustion also requires review rather than automatic skipping.

Classification/range tests pass 8/8 and the complete offline regression passes
225/225. FloorPlan2 has not run at this checkpoint.

After pushed `9ba7a0d`, exactly FloorPlan2 ran. Its complete pickupable-Cup set
again contained one object; the isolated pose query succeeded and returned zero
poses. The result is the same scene-specific classification,
`scene_start_ineligible_no_standing_cup`, with `scene_skip_allowed=true`.
Candidate pairs/trials remained 0/0. No route, CoffeeMachine interaction,
fallback, target lock, memory variant, image, or FloorPlan3 ran. Public evidence
is `docs/evidence/phase5_floorplan2_r2_v2_scene_start_ineligible.json`.

The one-scene stopping rule therefore halts here. FloorPlan3 is the next
eligible scene in order, but it may run only after the FloorPlan2 result is
committed and pushed; this result does not authorize batching later scenes.

After clean pushed `318db5f`, exactly FloorPlan3 ran. The first sorted
pickupable Cup supplied 158 standing poses, 12 rank-balanced Cup/CoffeeMachine
pairs were frozen before outcomes, and candidate 1 fully passed. The public
task-subgoal route is six primitive actions and honestly retains
`qualification_goal_input_used=true`; the target-independent fallback is 110
actions with no Cup/anchor input. K=2 eviction, native CoffeeMachine toggle,
fallback rediscovery/pickup, identical fresh-reset replay, and reset restoration
all passed. No memory variant or image ran. Public coordinate-free evidence is
`docs/evidence/phase5_floorplan3_r2_v2_qualification.json`.

### Production R2 runtime and excluded integration probe precommit

The first qualified R2 result is joined into a production runtime through two
strictly separated artifacts. `configs/phase5_r2_frozen_runtime_v1.json`
contains only the opaque configuration ID, scene, route IDs, and digests. The
local ignored registry contains the TeleportFull start and selected object IDs;
its complete digest is bound into the public contract. Runtime loading rejects
private-set, start-pose, scene, qualification, route-role, or route-digest
mismatches before planner observation zero. The setup privately verifies the
qualified Cup is visible/pickupable and the CoffeeMachine is toggleable, hidden,
and off. Ordinary traces may contain current visible observation state, but not
the private native setup, candidate plan, destination pose, or reachable graph.

One three-variant integration probe is precommitted in
`configs/phase5_r2_production_integration_probe_v1.json`. It uses fixed order
no-memory, K=2, object-memory; identical start/subgoal/fallback/target-lock; 140
steps; no images, GUI, evaluator debug, or formal aggregation; and immediate
stop on the first episode or audit failure. This checkpoint implements and
tests the runtime and probe only. It deliberately does not run the memory
variants yet. The real probe requires a clean committed and pushed revision.
Focused tests pass 18/18 and the complete offline regression passes 229/229.

#### FloorPlan3 production probe v1 stop

The clean pushed `a32a6bc` excluded probe ran the complete fixed triplet.
No-memory and K=2 both passed in 13 steps, using all six subgoal-route actions
and four actions from the capable shared fallback; K=2 was confirmed evicted
before reacquisition. Object memory failed at the 140-step limit. It executed
132 memory-guided actions, zero fallback actions, and accumulated 131 repeated
viewpoint visits. Every variant passed the information-boundary audit, and the
probe remained excluded from formal aggregation.

Trace diagnosis identifies a deterministic discrete-control defect. Beginning
at reacquisition step 9, the stored viewpoint bearing lay between two headings
available under 90-degree primitive rotation. The memory planner compared the
continuous bearing against a one-degree convergence tolerance, alternated
`RotateLeft` and `RotateRight`, never translated, and never relinquished the
still-present memory record to the fallback. This is not evidence that object
memory is intrinsically worse; it is an integration failure in the shared
memory-navigation controller.

Public stop evidence is
`docs/evidence/phase5_floorplan3_r2_production_probe_v1_stop.json`. FloorPlan4
and later scenes remain unrun. The next change must be separately precommitted:
a shared discrete-heading convergence rule plus a bounded memory-to-fallback
escape rule, with offline 90-degree quantization/parity/privacy tests. The full
three-variant excluded triplet must then be rerun from a clean pushed revision;
the two passing v1 episodes cannot be selectively reused.

The repair is precommitted as `phase5-memory-navigation-v2`. Continuous
last-seen-position and last-seen-viewpoint headings are deterministically
quantized to the runner's 90-degree primitive action grid using half-up ties.
Separately, a runner guard reads only successive planner-safe agent positions.
Three consecutive memory-guided actions with less than 0.05 m positional
progress suppress the cited record for retrieval, exposing the unchanged frozen
fallback. A later visible-derived observation of the same record removes the
suppression. No target/anchor/support coordinate, reachable graph, or evaluator
metadata is added to planner input. The guard exists for every memory variant;
no-memory and evicted K=2 simply never cite a record.

Probe v2 is frozen in
`configs/phase5_r2_production_integration_probe_v2.json`. It preserves the same
FloorPlan3 start, six-action subgoal route, 110-action fallback, variant order,
140-step limit, artifact policy, and exclusion label. It changes only the
declared memory-navigation policy and requires a complete triplet rerun with no
v1 episode reuse. Focused discrete-heading, bounded escape, visible-derived
recovery, parity, privacy, ordered-task, and stale-recovery tests pass 20/20;
the complete offline regression passes 235/235. A real v2 launch still requires
a clean committed and pushed revision.

The complete v2 triplet subsequently passed from clean pushed revision
`29db132`. No-memory and K=2 each completed in 13 steps using the same six
subgoal actions and four fallback actions; K=2 was evicted before
reacquisition. Object memory completed in 20 steps with 11 memory-guided
actions and no fallback, invalid action, interaction failure, guard escape, or
remaining suppressed record. Thus executable-heading quantization fixed the
observed v1 oscillation without relying on the escape guard. All ordinary-trace
privacy audits passed.

The result remains excluded integration QA. It cannot establish a memory
benefit, and the honest single-episode observation is that object memory was
seven steps slower than both controls. Public coordinate-free evidence is
`docs/evidence/phase5_floorplan3_r2_production_probe_v2.json`. The next gate is
ascending R2 qualification from FloorPlan4 until six frozen configurations;
no additional memory variants are allowed during qualification.

FloorPlan4 qualified at candidate 1 from clean pushed revision `4877f3e`: the
11-action task-subgoal route, 110-action target-independent fallback, K=2
eviction requirement, fresh-reset replay, and reset restoration all passed.
No memory variant or image ran. Public evidence is
`docs/evidence/phase5_floorplan4_r2_v2_qualification.json`, bringing the count
to 2/6.

Runtime-set immutability rule: the one-configuration v1 set remains the exact
snapshot used by the completed FloorPlan3 integration probe and must not be
mutated as later scenes qualify. Coordinate-free qualification evidence and
ignored evaluator outputs accumulate separately. Once the ascending procedure
reaches 6/6, freeze a new versioned six-configuration public/private set and
only then authorize the next multi-configuration runtime gate.
The FloorPlan4 public route/evidence gate passes 25/25 focused tests and the
complete offline regression passes 236/236.

FloorPlan5 qualification v2 stopped after all 12 precommitted pairs failed the
start precondition. Teleport, object existence, Cup pickupability, and initial
machine-off status passed 12/12; Cup visibility passed 8/12, while machine
hidden status passed 0/12. The pair prefix used only Cup pose orders 1-4 from
92 standing poses. Therefore the result cannot distinguish a structurally
ineligible scene from a rank-balanced-prefix coverage defect.

Before FloorPlan6 or any qualifier revision, run only the precommitted
`phase5-r2-start-visibility-census-v1` on FloorPlan5. It exhausts the selected
Cup's pose-sort-ordered standing poses under one fresh reset and one
TeleportFull per pose, checking only the seven already-declared start
preconditions. It may not query CoffeeMachine poses or reachable positions,
build/execute routes, interact, plan, use memory, save images, or contribute to
formal results. A nonzero eligible-pose count permits a separately precommitted
start-feasibility filter before rank-balanced pairing; zero permits structural
scene exclusion. Public stop evidence is
`docs/evidence/phase5_floorplan5_r2_v2_candidate_stop.json`.
The pre-run gate passes 16/16 focused tests and 239/239 full offline tests. The
real census may start only from a clean committed and pushed revision.

The clean pushed `4f23dd0` census exhaustively checked 86 standing poses and
found four joint-start-feasible poses; the first was pose order 39. Cup was
visible in 51/86 views and CoffeeMachine was hidden in 5/86, with four views
satisfying every condition. No route, interaction, target pose query, planner,
memory agent, image, private coordinate exposure, or formal result occurred.
The earlier qualification query returned 92 standing poses versus 86 here, so
pose count/order is not treated as a cross-run constant and no order or
coordinate is hardcoded.

Qualification v3 therefore performs an exhaustive, within-run evaluator filter
over the currently returned standing Cup poses, each after its own fresh reset.
It retains only poses satisfying the already-declared joint start preconditions,
then freezes the original first-12 rank-balanced pairs over eligible-pose rank
and CoffeeMachine-pose rank before any route/task outcome. All downstream gates
and public/private boundaries remain unchanged. Only FloorPlan5 may rerun from
the clean pushed v3 revision; FloorPlan6 and memory variants remain blocked.
The v3 pre-run gate passes 24/24 focused tests and 241/241 full offline tests.

The clean pushed `c26402b` FloorPlan5 v3 retry found five joint-feasible starts
among 92 standing poses but exhausted all 12 candidate pairs. Two poses failed
to reproduce Cup visibility on the later fresh-reset trial. The other ten each
completed the subgoal, K=2 hidden gate, CoffeeMachine toggle, and every action
of a 160-164-action zero-degree fallback with no action failure, yet never
observed Cup and never entered target lock. This is a fallback visual-coverage
failure, not navigation or interaction failure. FloorPlan6 remains blocked.

The next diagnostic fixes candidate 2, its private start, six-action subgoal,
and full spatial fallback sequence. A fresh-reset control retains the leading
30-to-0 LookUp and trailing 0-to-30 LookDown (162 actions). A fresh-reset
treatment removes only those boundary actions and executes the identical 160
intervening actions at absolute +30 degrees downward. No memory variant, image,
formal result, new route geometry, or later scene is allowed. Only a clean
control failure paired with a clean treatment success attributes the defect to
vertical scan coverage.
The paired diagnostic passes 21/21 focused tests and 244/244 full offline tests;
real execution requires a clean pushed revision.

The clean pushed `3ed2cbe` pair passed every integrity gate but both arms
failed: the 0-degree control executed 162 fallback actions and the +30-degree
treatment executed the identical 160 intervening actions, with zero action
failures, yet neither observed Cup or entered target lock. Therefore a downward
horizon alone is not causal or sufficient.

Read-only route audit locates the stronger baseline defect. The 127-node graph
was represented by only 16 full-scan waypoints and 58 traversed destination
nodes. The Cup's frozen initial viewpoint node was neither scanned nor
traversed; its nearest scan waypoint was exactly the configured three-grid-step
(0.75 m) nominal radius. Thus `complete_graph_coverage=true` means geometric
radius coverage, not guaranteed visual coverage under occlusion. Fresh-reset
restoration confirms Cup still exists, is visible at the frozen start, and is
not in inventory. The next revision must strengthen the target-independent
capable baseline's spatial/visual coverage generally; it cannot use Cup
coordinates or a FloorPlan5-specific route. FloorPlan6 and all memory variants
remain blocked. Public evidence is
`docs/evidence/phase5_floorplan5_r2_paired_horizon_diagnostic_v1.json`.

#### R2 exhaustive visual fallback v1 precommit

FloorPlan5 is now frozen as `visual_coverage_failure`. The prior route's
geometric radius claim is not reused as a visual-coverage claim. Its action
sequence and the qualified FloorPlan3/FloorPlan4 evidence remain immutable.

The successor `phase5-target-independent-exhaustive-visual-v1` is a separate
general fallback. It is built only from a fresh reachable-position graph and
the post-subgoal agent pose. It takes no Cup ID or coordinates, anchor/support
information, task outcome, memory record, memory provider, or variant label.
A deterministic depth-first traversal visits every reachable grid node and
returns over the same tree edges. On the first visit to every node it performs
one four-cardinal scan at absolute 0 degrees and one at absolute +30 degrees,
then restores the entry camera horizon at route end. Route construction is
fail-closed for a disconnected graph or if its conservative worst-case bound
exceeds the pre-registered 2048-action fallback limit.

When admitted to production, the route is built/frozen once per configuration
and supplied unchanged to no-memory, K=2, and object-memory. The existing
memory providers are not modified. A memory-capable agent may still reacquire
earlier, but reaching shared fallback exposes the same action sequence and
target-lock policy to every variant. Visible Cup observations may trigger the
existing common target lock; evaluator IDs remain limited to setup and success
checking and are never route-construction inputs.

Before any real execution, offline gates verify the target-free function
signature and serialized route, all-variant sharing contract, 2048-action cap,
unchanged memory-provider hashes, and unchanged FloorPlan3/FloorPlan4 evidence
hashes. The first real gate is exactly one excluded diagnostic using frozen
FloorPlan5 candidate 2, without memory variants, images, or later scenes. A
fresh reset isolates `GetReachablePositions` route construction from the task
trial. Only clean target rediscovery and pickup plus reset restoration permits
a separately versioned FloorPlan5 qualification retry. Route-action failure,
exhaustion without rediscovery, privacy failure, or frozen-hash failure stops
the protocol without qualification or FloorPlan6.

The clean pushed `4df165c` real candidate-2 diagnostic stopped at the start
gate. The new target-independent route itself constructed successfully for all
127 reachable nodes: 127 nodes visited and scanned at both 0 and +30 degrees,
1645 planned actions under the 2048 limit and 2028 conservative bound. However,
after the diagnostic's fresh reset and TeleportFull, Cup existed and remained
pickupable but was not visible. All other start preconditions passed. No
subgoal, toggle, target lock, or fallback action executed. A subsequent fresh
reset and the same frozen start restored Cup visibility, so the precise class
is `frozen_start_visibility_nonreproduction`, consistent with the earlier
cross-reset variability rather than a failure of the newly built fallback.

This result cannot be used to claim either success or failure of exhaustive
visual fallback. FloorPlan5 qualification retry remains prohibited and
FloorPlan6/memory variants remain blocked. Any retry needs a separately
precommitted matched treatment for nondeterministic frozen-start visibility;
the current run must not be silently repeated until it passes. Public evidence
is `docs/evidence/phase5_floorplan5_r2_visual_fallback_diagnostic_v1.json`.

### R2 start stability and qualification v4 precommit

`phase5-r2-start-visibility-stability-v1` replaces one-reset admission for new
R2 scenes. Within each scene, evaluator-only selection still chooses the first
pickupable Cup with standing interactable poses in deterministic identity order.
Every normalized standing pose is then checked on exactly three independent
fresh resets. Each reset repeats only the selected-Cup pose query, locates the
same pose by its private digest, teleports when present, and evaluates the seven
fixed conditions: teleport success, Cup existence/pickupability/visibility,
CoffeeMachine existence/off state/hiddenness. Only 3/3 poses are retained;
1-2/3 are unstable and 0/3 are ineligible. No stable pose yields the registered
scene-level class `scene_start_visibility_unstable_no_stable_pose`. Query error
or reset-restoration failure remains a hard stop. This gate builds no route,
queries no CoffeeMachine pose, runs no interaction/planner/memory, and saves no
image.

`phase5-r2-native-qualification-v4` reruns that stability gate in the actual
qualification process; it never imports a successful audit trial or hardcodes
an earlier pose. It then queries CoffeeMachine poses and the evaluator-only
reachable graph, freezes the deterministic rank-balanced first 12 stable-start
by destination pairs before task outcomes, builds the existing goal-qualified
subgoal route, and builds the general
`phase5-target-independent-exhaustive-visual-v1` fallback. That fallback visits
and scans every reachable node at absolute 0 and +30 degrees, has a fixed 2048
action limit, and receives no Cup/anchor/memory/variant input. A passing candidate
must pass one native trial, an independent fresh-reset replay, and restoration.

Scene-level construction, execution, reacquisition, or batch exhaustion classes
listed in `configs/phase5_r2_qualification_v4.json` may be recorded and skipped
after restoration and privacy checks. No FloorPlan-specific route or identity
exception is permitted. FloorPlan3/FloorPlan4 evidence, the one-configuration
runtime snapshot, and the prior search-route registry are hash-frozen at this
precommit. Qualification v4 produces evaluator-private drafts under ignored
outputs; each passing scene is published only as coordinate-free actions and
digests in its own later evidence commit. No memory variant or formal aggregate
is authorized by this revision.

### R2 over-bound start stability and qualification v5 precommit

FloorPlan13 stopped under v1 after its selected Cup returned 260 normalized
standing poses, above the implementation guard of 256. The stop is retained as
evidence; v1/v4 results are not reinterpreted or pooled with the successor.

`phase5-r2-start-visibility-stability-v2` pre-registers a 256-pose audit budget.
When the deterministic `pose_sort_key` order contains at most 256 poses, the
complete order is retained. When it contains more, the evaluator freezes 256
unique integer ranks spread evenly across the complete ordered range, including
both endpoints. The rank set is determined only by observed count and budget,
before any visibility, route, interaction, or task outcome. It is not a silent
prefix truncation and the cap is not raised. Public output exposes only
observed/selected/omitted counts, policy and selection digest; selected ranks,
pose digests, coordinates and identities remain evaluator-only ignored data.

The three-reset/seven-precondition rule is unchanged for every selected pose.
Any pose-query error remains a hard stop, but both the standalone gate and the
qualifier must perform and report an explicit fresh-reset restoration audit
before closing the environment. Failure to establish restoration remains a
hard stop.

`phase5-r2-native-qualification-v5` uses exactly the same common selector and
otherwise preserves v4's outcome-independent first-12 pairing, 240-action
subgoal bound, target-independent exhaustive visual fallback, fixed 2048 bound,
native replay, restoration, privacy boundary and registered scene exclusions.
It adds no target, anchor, support, identity or coordinate field to planner
input. Historical v1/v4 configs/evidence and the FloorPlan12 qualified public
configuration are hash-frozen in `configs/phase5_r2_qualification_v5.json`.
The first real successor gate is a fresh FloorPlan13 standalone audit from a
clean pushed revision; only if it passes may FloorPlan13 qualifier v5 run.

### R2 budgeted visual fallback v1 precommit

R2 remains 3/6 after FloorPlan5--16. The repeated blocker in FloorPlan6, 7,
8, 10, 13 and 16 is construction of the exhaustive visual fallback above the
unchanged 2048-action limit. Those outcomes and the qualified FloorPlan3, 4
and 12 evidence remain immutable.

`phase5-r2-budgeted-visual-fallback-v1` is a separately versioned successor.
It partitions the fresh reachable grid into fixed 3-by-3 grid-step bins,
retains exactly one deterministically selected reachable viewpoint in every
occupied bin, and joins viewpoints by deterministic graph shortest paths. At
each viewpoint it performs the same fixed four-cardinal scan at absolute 0 and
+30 degrees. Selection and ordering use only the reachable grid, fixed policy
parameters and starting pose. They accept no Cup or CoffeeMachine coordinate
or identity, anchor, candidate outcome, memory record/provider, or variant.
The route is one common construction for no-memory, K=2 and object-memory.

The 2048 limit is not raised. Exact construction above the limit is classified
`budgeted_visual_fallback_construction_ineligible`; it is never truncated or
adapted using object visibility. Bin coverage is a nominal geometric sampling
summary and makes no line-of-sight claim. Public evidence contains only policy
metadata, action/viewpoint counts, route digest, coordinate-free coverage
summary and classification. Reachable graphs, starting coordinates and the
complete route remain evaluator-only ignored output.

Before any real diagnostic, offline gates must prove input-order determinism,
the target-free signature and serialization, fixed scan template, action cap,
shared-variant contract and frozen historical hashes, followed by the full
repository regression and a clean pushed commit. Real work is construction
only, ordered FloorPlan6, 7, 8, 10, 13, 16. It performs no route execution,
qualification, memory variant, image or formal statistic. Processing stops at
the first construction pass; FloorPlan17 and later remain prohibited.

The first permitted real construction diagnostic passed on FloorPlan6 from
clean pushed revision `cef5b78`: 26 viewpoints, 404 planned actions under the
2048 limit, both fixed horizons represented, all occupied bins represented,
and reset restoration passed. Its route digest reproduced across the initial
audit-bug run and corrected retry. No route action, object-specific query,
qualification, memory variant or later scene ran. The registered stop-on-first-
pass rule is now active; FloorPlan7 and all later scenes remain untouched until
separate authorization.

### R2 native qualification v6 precommit

The subsequent authorization introduces `phase5-r2-native-qualification-v6`.
It hash-freezes the complete v5 qualifier and adapts only its fallback builder,
version labels, registered failure names and coordinate-free public fallback
metrics. The v2 start-stability audit, deterministic first-12 pair freeze,
subgoal route, trial/replay logic, target lock and reset restoration remain the
same function objects as v5.

The replacement builder is exactly
`phase5-r2-budgeted-visual-fallback-v1`, with the fixed 3-by-3 grid bins,
0/+30-degree cardinal scans and 2048 limit already construction-tested on
FloorPlan6. Candidate fallback routes are built before task outcomes. Cup and
CoffeeMachine identities remain evaluator-only inputs to qualification setup
and success checking; neither identity nor position enters fallback selection.
No memory provider/variant is run during qualification.

Only FloorPlan6, 7, 8, 10, 13 and 16 are admitted, in that operational order;
FloorPlan17+ remains prohibited. Registered scene-level outcomes distinguish
budgeted construction, execution and reacquisition failures. Public evidence
may expose only action/viewpoint count ranges, digest/action-only route
references, nominal bin coverage and classifications. Full qualification may
start only after offline tests, frozen-hash audit and clean push.

### R2 six-configuration runtime freeze v2 precommit

R2 qualification completed at 6/6 with FloorPlan3, 4, 6, 7, 10 and 12. The
one-configuration runtime v1 and shared v1 route registry remain immutable.
`phase5-r2-frozen-runtime-set-v2` is a separate six-configuration set with its
own public runtime registry, action-only route registry and ignored evaluator-
only setup registry.

The freeze tool accepts only the declared six configurations in fixed order.
It hash-checks every tracked qualification source, validates 12 route action
sequences/digests, verifies each ignored TeleportFull start against its public
start-pose digest, and computes one digest binding the complete private set.
The public registry contains only opaque configuration IDs, scene labels,
route/digest references and evidence paths. The private registry alone contains
target identities and start coordinates and remains under ignored `outputs/`.

Freezing is deterministic bookkeeping: it runs no simulator, planner, memory
variant or formal statistic. Offline tests and a clean push of the freeze tool
must precede generation. Generated public/private/route sets must then load all
six configurations and preserve v1 behavior before any new triplet probe.

### R2 runtime-v2 excluded integration probe v3 precommit

Before any multi-configuration or formal comparison, exactly one excluded
triplet uses `FloorPlan6_R2_fixed_start_001` from runtime set v2. The variant
order is fixed as no-memory, K=2 short memory, object memory, and execution
stops on the first episode or audit failure. All variants receive the same
13-action subgoal and 403-action budgeted fallback plus the same task, start,
success checker and 140-step cap.

The probe reuses the hash-frozen v2 runner/auditor and changes only its runtime
loader to v2. It reruns all episodes, saves no images/evaluator debug, exposes
no private setup in ordinary logs and is explicitly excluded from formal
aggregation. A pass is integration evidence only; it authorizes planning a
six-configuration dry run but is not itself a memory-effect result.

### R2 runtime-v2 probe v3 stop and shared-search entry recovery v1

The clean pushed `64cd8bf` v3 probe completed all three declared variants.
No-memory and K=2 both passed in 60 steps with the same 13 subgoal and 45
fallback-coverage actions; K=2 eviction was observed. Object memory executed
14 memory-guided actions, then the bounded memory-navigation guard suppressed
the record. The frozen fallback correctly refused to begin because those
actions had moved the agent away from the fallback entry captured immediately
after the ordered subgoal. Its failure was
`shared_search_unavailable:search route entry position mismatch`. All three
information-boundary audits passed. This is an excluded integration failure,
not a THOR failure, information leak, or memory-effect result. The v3 episodes
are not reusable. Public stop evidence is
`docs/evidence/phase5_r2_production_probe_v3_stop.json`.

`phase5-shared-search-entry-recovery-v1` is the separately registered
successor. Every variant receives the same mechanism. Before fallback coverage
has begun, it records only the names of successful pose-changing planner
actions. If fallback later becomes necessary, it reverses their order and maps
each to a fixed inverse: left/right rotations, up/down looks and ahead/back
translations. `Pass`, pickup and toggle do not change pose and are ignored.
The original fallback action sequence, digest and entry pose remain unchanged.

The recovery input contains no target or CoffeeMachine coordinate/identity,
anchor, support, candidate result, memory-record content, reachable graph or
evaluator-only metadata. The planner sees only one action-only shared-search
directive at a time. Recording is capped at 64 reversible actions. An
unsupported pose action, cap overflow, failed inverse, residual entry mismatch
or divergence from the directive invalidates the episode. The direct baselines
therefore receive the exact same policy but execute zero recovery actions when
they have not left the entry.

Offline gates must prove deterministic inversion, fixed cap, action-only
planner input, no-memory/K=2 zero-action parity, object-memory recovery after a
forced departure, unchanged v2 runtime/routes and unchanged v3 stop evidence.
Only after focused/full regression and a clean push may probe v4 rerun exactly
the complete FloorPlan6 triplet. V4 reuses no v3 episode, remains excluded from
formal aggregation, saves no image/debug trace, retains the 140-step cap and
must exercise at least one object-memory entry-recovery action without a route
entry mismatch. A pass authorizes pre-registration of the next dry-run gate;
it is still not a memory-improvement claim.

### R2 runtime-v2 excluded integration probe v4 result

After focused 24/24 and full 302/302 offline gates, clean pushed revision
`6deb0aa` reran the complete FloorPlan6 triplet from fresh resets. The retained
run passed all episode and information-flow audits. No-memory and K=2 each
completed in 60 steps with 13 subgoal and 45 fallback-coverage actions; K=2
eviction was reproduced. Both direct baselines recorded and executed zero
entry-recovery actions.

Object memory executed 14 memory-guided actions, then 14 exact inverse entry-
recovery actions, reached the original route entry with zero pending recovery,
and completed the same 45-action fallback prefix. It succeeded in 88 steps.
Thus the successor fixes the v3 route-transition defect, but this particular
scene is a clear object-memory regression rather than a positive memory result.
The result is excluded from formal aggregation and must be reported as such.

One host launch was denied before Python and one outer-command timeout ended a
partial triplet. The partial directory is retained under ignored outputs; no
episode from it or from v3 was reused. The evidence-bearing triplet is the
complete fresh run bound to `6deb0aa`. Public evidence is
`docs/evidence/phase5_r2_production_probe_v4.json`.

This v4 triplet satisfies the original Phase 5B requirement of one qualified
configuration under all three variants. Repeating all six R2 configurations as
another excluded dry run would duplicate the 18-cell formal panel and create an
unnecessary outcome-inspection stage. Therefore the next gate is Phase 5C
manifest readiness, not a second dry-run matrix.

The old generic `phase5-manifest-v1` builder is not suitable for execution: it
serializes raw `start_pose` fields into the public manifest and is not joined to
the now-frozen R1 evaluator setup/anchor registry or R2 runtime set v2 and its
12 action-only routes. Before any formal episode, a separately versioned
privacy-preserving real-runtime manifest must bind all 54 cells to opaque
configuration IDs, frozen public digests and ignored evaluator-only registries,
include the entry-recovery metrics in its required schema, fix one clean code
revision and fail closed on any incomplete 3-variant cell. No formal run is
authorized until that offline successor and its executor pass full regression.

### Privacy-preserving real formal manifest v2 precommit

`phase5-real-thor-manifest-v2` supersedes the old builder for real execution
without modifying historical manifest v1. Its public cells contain only panel,
task/condition, opaque configuration ID, scene label, memory variant, fixed
controller/output policy and action-only route IDs/digests. It explicitly
forbids raw start poses, target/support/anchor fields, object identities,
reachable graphs and native evaluator actions. Private setup, target identity
and relocation destination are joined locally through the ignored frozen R1/R2
registries and are never copied into the public manifest.

The matrix order is fixed as R1 stable, R2 stable, R1 stale; inside each panel,
declared configuration order then no-memory, K=2, object-memory. R1 stable and
stale use the same six FloorPlan202/302/303/305/306/307 configurations. R2 uses
FloorPlan3/4/6/7/10/12. This yields exactly 54 cells and 18 matched
three-variant configuration groups. Every episode uses the same 2048 evaluated-
action ceiling. This bound covers every frozen route, including the 1367-action
FloorPlan12 route, without changing the planner or stopping successful episodes
later than before.

Metric schema `phase5-real-thor-metrics-v3` retains the v2 outcomes and adds
setup/intervention validity plus the full shared-search entry-recovery contract.
The executor distinguishes an experimental task failure from an integrity
failure. A valid task failure stays in the fixed aggregate; leakage, missing
metrics, setup/intervention failure, route/digest/entry contract failure,
invalid planner action, private material in ordinary logs, dirty/unpushed code,
or incomplete runtime join invalidates and stops the matrix. Partial output is
retained and may never be resumed or selectively reused.

The first precommit sets `formal_execution_authorized=false` and permits only a
readiness run. Readiness must build the public 54-cell manifest from a clean
pushed revision, load all 12 private runtimes, verify every public/private
configuration and route join, and serialize no private material. Only a later
tracked authorization after successful readiness evidence may enable the
complete 54-episode command. Formal images, GUI, evaluator debug and desktop
screenshots remain disabled.

#### Formal v2 readiness result

Clean pushed revision `eba1c1f` built the 54-cell public manifest and joined all
12 private runtimes without starting THOR. The six R1 configurations resolved
to six action-only routes; the six R2 configurations resolved to six subgoal
and six fallback routes. The manifest contains 18 matched three-variant cells,
and its digest is `441aad54...03515`. Private runtime material was not
serialized. The readiness-only base retained
`formal_execution_authorized=false` throughout.

Formal execution may now be enabled only by a separate minimal authorization
overlay that hash-binds the immutable readiness base and this public evidence.
The overlay may not alter panels, configuration/variant order, controller,
2048 limit, metrics, output policy, runtime sources or stop rules. Execution
must still re-run readiness internally on its own clean pushed revision before
cell 1 and must start a fresh output directory; the no-THOR readiness artifact
is never treated as an episode or result.

#### Formal v2 execution authorization overlay

`phase5-real-thor-formal-execution-authorization-v2` is a minimal overlay, not
a second matrix configuration. It hash-binds readiness base
`ccbaefd7...d475`, public readiness evidence `c7590163...4221`, readiness code
revision `eba1c1f` and manifest digest `441aad54...03515`. Its field whitelist
contains no panel, configuration, variant, task, route, controller, metric,
limit, output or stop-policy override. Any additional field or hash mismatch
fails before output creation.

The effective config changes only `formal_execution_authorized` from false to
true and records the authorization provenance. The execution command must still
build a new manifest bound to its current clean pushed revision, repeat all 12
private joins, create a new output directory and begin at episode 1. No resume
or dry-run episode is accepted. Offline overlay gates must pass with the full
repository regression before the 54-cell command is launched.

### Formal v2 invalidation and Book-distraction successor

The clean `ed092cf` formal-v2 execution stopped after 8 of 54 cells and is
excluded in full. The first six FloorPlan202/302 R1-stable cells succeeded.
Both executed FloorPlan303 variants then produced the same task failure after
one successful `RotateRight`: the Book was still visible. Evaluator setup,
native action execution and the information boundary passed. This identifies a
shared task-template coverage defect, not a memory-variant effect. The K=2 row
also exposed an audit defect: eviction was required even though the common
failure occurred before reacquisition. Public stop evidence is
`docs/evidence/phase5_real_formal_pilot_v2_invalidated_stop.json`. No cell from
the partial matrix may be resumed or reused.

`phase5-book-distraction-v2` is the pre-registered successor. Every R1 variant
executes exactly the same target-independent template:
`RotateRight -> RotateRight -> LookDown -> LookUp`. The first turn is allowed
to retain visibility; after the fixed half-turn and the two camera observations,
the Book must be hidden and K=2 must be ready to have evicted observation 0.
The sequence cannot inspect Book identity/coordinates, memory, anchor/support,
candidate outcome, reachable graph or evaluator state. It has four evaluated
actions and does not change the 2048 formal episode ceiling.

Before a new formal protocol is written, the successor must pass offline gates
and one excluded FloorPlan303 isolation gate. That real gate runs all variants
only for the four fixed distraction actions, expects `max_steps_exceeded` after
the template rather than task success, requires the Book-hidden/reacquisition
stage and information boundary, saves no images/debug metadata and contributes
no formal result. Only a clean pushed pass permits a versioned full-matrix
successor. Its formal K=2 audit must require eviction only after the episode has
actually reached Book/Cup reacquisition; a common earlier task outcome remains
an outcome unless another integrity rule fails.

#### FloorPlan303 distraction gate v1 stop and horizon-independent v3

The clean pushed `aee5be3` v1 isolation gate stopped after the no-memory row.
Both fixed 90-degree rotations succeeded and the information boundary passed.
The third action, `LookDown`, failed because the frozen start was already at
the simulator's downward horizon limit. This is a relative-horizon template
failure, not a Book-visibility, setup or memory failure. The row is excluded
and cannot be reused. Public stop evidence is
`docs/evidence/phase5_r1_distraction_successor_gate_v1_stop.json`.

`phase5-book-distraction-v3` retains the target-independent half-turn but
replaces both relative horizon actions with one `Pass`. The exact template is
therefore `RotateRight -> RotateRight -> Pass`. The Pass changes neither pose
nor horizon; it creates the additional hidden observation required to evict a
Book record from an exact K=2 observation window. Final hiddenness is still
mandatory. Offline tests cover first-turn visibility, final hiddenness, exact
K=2 eviction, and the evaluator-only stale relocation trigger after Pass.

The half-turn can leave a direct baseline 180 degrees from the frozen route
entry. `phase5-shared-search-entry-alignment-v2` is a common target-free
successor that deterministically accepts 90- or 180-degree yaw error from the
planner-safe pose and uses at most two 90-degree rotations. It does not consume
object identity/coordinates, memory, anchor/support, route coordinates or
evaluator state. Existing one-turn behavior is preserved. Failure to converge
within two actions still invalidates the episode. The next real gate is a fresh
v2 isolation run from a new clean pushed revision; no v1 row is reused.

#### FloorPlan303 gate v2 stop and six-configuration distraction v4 gate

The clean `2162095` gate-v2 no-memory row executed both rotations and Pass
successfully, with setup and information-boundary checks passing. The exact
initial Book was nevertheless still visible after the half-turn. There was one
initially visible Book and no instance substitution. The frozen view's roughly
60-degree downward horizon and near-field geometry therefore invalidate the
assumption that yaw-only distraction guarantees hiddenness. The row is excluded
and cannot be reused. Public stop evidence is
`docs/evidence/phase5_r1_distraction_successor_gate_v2_stop.json`.

`phase5-book-distraction-v4` derives a bounded alignment to absolute horizon
0 only from the planner-safe initial `cameraHorizon`, using the already audited
0.001-degree normalization rule. It executes the fixed half-turn, the derived
LookUp/LookDown actions, and one final Pass. It never branches on Book
visibility or consumes object identity/coordinates, memory, evaluator state,
anchor/support, route graph or candidate outcome. Final exact-target hiddenness
remains mandatory.

Because distraction v4 can differ from the frozen route entry in both horizon
and yaw, `phase5-shared-search-entry-alignment-v3` deterministically restores
one or two 30-degree horizon steps followed by one or two 90-degree yaw steps,
using planner-safe pose only and a total four-action cap. Any off-grid error or
nonconvergence fails closed.

The next real gate covers all six frozen R1 configurations in declared order.
It runs one no-memory row per scene and the full three-variant triplet on the
previously failing FloorPlan303, for eight excluded short episodes total. Each
episode ends exactly after its derived distraction template and tests
hiddenness, K=2 readiness, action success, information boundary and exact fixed
actions; it does not test pickup/task success or enter formal aggregation. Stop
on the first failure. A pass is required before any formal readiness successor.

#### Six-configuration distraction coverage result

Clean pushed revision `cdd7042` completed all eight declared short episodes.
Every native action succeeded, every exact initial Book was hidden after its
3--5 action template, every progress controller entered `reacquire_book`, and
every information-boundary/audit check passed. FloorPlan303 reproduced the same
five-action boundary for no-memory, K=2 and object-memory. The other five scenes
passed their predeclared no-memory coverage rows. No pickup/task-success or
memory-effect result was evaluated, and all rows remain excluded from formal
aggregation. Public evidence is
`docs/evidence/phase5_r1_distraction_coverage_gate_v1.json`.

This pass closes the R1 distraction eligibility gap that invalidated formal-v2.
It authorizes only a new no-THOR readiness protocol. That successor must keep
the 54-cell matrix, bind distraction-v4 and entry-alignment-v3 in every public
R1 contract, add their policy/limit fields to the required metric schema,
retain the conditional K=2 audit, hash-freeze this gate evidence, and keep
formal execution disabled until a separate readiness result and authorization
overlay exist.

### Privacy-preserving real formal manifest v3 precommit

`phase5-real-thor-manifest-v3` preserves the exact 54-cell v2 matrix, runtime
sets, panel/configuration/variant order, controller settings, 2048 action bound,
no-image output and privacy boundary. It is a complete new protocol: no v2
episode or readiness artifact is reused. The R1 cells publicly bind
`phase5-book-distraction-v4`; R2 cells retain the inert historical v1 Book
policy because they do not run the Book task.

Metric schema v4 adds the episode Book-distraction policy and shared route-entry
alignment policy/limit to the required metrics. The executor requires
`phase5-shared-search-entry-alignment-v3` with a four-action cap. The K=2
eviction integrity check is conditional: it is mandatory once the task reaches
Book or Cup reacquisition, but a matched task outcome before that stage is not
converted into an integrity failure. All previous setup/intervention, route,
private-log, invalid-action, dirty-revision and information-flow fail-closed
rules remain.

The v3 base is readiness-only and sets
`formal_execution_authorized=false`. It hash-freezes both formal-v2 stop
evidence and the successful six-scene distraction coverage evidence, plus the
current task/planner/runner/search/formal executor sources and the unchanged
R1/R2 runtimes. Its public manifest must contain no start/target/anchor/support
coordinates, object identities or native evaluator actions. A clean pushed
no-THOR readiness must reconstruct all 54 public cells and join all 12 private
runtimes before a separately tracked v3 authorization overlay is allowed.

#### Formal v3 readiness and execution authorization

Clean pushed revision `ca31582` passed the no-THOR v3 readiness gate. It
reconstructed all 54 cells, joined all 12 private runtimes and verified all 18
action-only routes. The public manifest digest is `2fc10000...17af`; private
runtime material was not serialized, formal execution remained disabled and no
AI2-THOR or memory episode started. Public evidence is
`docs/evidence/phase5_real_formal_readiness_v3.json`.

`phase5-real-thor-formal-execution-authorization-v3` is a separately versioned
minimal overlay. It hash-binds the immutable readiness-only v3 base, the public
readiness evidence/revision/digest and a thin authorization launcher. The
launcher validates that binding, changes only `formal_execution_authorized` in
memory, repeats the v3 precommit and 12-runtime readiness on the current clean
pushed revision, and then invokes the already readiness-frozen executor. It
cannot override panels, configurations, variants, task policies, routes,
controller settings, the 2048 limit, metrics, output policy or stop rules.

The authorized run must use a new output directory and start at cell 1. Resume,
selective reuse, images, GUI and evaluator-debug output remain prohibited. An
integrity failure stops and invalidates the partial matrix; an integrity-valid
task failure remains an experimental outcome and does not authorize selective
rerunning.

#### Formal v3 invalidation and target-lock recovery successor gate

Clean pushed revision `983217d` stopped at cell 15 of 54. Cells 1--14 were task
successes, including the previously failing FloorPlan303 triplet. Cell 15,
FloorPlan306 R1-stable object-memory, visibly reacquired the Book and passed the
information boundary, setup and route checks, but its native pickup at camera
horizon 0 failed with the pickup-collision category. The matched no-memory and
K=2 controls picked successfully from the same fixed position/yaw/standing
state after common entry alignment restored camera horizon -30.

The failure exposed two shared target-lock-v1 defects. Its recoverability test
searched the full native stack trace and matched an internal method-name
substring, misclassifying collision as a distance/angle failure. After its
six-action approach budget exhausted, suppression returned control to the
ordinary visible-target planner, which retried pickup until the 2048 limit.
The formal audit then correctly stopped on the nonzero native-action integrity
counter. Public evidence is
`docs/evidence/phase5_real_formal_pilot_v3_invalidated_stop.json`; all 15 rows
are excluded and cannot be resumed or reused.

Before another formal protocol, a versioned shared target-lock interaction
recovery must be pre-registered. It must classify only the first-line ordinary
simulator reason, use no evaluator/private state or hidden target coordinate,
be identical for all memory variants, restore a fixed planner-safe interaction
horizon under a small action cap, retry pickup only within a total bound, and
terminate with an explicit task failure rather than falling through to an
unbounded ordinary-planner loop. Offline contract/privacy/budget tests and one
excluded FloorPlan306 object-memory isolation probe are required before a new
readiness protocol is allowed.

`phase5-shared-target-lock-v2` implements that successor. Collision recognition
uses only the first line of the ordinary simulator error and therefore cannot
match method names in the native stack trace. On `collide`/`clip into`, it
normalizes the planner-visible current camera horizon with 0.001-degree
tolerance, deterministically emits 30-degree LookUp/LookDown actions toward the
fixed -30-degree pickup horizon, caps that sequence at four actions, and permits
one pickup retry. Recovery actions contain only an action name. They do not
consume memory/variant, target coordinates or identity, anchor/support,
candidate outcome, reachable graph or evaluator state. A second collision,
off-grid/unavailable horizon recovery, recovery-action failure or target loss
sets a terminal target-lock reason; the runner stops the episode before any
ordinary-planner fallthrough.

The pre-registered real gate runs exactly the formerly failing FloorPlan306
R1-stable object-memory cell, excluded from aggregation, with a 64-step ceiling
and no image/GUI/debug output. It must exercise the exact target-lock subsequence
`PickupObject(fail) -> LookUp(success) -> PickupObject(success)`, with horizons
`0 -> 0 -> -30`, exactly one failed interaction/invalid native action, exactly
one recovery action/attempt, zero terminal failures, task success and a passing
information boundary. It freezes the v3 stop evidence, v2 policy/config,
runner/contracts and unchanged R1 runtime/route. This isolation gate is a
mechanism-repair check only, not a memory comparison or formal result.

Clean pushed revision `623ec53` passed that exact isolation gate in nine
evaluated actions. The target-lock subsequence was
`PickupObject(false) -> LookUp(true) -> PickupObject(true)` at planner-safe
horizons `0 -> 0 -> -30`. It recorded one native failed interaction/invalid
action, one recovery action and attempt, zero terminal failures, task success,
and a passing information boundary. The recovery directive contained only its
action name. Public evidence is
`docs/evidence/phase5_r1_target_lock_recovery_gate_v2.json`; the episode remains
excluded and supports only the repaired mechanism.

This pass authorizes design of a fresh formal-v4 readiness protocol, not direct
execution. That protocol must bind target-lock-v2 and add its policy, limits,
recovery and terminal counters to the required metrics. It must distinguish an
action-space/schema-invalid planner decision (integrity failure) from a legal
planner action that THOR rejects (recorded performance outcome). Route action
failures, setup/intervention errors, information leakage and invalid planner
decisions remain fail-closed. No formal-v3 row is reusable.

### Privacy-preserving real formal manifest v4 precommit

`phase5-real-thor-manifest-v4` starts a completely fresh protocol while keeping
the exact 54-cell matrix, panel/configuration/variant order, R1/R2 frozen
runtimes and routes, controller settings, 2048 episode ceiling and no-image
output of v3. Every cell publicly binds `phase5-shared-target-lock-v2`; R1 also
keeps distraction-v4 and route-entry alignment-v3. No v3 row or output is
reused.

Metric schema v5 has 64 required fields. In addition to v4, it requires the
target-lock policy, canonical -30-degree interaction horizon, four-action/one-
retry bounds, recovery action/attempt counts, terminal-failure count, and a
separate `invalid_planner_decision_count`. `invalid_action_count` continues to
record schema-valid actions rejected by THOR and remains a performance metric.
Planner action-space/schema violations increment the separate counter and fail
integrity; route-controlled failures retain their dedicated fail-closed
counters. A bounded terminal target-lock failure is a task outcome, like other
task failures, provided every integrity audit remains valid.

The readiness-only base sets formal execution false and hash-freezes the v3
invalidated stop, the successful real target-lock-v2 isolation evidence, the
successful R1 distraction gate, all public/private runtime loaders and route
registries, and current runner/task/planner/contracts/search/target-lock/formal
sources. Its no-THOR readiness must reconstruct 54 public cells, verify all 64
metrics and join all 12 private runtimes on one clean pushed revision. A
separate hash-bound authorization is required afterward; readiness itself may
not start an episode.

#### Formal v4 readiness and execution authorization

Clean pushed revision `2a18ea5` passed the no-THOR v4 readiness gate: all 54
public cells, 64 required metrics, 12 private runtime joins and 18 action-only
routes were reconstructed. The public manifest digest is
`51ef356e...b641d`. No private runtime material was serialized, execution
remained false, and no THOR or memory episode started. Public evidence is
`docs/evidence/phase5_real_formal_readiness_v4.json`.

`phase5-real-thor-formal-execution-authorization-v4` separately hash-binds the
immutable v4 base, readiness evidence/revision/digest and a thin post-readiness
launcher. The launcher changes only the in-memory execution flag, repeats
precommit/readiness on its current clean pushed revision, and invokes the
already frozen v4 executor. Its whitelist cannot alter matrix/order, runtime,
task policies, controller, 2048 ceiling, 64 metrics, output or stop rules.

The authorized run must start from cell 1 in a new output directory. It may not
resume or selectively reuse any v2/v3/partial cell. Images, GUI and evaluator
debug remain disabled. Integrity failure stops and excludes the partial matrix;
an integrity-valid task failure or legal native action rejection remains a
recorded experimental outcome.

#### Formal v4 invalidation and route-action recovery gate

Clean pushed revision `b6aae91` stopped at cell 31 of 54. Cells 1--30 were task
successes, including all 18 R1-stable cells, the repaired FloorPlan306 target-
lock cell and the first four R2 configuration triplets. Cell 31, FloorPlan10
R2-stable no-memory, completed its 12-action shared subgoal and matched the
fallback entry. At fallback coverage index 200, the exact frozen `MoveAhead`
was rejected because a scene obstacle blocked translation. Planner validity,
information boundary and setup passed; the dedicated route-action-failure
counter correctly stopped execution. Public evidence is
`docs/evidence/phase5_real_formal_pilot_v4_invalidated_stop.json`; all 31 cells
are excluded and cannot be reused.

The same 512-action route passed qualification, fresh-reset replay and reset
restoration, so the next gate tests a general transient execution successor
rather than altering the route or increasing 2048. It must be shared by every
memory variant and both frozen-route roles, consume only the failed ordinary
route action/result and fixed constants, issue one `Pass` stabilization action,
then retry the exact same frozen action once without advancing the cursor. It
must use no target/object/obstacle identity or coordinates, memory, evaluator
state, candidate outcome or reachable graph, and must retain a small total
episode recovery cap. A failed stabilization/retry remains fail-closed. Offline
determinism/privacy/budget tests and one excluded FloorPlan10 no-memory replay
are required before another formal readiness protocol.

#### Shared route-action recovery v1 precommit

`phase5-shared-route-action-recovery-v1` implements that successor without
changing either frozen route. A failed ordinary coverage action leaves the
cursor fixed, emits exactly one `Pass`, and retries the exact same action once.
The mechanism is shared by all three memory variants and by fallback/subgoal
route roles. It has an episode-wide cap of four attempts/eight recovery actions;
failed stabilization or retry is terminal. Recovery directives contain only the
existing public route contract, phase/index and action. Target/object/obstacle
identity or coordinates, memory, evaluator state, reachable graph and candidate
outcome remain forbidden.

Offline state, planner, runner, privacy and fail-closed tests pass for all three
variants. Full repository regression passes 368 tests plus 70 subtests. The old
v4 authorization is intentionally hash-invalid under this successor and cannot
be reused. The next pre-registered real gate is one excluded FloorPlan10 R2
no-memory replay, max 2048 and no images/GUI, requiring coverage index 200 to
produce `MoveAhead(false) -> Pass(true) -> MoveAhead(true)`, task success and
zero terminal recovery failures. It is not a formal result or memory comparison.
The first launcher invocation was rejected before THOR reset because the runner
config omitted the already-frozen subgoal route ID; no episode or environment
action ran. The launcher now declares both frozen R2 route IDs before retry.

The clean pushed retry at `1553b66` exercised the intended mechanism but did
not pass. Coverage index 200 produced `MoveAhead(false)`, the fixed `Pass`
succeeded, and the exact `MoveAhead` retry failed with the same blocking class.
The runner terminated at step 217 with one recovery attempt/two recovery
actions, zero recovered failures and one terminal recovery failure. Setup,
planner validity and the information boundary passed. Therefore the blocker is
classified as persistent route obstruction rather than transient settling.
Public stop evidence is
`docs/evidence/phase5_r2_floorplan10_route_action_recovery_gate_v1_stop.json`;
the episode remains excluded. Automatic execution stops here. Before formal-v5,
the protocol must choose and pre-register either conservative scene exclusion
plus a replacement qualified R2 route, or a shared persistent-blocked-action
successor. The existing `Pass` policy is not sufficient evidence for a rerun.

#### R2 conservative replacement protocol v1

FloorPlan10 is excluded rather than allowing a blocked route action to be
skipped. The retained R2 order is FloorPlan3, 4, 6, 7 and 12. Replacement
qualification resumes in untouched ascending kitchen-scene order at
FloorPlan17 and may continue through FloorPlan30, stopping after the first
qualified replacement. It reuses the v6 stable-start, first-12 frozen candidate
and target-independent budgeted visual fallback rules. No memory variant,
image, GUI or formal statistic runs during qualification.

A native qualification pass is no longer sufficient for replacement freeze.
The candidate must then pass a separately frozen production-equivalent
no-memory Runner gate at max 2048 with task success, information-boundary pass,
zero subgoal/fallback route failures and zero shared route-action recovery
attempts/actions. This extra gate directly addresses the FloorPlan10 gap between
qualification replay and production execution. The replacement may enter a new
six-configuration runtime set only after both gates pass; prior runtime-v2 and
formal-v4 artifacts remain immutable. Offline focused tests pass 16/16 and the
full repository regression passes 375 tests plus 70 subtests.

FloorPlan17 was the first scene attempted under this order and candidate 1
passed native qualification plus fresh-reset replay. The public action-only
contract has a four-action subgoal route and 212-action/13-viewpoint fallback;
47 of 50 audited starts were stable and reset restoration passed. It remains a
candidate, not a frozen replacement: `production_equivalent_gate_passed` and
`replacement_freeze_allowed` are false. Public evidence is
`docs/evidence/phase5_floorplan17_r2_replacement_qualification_v7.json`.

The next gate is exactly one excluded FloorPlan17 no-memory Runner episode. It
hash-binds the public candidate and ignored evaluator-only start, uses max 2048
with no images/GUI, and requires task success, information-boundary pass, zero
subgoal/fallback route failures and zero route-action recovery. Focused tests
pass 12/12; the full repository regression passes 381 tests plus 70 subtests.

#### FloorPlan17 production-equivalent replacement gate

Clean pushed revision `ba8f4d9` passed the single excluded FloorPlan17
no-memory Runner gate in nine actions. Task success and the information
boundary passed; invalid actions, subgoal/fallback route failures, shared route
recovery attempts/actions/terminal failures and target-lock interaction
recovery were all zero. This closes the qualification-versus-production gap
that invalidated FloorPlan10 without changing the routes or 2048 ceiling.

Public evidence is
`docs/evidence/phase5_r2_floorplan17_production_gate_v1.json`. It contains no
coordinates or object identity. The result authorizes FloorPlan17 to replace
FloorPlan10 in a new R2 runtime-v3 containing FloorPlan3, 4, 6, 7, 12 and 17.
It is an excluded engineering gate, not a memory comparison or formal result;
runtime-v2 and all prior formal artifacts remain immutable.

#### R2 conservative replacement runtime-v3 freeze

Runtime-v3 is a new set rather than a mutation of runtime-v2. Its fixed order
is FloorPlan3, 4, 6, 7, 12 and 17. FloorPlan10 is absent, and FloorPlan17 is
admitted only because both its native qualification and excluded production-
equivalent no-memory gate passed. The freeze hash-checks those gate artifacts
and the retained historical inputs.

The generated registry contains six public runtime references and 12 action-
only routes. The ignored evaluator-only registry has private-set digest
`9bbbd2d4...859f`; two consecutive freezes produced identical public and
private hashes. All six joined runtimes load, focused tests pass 19/19 and the
full repository regression passes 388 tests plus 70 subtests. No simulator or
memory variant ran, and runtime-v2 remains byte-frozen. Public
evidence is `docs/evidence/phase5_r2_runtime_freeze_v3.json`.

Before any new formal readiness, the next gate is one excluded FloorPlan17
runtime-v3 triplet in fixed no-memory, K=2 and object-memory order. It must use
the same task/start/routes/evaluator, stop on the first integrity failure, save
no images or evaluator debug and remain outside every formal aggregate.

#### FloorPlan17 runtime-v3 integration triplet precommit

`phase5-r2-runtime-v3-integration-probe-v1` binds the new runtime-v3 registry,
FloorPlan17 qualification and production-gate evidence, current shared runner,
planner, search and memory-navigation sources. It runs exactly three fresh
episodes at max 2048 in no-memory, K=2, object-memory order and stops at the
first episode or information-flow audit failure.

Every variant receives the same frozen start, four-action ordered subgoal,
212-action target-independent fallback, task and evaluator. The gate requires
task success, route/digest identity, zero route execution/recovery failures,
the K=2 eviction event and exercised retrieval/guidance for object memory.
Shared entry recovery remains permitted and audited; native target-lock
recovery remains a bounded performance mechanism. Images, GUI, evaluator debug,
episode reuse and formal aggregation are disabled. A pass is integration
evidence only and authorizes planning the six-configuration excluded dry run;
it is not a superiority result. Focused tests pass 19/19 and the full
repository regression passes 394 tests plus 70 subtests.

#### FloorPlan17 runtime-v3 integration triplet result

Clean pushed revision `c60e9a6` completed all three excluded episodes with no
audit error. No-memory and K=2 each succeeded in nine steps using four subgoal
and two fallback coverage actions; K=2 eviction was observed. Object memory
also succeeded in nine steps with nine retrievals and two memory-guided actions
and did not enter the fallback. Every information boundary passed; invalid
actions, route-action recovery, entry recovery and target-lock recovery were
zero for all three variants.

Public evidence is
`docs/evidence/phase5_r2_runtime_v3_integration_probe_v1.json`. It establishes
that all three providers execute correctly and fairly through the replacement
runtime, including the intended K=2 eviction and object-memory paths. Equal
nine-step outcomes provide no memory-superiority evidence. The next gate is an
excluded 6-configuration x 3-variant runtime-v3 dry run; no prior episode may
be reused and formal readiness remains unauthorized.

#### R2 runtime-v3 six-configuration dry-run precommit

`phase5-r2-runtime-v3-six-configuration-dry-run-v1` is a fresh excluded 18-cell
matrix. Configuration-major order is FloorPlan3, 4, 6, 7, 12 and 17; within
each configuration the order is no-memory, K=2, object-memory. Every cell uses
the frozen runtime-v3 start, task, action-only routes and evaluator, with max
2048 and a fresh reset. No integration-probe episode is reused.

The existing triplet audit is applied unchanged to every cell: success and
information boundary are required, route/digest and recovery integrity remain
fail-closed, K=2 eviction must be observed and object memory must exercise
retrieval/guidance. Execution stops on the first audit failure. Images, GUI,
evaluator debug and formal aggregation are disabled. A complete pass can only
authorize design of fresh formal-v5 readiness; the dry-run rows themselves are
not reusable and do not constitute a benchmark or superiority result. Focused
tests pass 19/19 and the full repository regression passes 400 tests plus 70
subtests.

#### R2 runtime-v3 six-configuration dry-run result

Clean pushed revision `6cd45e1` completed all 18 excluded cells. Every task
succeeded, every information-flow audit passed, K=2 eviction occurred in all
six configurations and object-memory retrieval/guidance occurred in all six.
No frozen-route action recovery or terminal target-lock recovery was used. One
legal native action rejection occurred in the FloorPlan7 object-memory cell;
it remained an integrity-valid performance event and the task succeeded.

Descriptively, no-memory and K=2 had identical steps in every configuration
and mean 28.5. Object memory had mean 32.0: it was faster in FloorPlan4, tied
in FloorPlan17 and slower in four configurations. FloorPlan6 required 14 shared
entry-recovery actions after memory-guided departure. These excluded rows are
useful negative engineering evidence: memory guidance can avoid fallback yet
still cost more navigation. They are not a formal comparison and must not be
used to claim either benefit or harm.

Public evidence is
`docs/evidence/phase5_r2_runtime_v3_six_configuration_dry_run_v1.json`. A fresh
formal-v5 readiness design is now allowed, replacing only R2 runtime-v2 with
runtime-v3 while rerunning the complete 54-cell matrix from cell 1. No dry-run
or earlier formal cell may be reused.

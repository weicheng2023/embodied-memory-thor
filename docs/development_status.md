# Development Status

## Current status: Phases 0-6 complete

The accepted formal-v5 run completed 54/54 real AI2-THOR episodes on clean
revision `069dab5`, with 54 task successes, zero integrity errors, and all rows
accepted for the fixed aggregate. Hash-bound descriptive analysis on clean
revision `9dcf9b5` was byte-identical across two runs. The result is mixed:
object memory slightly reduced R1 stable reacquisition cost, increased overall
R2 stable action cost despite fewer rotations, and safely completed the stale
panel with five explicit record corrections. Public results are in
`docs/phase5_formal_results.md` and
`docs/evidence/phase5_real_formal_v5_descriptive_results.json`.

Phase 6 packages the architecture, research report, failure analysis,
158-word application abstract, and conservative 91/100 scorecard. Documentation
and result-consistency gates pass, as do 422 tests plus 70 subtests. No new
experiment or selective rerun was part of this documentation phase.

## Historical Phase 5 engineering log (began at Phase 5A1)

The manual Phase 4 protocol-v3 case completed successfully even though the
isolated live viewer reported `viewer_display_timeout`; all non-GUI artifacts and
the final summary survived. Phase 4V is therefore closed.

Phase 5A1 has begun offline. The real runner accepts no memory, exact K=2 short
memory, and persistent object memory behind the same deterministic planner. Unit
tests lock K=2 eviction, persistent/no-memory semantics, common record schema,
memory-guided action parity, and identical systematic fallback after eviction.
No Phase 5 AI2-THOR episode or comparative result has run. The ordered second
task, stale intervention, metrics, scene qualification, and frozen manifest remain
future gates before the single three-variant engineering dry run.

The provider and R1 slices pass 7/7 targeted tests and the complete offline suite
passes 67/67. The accepted Phase 4 Book task and its retry behavior remain
unchanged. A separate Phase 5
candidate uses `RotateRight -> LookDown -> LookUp`, requires Book to stay hidden,
evicts observation 0 from K=2, and preserves identical no/short fallback. This
sequence still requires real scene qualification before any matched comparison.

Phase 5A2 now adds the offline `thor_cup_after_coffee_subgoal` candidate. All
variants share CoffeeMachine search and visible toggle behavior, and Cup pickup is
audited as valid only after the toggle milestone. The runner uses task-specific
initial/retrieval targets, setup actions, and allowed actions, so the Cup task
cannot silently reuse Book setup. The shared visible-target policy approaches a
distant CoffeeMachine before toggling. Phase 5 targeted tests pass 11/11 and the
full offline regression passes 71/71. No real R2 or comparison episode has run.

Phase 5A3 now provides an injected evaluator-only stale Book intervention, a
separate `intervention.jsonl`, native-action leak prevention, visible-history
old-viewpoint miss detection, stale-record exclusion, common fallback, and
visible rediscovery/correction. Failed interventions stop with private diagnostics.
Phase 5 targeted tests pass 15/15 and the full offline regression passes 75/75.
The actual AI2-THOR 5.0.0 relocation action and
per-scene valid destinations are deliberately not frozen before qualification.

The first FloorPlan1 stale relocation anchor is now physically qualified, and
its exact 210-action target-independent route is integrated as a coordinate-free
public action sequence. The runner supplies the same coverage indexes/actions to
no memory, exact K=2, and object memory after a shared route-entry check based
only on observation-0 agent pose. Offline matched parity, leakage, route digest,
and route-failure tests pass; the Phase 5 related suite is 33/33 and the complete
offline regression is 93/93. This is not a
real memory result. The first-six R1/R2 qualification pool and one excluded real
three-variant dry run still block the formal matrix.

A subsequent metadata-only census stopped first-six work at a design blocker.
Across all 30 kitchens, only FloorPlan1 and FloorPlan7 contain a pickupable Book,
while all 30 contain a pickupable Cup and toggleable CoffeeMachine. The original
kitchen-only R1 first-six pool is therefore impossible. No further anchor trial
or memory episode ran. R1 scene-family scope must be revised and precommitted
before qualification continues; R2 presence alone is not full qualification.

The pre-outcome protocol decision is to retain Book and expand R1 to the ordered
living-room then bedroom pool in `configs/phase5_r1_scene_pool.json`. A dedicated
coordinate-free census script records presence feasibility without running an
agent. Full task and anchor qualification still require separate gates.

The expanded census passed at presence level: 35/60 candidates, zero reset
errors, with the first six fixed as FloorPlan201, FloorPlan202, FloorPlan203,
FloorPlan209, FloorPlan213, and FloorPlan224. None has a default-view visible
Book, so evaluator-only visible-and-pickupable start qualification is the next
gate; this is not a memory result.

That start gate passed 6/6 on clean revision `12978db`, but the subsequent
target-independent route gate passed only FloorPlan202: 225 actions versus the
frozen 240 maximum. The other five routes require 330-630 actions. No anchor or
memory episode ran after this finding. The next safe batch is to continue down
the already declared scene order and retain later candidates that pass both
start and route gates before spending compute on anchor trials.

The remaining 29-scene prescreen then completed on clean revision `a3da5aa`:
29/29 start-qualified, 24/29 route-qualified, and zero runtime errors. Across all
35 presence candidates, 25 fit the frozen route limit. The earliest six
route-eligible scenes are FloorPlan202 and FloorPlan301-FloorPlan305. The route
pool gate is cleared; relocation-anchor qualification is still pending for all
six, and no memory comparison has run. The complete offline regression remains
93/93 after the batch-tool addition.

The multi-scene anchor qualifier then passed 8/8 focused and 96/96 complete
offline tests. Its first real run on FloorPlan202 stopped the batch: 12/12
candidate placements passed physical QA, but 8 were never rediscovered and 4
were seen at route step 197 then lost after one approach action and not picked.
No anchor was frozen; FloorPlan301-FloorPlan305 did not run. The active blocker
is shared visual fallback capability, not relocation physics or scene supply.

The shared fallback now has an offline-tested target-lock/local-recovery
micro-policy. A currently visible pickupable target pauses coverage and is tried
immediately; recoverable distance/angle failures receive bounded approach, and a
target lost after approach receives at most 12 planner-safe local recovery
actions, beginning with `MoveBack` after a successful `MoveAhead`. The same
helper and action space are used by no memory, exact K=2, and object memory.
Ten focused tests and the complete 106-test offline regression pass, including a
runner fixture in which every variant follows `PickupObject -> MoveAhead ->
MoveBack -> PickupObject` and passes the information-boundary audit. Metric
schema `phase5-metrics-v2` adds target-lock and transient-loss fields.

This checkpoint is not a memory comparison and is not real-simulator recovery
evidence. AI2-THOR was not started, no image was saved, and the retained
FloorPlan202 failure record was not replaced. The optional candidate-4-only
probe was skipped because the current batch qualifier cannot safely select just
that candidate without widening this change. FloorPlan202 requalification and
the anchor/stale-panel gate remain blocked on one bounded real diagnostic or an
explicitly scoped single-candidate runner.

That explicitly scoped runner is now implemented as diagnostic-only qualifier
mode and was used exactly once on clean revision `e5c3533`: FloorPlan202 fixed
start 001, frozen geometry candidate 4, no other candidate, no memory variant,
no image, no fresh-reset replay, and no anchor freezing. Physical placement and
reset restoration passed. The common route rediscovered Book after action 197;
target lock then issued immediate `PickupObject` at action 198 and succeeded.
All 198 ordinary actions succeeded. The former successful `MoveAhead` followed
by visibility loss was therefore avoided rather than recovered from.

This is real single-case evidence that immediate target lock removes candidate
4's old failure path. Because transient loss never occurred, it is not real
evidence for the `MoveBack`/local-scan recovery branch. It also does not qualify
an anchor: fresh-reset replay was intentionally excluded, and the eight
previously never-visible candidates remain unresolved. No further THOR run was
started.

The next correction is precommitted before another placement outcome. Route v2
used 22 scan waypoints and 88 horizontal rotations but zero camera-horizon
actions. Route v3 adds one target-independent relative `LookDown` before the
complete route and one `LookUp` after it, keeping every move, waypoint, and yaw
scan unchanged. FloorPlan202 therefore changes from 225 to 227 actions, still below
the frozen 240 limit. A one-scene public contract binds the v3 route digest,
30-degree relative scan adjustment, action count, and existing private-start digest without
coordinates or object IDs. The first real gate must be the earliest previously
never-visible candidate (candidate 1), not a hand-selected success. No v3 real
outcome exists at this checkpoint.

Candidate 1 then passed the single real gate on clean revision `6a83736`: the
v3 route exposed Book after action 26 and target lock picked it at action 27,
with no failed action or image. Full FloorPlan202 qualification was therefore
run from the frozen beginning. Candidate 1 again passed physical placement,
common fallback pickup, fresh-reset placement replay, and reset restoration;
`FloorPlan202_R1_stale_Book_anchor_001` is frozen in the ignored private
registry. No memory variant ran.

Qualification stopped before FloorPlan301 because v3's `LookDown` is a relative
30-degree action, not an absolute camera-horizon setting. The six frozen starts
have different initial horizons, so applying the same relative action would not
produce a common scan view and could reach a camera limit. FloorPlan202 evidence
remains valid for its scene-bound v3 contract, but v3 cannot be copied to later
scenes. The next protocol must use planner-safe initial horizon to align every
configuration to one declared absolute scan horizon and restore it afterward;
then it must requalify from FloorPlan202 if a common first-six policy is required.

Route v4 is now implemented offline with an absolute `0`-degree scan-horizon
contract. It reads only the planner-safe initial `cameraHorizon`, emits a bounded
ordinary `LookUp`/`LookDown` alignment prefix, runs the unchanged target-
independent waypoint/yaw route, and appends the exact inverse actions to restore
the initial horizon on route exhaustion. Starts at -30, 0, 30, and 60 degrees
require 1, 0, 1, and 2 alignment actions respectively. Including restoration,
the worst overhead is four actions; a 225-action base remains 229/240.

Offline acceptance explicitly feeds the same v4 action-only directives to no
memory, exact K=2, and object memory and rejects target/anchor/candidate/private-
registry fields in planner input. A FloorPlan202-only public contract binds the
absolute horizon, existing start digest, 227 actions, and v4 digest before any
real outcome. The next real gate remains candidate 1, followed by full
FloorPlan202 requalification; FloorPlan301 is prohibited until both pass.
The v4-focused suite passes 30/30 and the complete offline regression passes
113/113; compile and planner-input audits also pass.

## Implemented

### Phase 0

- Python package scaffold
- Packaging and optional dependency metadata
- Safe environment-variable template
- Human-readable and JSON environment diagnostics
- Unit tests for diagnostic behavior

### Phase 1

- Common real/mock environment interface
- Deterministic kitchen `MockEnv` with interaction and navigation actions
- Lazy, failure-aware `ThorEnv` adapter
- Safe AI2-THOR-style object metadata normalization
- Human-readable and JSON scene-object inspection CLI
- Unit tests for mock state transitions, parsing, and controller adaptation

The real adapter is unit-tested with an injected controller-like object and has now been exercised against a live AI2-THOR 5.0.0 Unity runtime through Ubuntu 22.04 WSL2/WSLg.

### Phase 2

- Four validated YAML household tasks
- Required-object availability checks before execution
- Structured action validation and exception-safe execution
- Success evaluation based only on environment object state
- Transparent rule-based planner for all four mock tasks
- JSONL step logs and JSON episode summaries under timestamped output directories
- Success, steps, invalid-action count/rate, planning latency, episode latency, and failure reasons
- Unit and CLI verification of successful and max-step failure paths

### Phase 2R

- Separate agent observation and privileged evaluator-state interfaces
- Three-region seeded partial mock layout
- View-dependent visibility from region and orientation
- Visibility and interaction-distance preconditions with explicit failure codes
- Partial task that forces the Apple to leave and later re-enter observation
- Observation-only no-memory region-search baseline
- Explicitly privileged oracle debug upper bound
- Auditable pre/post-action observations and planner-received object IDs
- Successful CLI runs for seeds 0–2 with both planners

Phase 2R remains controlled E1 harness evidence and does not demonstrate a memory improvement before Phase 3.

### Phase 2.5

- Verified WSL2/WSLg setup with hardware-accelerated AMD Radeon 780M rendering
- Isolated Python 3.10.12 and AI2-THOR 5.0.0 environment with exact dependency record
- Reproducible `smoke_ai2thor.py` acceptance CLI
- Live FloorPlan1 and FloorPlan10 startup
- Real object metadata, agent pose, and visibility-change logging
- Successful rotation, movement, Book pickup, and CoffeeMachine toggle
- Intentional failed object interactions captured without crashing
- Two inspected RGB frames and sanitized E2 result evidence

Phase 2.5 is integration evidence only. It is not a memory experiment or a repeated simulator benchmark.

### Phase 3 implementation

- Exact-K short-term transition memory (`K=2` in the frozen pilot)
- Persistent visible-observation-derived object memory with provenance
- Structured action log and deterministic retrieval
- Explicit `suspected_stale` marking and visible-only correction
- One shared task/search planner parameterized by no, short-term, or object memory
- Capable no-memory systematic-search baseline
- Second ordered Book-after-DeskLamp task
- Evaluator-side Apple relocation outside `ActionSpace`
- Per-step before/retrieval/after memory evidence and information-leak audit
- Frozen six-layout, three-condition, three-variant pilot runner and manifest
- Unit, parity, two-task, and protocol-acceptance tests

The formal `phase3-v2` pilot completed 54/54 successful episodes from clean revision `1af6c9c`. All 54 ordinary information-leak audits, all 18 T2 ordered-subgoal audits, all 18 matched stale interventions, and all six ObjectMemory stale miss/recovery traces passed. See `phase3_results.md` for per-layout results and the documented v1 invalidation.

## Planned

- Phase 4: one real AI2-THOR episode engine with deterministic and OpenAI-compatible structured planners
  - controlled `thor_book_reacquire` closed-loop task using ordinary THOR actions
  - exact planner-safe input, memory provenance, action result, memory update, and evaluator-status trace
  - formal non-interactive and visual debug profiles over the same decision engine
  - aligned RGB frames and portable HTML trace, with hidden evaluator metadata stored separately
  - mode-parity and hidden-state-leakage acceptance tests
- Phase 5: experiments, metrics, and ablations
- Phase 6: architecture, research report, failure cases, and scorecard

Phase 4 planning does not establish real memory improvement: a controlled closed-loop trace remains E2 integration/information-flow evidence. Repeated matched real-simulator comparisons remain Phase 5 E3 work.

Phase 4 source, CLI, configuration, and a single bounded test case are staged.
The first live formal episode reached AI2-THOR but stopped at preflight with
`initial_visible_book_missing`: FloorPlan1's reset observation did not show a
Book. No planner call or environment action followed. The run also exposed that
preflight failures currently omit observation-0 RGB and leave `episode.jsonl`
empty. Phase 4 remains planned/unverified until deterministic setup and durable
preflight evidence are implemented and the same bounded gate is rerun.

Protocol v2 implements the deterministic safe-observation setup sequence and a
separate `setup.jsonl`. It diagnoses `event.frame` numerically in memory and does
not rely on desktop screenshots or save PNGs by default. One targeted local test
and the corrected single live case passed; full offline regression and mode-parity
acceptance remain pending.

This status page distinguishes implemented work from intended interfaces. Planned items must not be moved into the implemented section until their acceptance commands have been run.

### Phase 4V viewer hardening

Protocol v3 isolates OpenCV/Qt GUI calls in a spawned child process after a manual
`xcb` failure aborted an otherwise healthy debug episode after Step 1. Viewer
startup failure and mid-episode native death now degrade to non-GUI artifacts and
cannot change the planner trace or final task outcome. Seven targeted Phase 4 tests
and all 60 offline tests pass. A manual v3 visual rerun remains pending.

## Phase 5 protocol status

The real comparison protocol is frozen in `phase5_experiment_protocol.md` before
implementation or comparative runs. It requires two task structures, three fair
memory variants, six qualified configurations, stable and stale panels, and a
54-episode clean-revision formal matrix. Phase 5A implementation and qualification
must pass before the one-configuration engineering dry run; no Phase 5 result
currently exists.

The support-census blocker now has an offline-tested paired-causal successor.
Every `anywhere=true` support query has a fresh-reset measured-Pass control;
pair order alternates and only positive query-minus-control excess decides pose
effects. Absolute one-action jitter is diagnostic only. The frozen scope stays
FloorPlan202 plus FloorPlan301-305 and eight declared support types. Placement,
pickup, fallback, memory, images, and force actions remain disabled.
Successor-specific tests pass 8/8 (24/24 with adjacent census/replication
tests), and the complete offline regression passes 170/170. The real six-scene
census has not started, so support policy v3 and FloorPlan301 candidate 1 remain
blocked.
Paired-diagnostic/R2 focused tests pass 21/21 and full offline regression passes
244/244. The real two-arm diagnostic remains pending clean commit/push.

The clean `3ed2cbe` pair completed with full integrity but both arms exhausted:
0 degrees used 162 actions and +30 degrees used the same 160 spatial actions;
both had zero failures and zero Cup observations. Downward horizon is therefore
insufficient. The route audit shows the Cup's initial viewpoint node is neither
scanned nor traversed. It is merely within the configured 3-step/0.75 m radius
of a scan waypoint, demonstrating that nominal geometric coverage does not
guarantee visual coverage under occlusion. Work stops before FloorPlan6 and
memory variants pending a general capable-baseline fallback redesign.

The real successor then ran on clean revision `3b5e8d7`. FloorPlan202 (3/3
pairs) and FloorPlan301 (9/9) completed, but FloorPlan302 stopped after pair 3
of 9 at Shelf ordinal 1. The successful query had 0.261734 degrees more maximum
rotation change than its matched Pass control, above the frozen 0.1-degree
gate; position excess was below threshold and logical/identity state was
unchanged. The census is incomplete, policy v3 is not recommended, and
FloorPlan301 candidate 1 remains blocked. No placement, pickup, fallback,
memory, image, or later-scene run occurred. Post-run focused evidence tests
pass 9/9 and the complete offline regression passes 171/171.

Support policy v3 now replaces spawn-query census outcomes with a pre-outcome
semantic eligibility rule over the same eight previously declared types. No
type is excluded because of the Shelf stop. Qualification v3 isolates every
support query behind its own reset/setup, discards query-mutated state, and
performs a final clean reset before unchanged geometry-v2 and route-v4 planning.
Native placement, physical QA, common fallback, fresh-reset replay, and reset
restoration remain the anchor gates. Formal episodes still use frozen opaque
anchors and never query coordinates. Focused offline tests pass 18/18. No new
AI2-THOR run exists yet; the complete offline regression passes 174/174.
FloorPlan301 geometry candidate 1 is the next and only real gate after a clean
pushed precommit.

The first FloorPlan301 v3 launch on clean `1b9b8d3` stopped before environment
creation because the command supplied a retained start registry that does not
contain FloorPlan301. The correct already-retained prescreen source was located
read-only, but the run was not retried under the stop-on-problem rule. This is
not a candidate failure: resets, queries, planning, placement, fallback, replay,
memory, and images all remained zero. Candidate 1 is still pending. Focused
evidence tests pass 19/19 and complete regression passes 175/175.

The corrected FloorPlan301 v3 diagnostic then completed eight isolated queries
on clean `596e1c2`: Desk 882 coordinates, Dresser 441, and six Shelves 2,646.
After a clean reset, geometry v2 rejected all 3,969 as Book footprint crossing
the support boundary, so candidate 1 did not exist. No native placement,
fallback, replay, memory, image, anchor, full qualification, or later scene ran.
FloorPlan301 remains blocked on a new precommitted geometry/protocol decision.
Focused evidence tests pass 20/20 and complete regression passes 176/176.

Scheme B now has a native-first qualification-v4 implementation pending offline
acceptance. Semantic policy v3 remains fixed. Fresh-reset spawn queries only
generate coordinates; AABB boundary/overlap calculations rank candidates but
cannot reject them. Only invalid/duplicate/under-distance points are excluded.
The first 12 candidates are frozen before outcomes and native physical QA,
common fallback, fresh-reset replay, and restoration decide acceptance. No Book
rotation, margin change, memory run, image, or later scene is authorized.
Focused tests pass 22/22 and complete regression passes 178/178. The real v4
batch has not started.

The clean `548c7ce` native-first v4 batch exhausted 12/12 frozen candidates.
All were Shelf; every native placement failed because the scene wall blocked
the spawn area. The Book never moved, fallback/replay did not run, restoration
passed 12/12, and no anchor was frozen. The fixed prefix therefore lacked
support-type coverage. A continuation requires a separately precommitted
balanced sampler; candidate 13 cannot be appended. Result-focused tests pass
23/23 and the complete offline regression passes 179/179.

Qualification v5 is the separately versioned type-balanced successor. It does
not append or pool v4. Candidate construction remains independent of native
outcomes: each present support type retains v4's within-type advisory rank, and
types are round-robined in the eight-type semantic policy order. In
FloorPlan301 this will alternate Desk, Dresser, and Shelf, giving four prefix
positions to each when all 12 are needed. Native gates, fresh resets, route,
margin, orientation, action boundaries, privacy, and stop-at-first-full-anchor
remain unchanged. Offline acceptance is pending.
Focused v5 acceptance now passes 25/25 and the complete offline regression
passes 181/181. The real v5 batch has not started.

The clean `d3e8ca1` v5 batch completed all 12 balanced trials: Desk 4,
Dresser 4, Shelf 4. Native placement succeeded 0/12; ten spawn areas were
blocked by scene wall geometry and two by an existing object. The Book never
moved, fallback/replay correctly stayed at zero, and reset restoration passed
12/12. No anchor, memory run, image, formal episode, or later scene exists.
This removes the Shelf-only alternative explanation but does not make
FloorPlan301 feasible. FloorPlan302 requires a separately precommitted
scene-level failure-and-skip rule.
Result-focused tests pass 26/26 and the complete offline regression passes
182/182.

Qualification v6 precommits the scene-level successor rule for FloorPlan302.
Only complete balanced-prefix exhaustion with no fatal, query, route, or reset
restoration failure permits skipping a failed predecessor. FloorPlan301 v5
meets that rule; runtime/integrity failures never permit a skip. The next scene
is fixed as FloorPlan302 by the declared order. Candidate ranking and all native
gates are unchanged, but a clean coordinate-free route-v4 precommit must pass
and be committed before any FloorPlan302 placement. This contract authorizes no
later scene, memory agent, image, force action, or Book rotation. Offline
acceptance is pending.
Focused transition tests pass 27/27 and the complete offline regression passes
183/183. FloorPlan302 route-only construction has not started.

FloorPlan302 route-only construction passed on clean `a9ce79f`: 61/240
actions, absolute scan horizon 0 degrees, and route digest
`8844fb4f2424b3b143ffcf2de8c58f249ab5ba35206289a0e11d4b60f1e9400a`.
It used no target/anchor input and ran no support query, placement, memory agent,
or image capture. The coordinate-free scene contract is prepared; offline
acceptance and a clean push remain required before placement.
Route-contract tests pass 28/28 and the complete offline regression passes
184/184.

FloorPlan302 qualification v6 then fully passed on clean `90a1ec7` at the
first balanced candidate (Bed). Native placement moved the Book 2.007788 m,
made it invisible from the old view, stayed stable for three samples, preserved
the expected support relation, and introduced no non-support overlap. The
common fallback rediscovered at step 20 and picked up at step 21 with no failed
action. Fresh-reset replay and reset restoration passed, so one opaque anchor
was frozen. No memory agent, image, force action, Book rotation, formal episode,
or later scene ran. This is anchor qualification evidence, not a memory result.
Result-focused tests pass 29/29 and the complete offline regression passes
185/185.

Qualification v7 fixes FloorPlan303 as the next declared scene after the
audited FloorPlan302 pass. The running state is two qualified scenes
(FloorPlan202, FloorPlan302) and one cleanly exhausted failure (FloorPlan301).
The sequence advances exactly one route-eligible scene after an audited pass or
clean exhaustion and never uses prior placement outcomes to rank the next
scene's coordinates. Candidate/gate behavior remains unchanged. A clean
coordinate-free FloorPlan303 route-v4 contract is required before any support
query or placement. No memory, image, force, rotation, or FloorPlan304+ work is
authorized. Offline acceptance is pending.
Focused transition tests pass 30/30 and the complete offline regression passes
186/186. FloorPlan303 route-only construction has not started.

The clean `37b7b8f` FloorPlan303 route-only run stopped before route
construction. Its retained start requested horizon 60 degrees, but AI2-THOR
returned `60.00001525878906`; the strict route-v4 upper-bound comparison
rejected the 0.000015-degree floating deviation. A reset/Teleport-only probe
confirmed Teleport success and the exact returned value. No support query,
placement, memory, image, anchor, or later scene ran. This is a route numerical
boundary bug, not FloorPlan303 infeasibility. The next gate is a separately
precommitted bounded normalization/tolerance fix and offline test of the
observed value; FloorPlan303 route-only must then restart from the beginning.
Stop-evidence tests pass 31/31 and the complete offline regression passes
187/187.

Route-v4.1 horizon tolerance is now precommitted but not yet real-run. A value
is normalized to the nearest 30-degree action grid only within 0.001 degrees;
the observed `60.00001525878906` becomes 60, while 60.5 and 61 remain invalid.
Exact-grid inputs preserve the v4 serialized route and therefore the established
FloorPlan202 and FloorPlan302 digests. A route that actually needs normalization
is marked v4.1 and records the bounded policy. Planner input schema and the
target/anchor/support/coordinate boundary are unchanged. FloorPlan303 native
qualification remains prohibited until its clean route-only rerun passes.
Focused route-v4.1 tests pass 34/34 and the complete offline regression passes
190/190. The real FloorPlan303 route-only rerun has not started.

The clean `acf6420` FloorPlan303 route-only rerun passed under v4.1. The real
60.000015-degree start normalized to 60, used two LookUp alignment and two
LookDown restoration actions, and produced a 100/240-action route with digest
`5d4de455b78ab05f17038cb7b5cf4dbc63c736d4b0c0fdf40e733545319c4254`.
The route remained target/anchor independent; no support query, placement,
memory, or image ran. A coordinate-free scene contract is prepared. Native
qualification remains blocked until this result passes offline tests and is
committed and pushed.
Route-contract tests pass 35/35 and the complete offline regression passes
191/191.

FloorPlan303 qualification v7 then fully passed on clean `9a79fc6` at the
first balanced Bed candidate. The same Book moved 1.241027 m, became invisible
from the old view, stayed stable for three samples, retained the expected
support relation, and had zero non-support overlaps. Common fallback rediscovered
at step 68 and picked up at step 69 with zero failed actions. Fresh-reset replay
and reset restoration passed, freezing one opaque anchor. No memory agent,
image, force action, Book rotation, formal episode, or later scene ran. R1 now
has three qualified scenes: FloorPlan202, FloorPlan302, and FloorPlan303.
Result-focused tests pass 36/36 and the complete offline regression passes
192/192.

FloorPlan304 is now the sole declared successor after the audited FloorPlan303
pass. The running state is three qualified scenes (FloorPlan202, FloorPlan302,
FloorPlan303) and one retained clean failure (FloorPlan301). Qualification v7,
type-balanced candidate ordering, native gates, privacy boundaries, and the
240-action route bound are unchanged. Before any support query or placement,
FloorPlan304 must pass route-only QA under absolute-horizon policy v4.1 and its
coordinate-free digest/count contract must be tested, committed, and pushed.
Only then is exactly one native qualification-v7 batch, capped at 12 balanced
candidates, allowed. No memory agent, image, FloorPlan305, force action, or Book
rotation is authorized. Focused transition tests pass 37/37 and the complete
offline regression passes 193/193. No THOR run for FloorPlan304 has started.

The clean `7495931` FloorPlan304 route-only run passed under absolute-horizon
policy v4.1. AI2-THOR reported a 30.000003814697266-degree start horizon, which
normalized to 30 within the frozen tolerance. One LookUp alignment and one
LookDown restoration action produced a 127/240-action route with digest
`6892b381c8957171367a3513d278ddbb5300b039dae50ed998a684bed0a3679b`.
The route used no target/anchor input and ran no support query, placement,
memory agent, or image. Route-contract tests pass 38/38 and the complete offline
regression passes 194/194. Its public coordinate-free contract is prepared;
native qualification remains blocked until commit and push.

After the route contract was pushed as `59b9f02`, the single authorized
FloorPlan304 qualification-v7 batch completed all 12 balanced trials without a
fatal process error, but no anchor qualified. The split was six Bed and six
Shelf candidates. All six Bed placements passed native placement and physical
QA, moving the Book 2.313--2.898 m, hiding it from the old view, remaining
stable, retaining the support relation, and adding no overlap. However, each
common fallback stopped at route action 109 when a LaundryHamper blocked a
coverage move. All six Shelf placements failed because an existing object
blocked the spawn area. Reset restoration passed 12/12; replay did not run.

This is not a clean scene-infeasibility exhaustion: the repeated fallback route
execution failure prevents the existing skip rule from admitting FloorPlan305.
No anchor, memory agent, image, force action, Book rotation, or later scene ran;
the qualified count remains 3/6. The next gate is a separately preregistered
diagnosis/protocol decision for shared fallback route execution. This scope
stops here. Result-focused tests pass 39/39 and the complete offline regression
passes 195/195.

A FloorPlan304 route-mutation diagnostic is now preregistered but has not run.
It pairs two fresh resets and replays the identical frozen 127-action route
directly, without planner or target-lock behavior. The baseline uses four Pass
actions; the placement condition uses frozen Bed candidate 1 followed by three
Pass actions, matching four pre-route environment actions. If baseline fails,
FloorPlan304 is marked route-failed and work stops. If only placement fails,
the effect is placement-induced and a general obstacle-recovery policy must be
separately preregistered before any rerun. Only if both complete is continuation
within FloorPlan304 allowed. The diagnostic cannot query supports, create new
candidates, recover obstacles, run memory/images, or enter FloorPlan305.
Diagnostic-focused tests pass 42/42 and the complete offline regression passes
198/198. The real paired diagnostic has not started.

The clean `336fa40` paired diagnostic produced a conclusive non-good result.
The original-scene control and frozen Bed-candidate-1 placement condition both
failed at the identical route action 109: a coverage `MoveAhead` blocked by a
LaundryHamper. Step 108 succeeded in both conditions. Placement itself
succeeded. The LaundryHamper remained non-moving with sub-micrometer drift, and
no non-Book object differed by more than 1 mm between pre-route conditions.
Therefore Book placement did not cause the route failure; FloorPlan304's frozen
route is not runtime-traversable.

The earlier route-only pass is retained but narrowed correctly: it proved
route construction, digest, horizon, and action bound, not execution of all
actions. No obstacle recovery was selected or run. No support query, new
candidate, planner, memory, image, anchor, or FloorPlan305 occurred. Per the
preregistered rule, FloorPlan304 is marked route-failed and execution stops.
Result-focused tests pass 43/43 and the complete offline regression passes
199/199.

Route-execution gate v1 now formalizes the FloorPlan304 result and the forward
protocol. FloorPlan304 is route-construction-eligible but
route-execution-ineligible; its valid fresh-reset baseline failure permits a
recorded scene skip to FloorPlan305. From FloorPlan305 onward every scene must
pass, in order: absolute-horizon route construction, full fresh-reset baseline
route execution, then native qualification. Baseline execution uses four Pass
actions and direct route replay with no placement/planner. An ordinary action
failure with valid contract and reset restoration is skippable; fatal, launch,
contract, precondition, or restoration failures stop. New native contracts are
machine-gated on matching public baseline-pass evidence. Memory, images, and
obstacle recovery remain disabled. Offline acceptance is pending.
Gate-focused tests pass 46/46 and the complete offline regression passes
202/202. FloorPlan305 has not started.

On clean `00fd480`, FloorPlan305 passed both pre-native gates. Route
construction produced a compatible absolute-horizon-v4 route with 115/240
actions and digest
`ee28505764f148e0e5b209810333e40cf84cd12d3259c5bc1113918da00dca09`.
The fresh-reset baseline then executed all 115/115 actions after four Pass
controls; precondition and reset restoration passed. No support query,
placement, planner, recovery, memory, or image ran. The native candidate
contract now binds both route and baseline evidence; offline acceptance and a
clean push are required before FloorPlan305 placement. Gate/result tests pass
47/47 and the complete offline regression passes 203/203.

After the route/baseline contract was pushed as `60aca71`, FloorPlan305 native
qualification passed its first balanced Bed candidate. The Book moved 2.855426
m, became invisible from the old view, stayed stable, retained the expected
support relation, and had zero extra overlap. Common fallback rediscovered at
step 38 and picked up at 39 with no failed action. Fresh-reset replay and reset
restoration passed, freezing one anchor. No memory, image, force, rotation, or
later scene ran. R1 now has 4/6 qualified scenes; FloorPlan306 is next under the
route-construction/baseline-execution gate.
Result-focused tests pass 48/48 and the complete offline regression passes
204/204.

On clean `344e70a`, FloorPlan306 passed route construction at 150/240 actions
with digest
`31b9037b881994ab80dc97f732e6b37ae95a330629d112831f78781fd5d3207f`,
then executed all 150/150 baseline actions after four Pass controls. The
precondition and reset restoration passed. No support query, placement,
planner, recovery, memory, or image ran. A baseline-gated native contract is
prepared; test, commit, and push are required before placement.
Gate/result tests pass 49/49 and the complete offline regression passes 205/205.

After `d475fee` was pushed, FloorPlan306 native qualification passed candidate
1 (Bed). The Book moved 3.492891 m and passed old-view invisibility, stability,
support, and overlap gates. Fallback rediscovered at action 94 and picked up at
95 with zero failed actions; replay and restoration passed. One anchor was
frozen, with no memory/image/later-scene run. R1 is now 5/6; FloorPlan307 is the
next gated scene.
Result-focused tests pass 50/50 and the complete offline regression passes
206/206.

On clean `ff72e77`, FloorPlan307 passed route construction at 113/240 actions
with digest
`ce1cdda7f8fbf30eaf8f37efce4a52a9a6b48a47c93111023b433ecddf6845eb`,
then passed all 113/113 baseline actions plus reset restoration. No horizon
alignment was needed. No query, placement, planner, recovery, memory, or image
ran. Its baseline-gated native contract is prepared; tests and push precede any
placement.
Gate/result tests pass 51/51 and the complete offline regression passes 207/207.

After `55cf276` was pushed, FloorPlan307 candidate 1 (Bed) fully qualified.
The Book moved 3.627789 m and passed invisibility, stability, support, and
overlap gates. Fallback rediscovered/picked at actions 39/40 with no failure;
replay and reset restoration passed. This freezes the sixth distinct R1 anchor.
The final ordered set is FloorPlan202, FloorPlan302, FloorPlan303,
FloorPlan305, FloorPlan306, and FloorPlan307. FloorPlan301 remains native-
candidate-ineligible and FloorPlan304 route-execution-ineligible. Scene
expansion stopped before FloorPlan308. An evaluator-only merged registry tool
and coordinate-free six-scene manifest are prepared; this is still anchor
qualification, not a memory comparison.

The six private source registries were then merged offline with all scene,
digest, public-pass, and one-anchor uniqueness checks passing. The ignored
evaluator-only registry contains six anchors and has digest
`423cf8ef98d73b56d836edbda83563cf4ebdc0604063e1ccf9530f876f781d92`.
No coordinates enter public evidence or planner input.
Completion tests pass 55/55 and the complete offline regression passes 211/211.

The six frozen R1 configurations are now connected to the production episode
runner without publishing evaluator material. Each public configuration binds
an opaque anchor ID, start-pose digest, private-set digest, and coordinate-free
action-only route. A local evaluator-only loader verifies every digest, applies
the exact `TeleportFull` start before observation 0, and performs exactly one
`PlaceObjectAtPoint` intervention after distraction transition 3. Native setup
and intervention details go only to separate private logs.

An offline acceptance test exposed and fixed a real boundary defect: after
private teleport, AI2-THOR's `lastAction=TeleportFull` would otherwise enter
planner observation 0. The runner now restores only the reset observation's
safe last-action fields while retaining the post-teleport camera pose and
visible objects. All six private/public/start/route joins pass. The excluded
R1 production integration triplet is preregistered on FloorPlan202 in fixed
no-memory, K=2, object-memory order, with 260 steps, no images/GUI/debug state,
stop-on-first-failure, and no formal aggregation. R2 still lacks six qualified
real configurations, so this triplet cannot complete Phase 5B or unlock the
54-episode matrix. Focused tests pass 18/18 and full regression 215/215. No real
memory variant has run at this checkpoint.

The first real v1 R1 integration triplet ran from clean `a364289` and all three
variants succeeded in 31 steps with complete metric and information-boundary
audits. No memory and K=2 used the same 26 public coverage actions plus one
entry alignment; object memory used one stale-memory action, detected the old-
viewpoint miss, used the same 26 coverage actions, rediscovered/corrected the
record at step 30, and picked up at step 31. This is a stale-risk/recovery QA
result, not a memory-benefit result.

Post-run evidence review found a labeling defect: the top-level probe manifest
correctly excluded all episodes, but each generic runner manifest still said
`formal_acceptance_candidate`. Behavior, privacy, and metrics passed, but v1 is
not the final public evidence. Probe v2 preserves every behavioral choice and
adds explicit per-episode `included_in_formal_aggregate=false`,
`run_purpose=phase5_r1_production_integration_probe`, and
`evidence_status=excluded_engineering_probe`. V2 must pass tests on a clean
pushed revision and rerun the complete triplet; no selective episode reuse.
V2 label-focused tests pass 18/18 and the full offline regression remains
215/215; the clean-revision v2 rerun has not started.

The clean `1b97aab` v2 rerun passed all three variants with zero audit errors.
Each episode and the enclosing probe explicitly exclude formal aggregation and
use `evidence_status=excluded_engineering_probe`. Results match v1: 31 steps
for every variant; no/K=2 share one entry alignment plus 26 coverage actions;
object memory uses one stale record, records one old-viewpoint miss, runs the
same 26 coverage actions, corrects at step 30, and picks up at step 31. Public
coordinate-free evidence is
`docs/evidence/phase5_r1_production_integration_probe_v2.json`. R2 six-scene
qualification remains the next hard gate.

R2 qualification is now pre-registered as a dual-route real-scene gate. A
goal-qualified CoffeeMachine route is honestly labeled
`task_subgoal_navigation` with `qualification_goal_input_used=true`; its
runtime/planner representation is still action-only and coordinate-free. Cup
fallback remains a genuinely target-independent coverage route. The production
runner requires both routes together, completes the subgoal route before
interaction, invalidates route mismatch/failure or a missing CoffeeMachine at
the frozen endpoint, and records separate route metrics. The offline fixture
shows all three variants share subgoal actions while only persistent object
memory can avoid fallback after the ordered subgoal.

The new evaluator-only qualifier freezes at most 12 FloorPlan1 Cup/start and
CoffeeMachine/destination pose pairs before outcomes, then requires native
route execution, K=2 eviction, successful toggle, capable target-independent
fallback pickup, full fresh-reset replay, and reset restoration. It runs no
memory agent and emits a coordinate-free public summary plus private retained
diagnostics. Focused contract/route tests pass 23/23 and the complete offline
regression passes 220/220. The first real FloorPlan1
qualification remains blocked until this precommit is committed and pushed;
FloorPlan2 and later scenes are not authorized by this gate.

The clean pushed `aa6e08d` FloorPlan1 launch then stopped before any candidate
or task action: the first pickupable Cup in sorted object-ID order had no
standing interactable pose. Candidate pairs/trials were 0/0. No route, toggle,
fallback, target lock, memory variant, image, or FloorPlan2 run occurred. This
invalidates the too-strong target-selection assumption; it does not reject the
scene or establish an R2 result. The protocol must pre-register either
first-standing-interactable Cup selection across sorted Cup instances
(recommended) or non-standing start support before a new real launch. Public
stop evidence is `docs/evidence/phase5_floorplan1_r2_start_pose_stop.json`.

The recommended R2 start-selection revision is now adopted in code: sorted
pickupable Cup IDs are checked one by one, each after an independent fresh
reset, and the first Cup with a normalized standing interactable pose is
selected. Later Cups are not queried after a pass. This evaluator-only
feasibility gate runs before and cannot inspect route, toggle, fallback,
pickup, or memory outcomes. Query errors remain fatal; an all-fail scene keeps
the complete private audit. No downstream candidate-pair or task gate changes.
Offline tests and a clean pushed revision are required before the one allowed
FloorPlan1 rerun; memory variants and FloorPlan2 remain prohibited meanwhile.

The revised selection tests cover sorted order, fresh-reset isolation,
first-pass stopping, all-fail audit retention, and fatal query errors. The full
offline regression passes 223/223; no real v2 rerun has started yet.

The clean `b1f42ec` FloorPlan1 v2 rerun inspected its only pickupable Cup. The
pose query succeeded but returned zero poses, so the scene has no standing-
interactable Cup start under the registered rule. Candidate pairs/trials stayed
0/0 and no route/task/memory/image action ran. This is classified as
`scene_start_ineligible_no_standing_cup`, `scene_skip_allowed=true`; the next
legal scene is FloorPlan2 after the classification and kitchen-range gate are
tested, committed, and pushed. Public evidence is
`docs/evidence/phase5_floorplan1_r2_v2_scene_start_ineligible.json`.

Classification/range tests pass 8/8 and the full regression passes 225/225.
FloorPlan2 has not run yet.

On clean pushed `9ba7a0d`, FloorPlan2 also had one pickupable Cup whose
successful isolated pose query returned zero poses. It is classified
`scene_start_ineligible_no_standing_cup`, skip allowed, with candidate
pairs/trials 0/0. No route/task/memory/image/FloorPlan3 action ran. Public
evidence is `docs/evidence/phase5_floorplan2_r2_v2_scene_start_ineligible.json`.
FloorPlan3 is next only after this evidence is committed and pushed.

On clean pushed `318db5f`, FloorPlan3 fully qualified candidate 1. Its public
ordered-subgoal route has 6 actions and discloses evaluator goal use; its
target-independent fallback has 110 actions and no Cup/anchor input. K=2
eviction, native interaction, fallback pickup, fresh-reset replay, and reset
restoration all passed. No memory variant or image ran. Evidence is
`docs/evidence/phase5_floorplan3_r2_v2_qualification.json`; R2 qualified count
is now 1/6.

The qualified result is now wired into a public/private frozen R2 loader. The
public registry exposes only opaque IDs and digests; the ignored private
registry holds the native start and selected object IDs. Digest/scene/route
joins and ordered-start preconditions fail closed. The generic runner and CLI
now accept this evaluator setup with both action-only R2 routes. An excluded
three-variant production probe is precommitted for FloorPlan3 with no images,
GUI, evaluator debug, or formal aggregation and stop-on-first-failure. Offline
runtime, tamper, privacy, CLI, qualification, and ordered-task tests pass 18/18.
The complete offline regression passes 229/229. The probe has not run; it first
requires a clean committed and pushed revision.

The clean `a32a6bc` FloorPlan3 excluded R2 probe has now stopped at a real
object-memory integration failure. No-memory and K=2 passed in 13 steps with
six common subgoal actions and four fallback actions. Object memory reached the
140-step ceiling after 132 memory-guided heading actions, zero fallback actions,
and 131 repeated viewpoints. All privacy/evidence audits passed.

The trace shows a deterministic 90-degree quantization oscillation: a continuous
last-seen-position bearing falls between adjacent executable headings, but the
planner requires one-degree alignment, so it alternates left/right indefinitely
and retained memory prevents fallback. FloorPlan4 did not run. The failure is
recorded in
`docs/evidence/phase5_floorplan3_r2_production_probe_v1_stop.json`. Next work
must precommit and offline-test discrete-heading convergence and bounded
memory-to-fallback escape, then rerun all three excluded variants on a clean
pushed revision before R2 scene expansion resumes.

The fix is now precommitted as `phase5-memory-navigation-v2`: continuous memory
bearings are quantized to the configured 90-degree action grid, and a second
planner-safe guard suppresses a cited record after three memory-guided actions
without 0.05 m positional progress. Suppression exposes the unchanged frozen
fallback; a later visible-derived update recovers the record. The policy adds
no hidden state to planner input and is instantiated for every variant.

Probe v2 preserves FloorPlan3, both route digests, order, 140-step cap, and
excluded labels, with no v1 episode reuse. Focused tests pass 20/20 and full
regression passes 235/235. The full v2 triplet has not run; commit/push is the
remaining precondition.

The full v2 triplet then ran from clean pushed revision `29db132` and passed.
No-memory and K=2 again completed in 13 steps with six shared-subgoal and four
shared-fallback actions; K=2 eviction was confirmed. Object memory completed in
20 steps using 11 memory-guided actions, zero fallback actions, zero invalid
actions, and zero failed interactions. Its bounded escape did not trigger, so
the former oscillation was resolved by executable-heading quantization itself.
All three information-boundary audits passed.

This is integration evidence, not a positive memory result: in this excluded
single configuration, object memory took seven more steps than either control.
Public evidence is
`docs/evidence/phase5_floorplan3_r2_production_probe_v2.json`. The next allowed
gate is ascending R2 qualification beginning with FloorPlan4; no later memory
variants may run until the six-configuration runtime is frozen.

FloorPlan4 then qualified from clean pushed `4877f3e` on precommitted candidate
1. Its 11-action goal-qualified subgoal, 110-action target-independent fallback,
K=2 eviction gate, fresh-reset replay, and reset restoration all passed. No
memory agent or image ran. R2 qualification is now 2/6: FloorPlan3 and
FloorPlan4.

The one-configuration `frozen_runtime_v1` remains immutable because its private
digest is part of the completed FloorPlan3 integration probe. Qualified scenes
are recorded separately; after 6/6, a new six-configuration runtime-set version
will be frozen. FloorPlan5 is next.
Focused R2 runtime/qualification tests pass 25/25 and the full offline
regression passes 236/236.

FloorPlan5 v2 exhausted 12/12 candidate pairs at start preconditions. All
teleports and object/state checks passed except Cup visibility (8/12) and
CoffeeMachine hidden status (0/12). Because the prefix covers only Cup pose
orders 1-4 out of 92, this is not yet a valid structural scene exclusion.
FloorPlan6 remains blocked. A FloorPlan5-only exhaustive start-visibility
census is precommitted with fresh reset per pose and no route, interaction,
planner, memory, image, or formal result.
Focused census/R2 tests pass 16/16 and the full offline regression passes
239/239. The real census has not run and requires a clean pushed revision.

The clean `4f23dd0` census completed 86/86 pose trials and found four eligible
joint starts, first at within-run order 39. Thus FloorPlan5 is feasible and the
v2 pair prefix was incomplete. A 92-versus-86 cross-run pose-count difference
also rules out hardcoding an order/coordinate. Qualifier v3 now prefilters every
within-run standing pose using fresh-reset start booleans before freezing the
unchanged first-12 rank-balanced pairs. FloorPlan5-only rerun remains pending
commit/push; no memory variant is authorized.
Qualifier-v3/R2 focused tests pass 24/24 and the full offline regression passes
241/241.

FloorPlan5 v3 on clean `c26402b` found 5/92 joint-feasible starts but qualified
0/12 pairs. Two start views did not reproduce on trial reset. Ten candidates
passed subgoal/toggle and all 160-164 fallback actions with zero action failure,
but Cup was never visible and target lock never entered. A candidate-2 paired
0-degree versus +30-degree downward diagnostic is now precommitted; it changes
only the two horizon-boundary actions. FloorPlan6 and memory agents remain
blocked.

FloorPlan12 later qualified under R2 v4, bringing R2 to 3/6. FloorPlan13
stopped before trials because its 260 standing poses exceeded the v1
implementation guard of 256 and early-exit restoration was not established.
The separately versioned start-stability v2 / qualifier v5 successor now
pre-registers deterministic even-rank selection of 256 poses across the full
ordered set before outcomes and requires explicit restoration after query
errors. Offline acceptance and a clean push are required before any FloorPlan13
retry; no memory variant or formal aggregate is allowed.

The next registered gate is now the construction-only
`phase5-r2-budgeted-visual-fallback-v1` successor. It uses deterministic fixed
3-by-3 grid binning and fixed 0/+30-degree four-way scans, retains the 2048
cap, and has no target, identity, outcome, memory or variant input. Historical
exhaustive-fallback and FloorPlan3/4/12 qualification artifacts are hash-frozen.
After offline regression and a clean push, only FloorPlan6, 7, 8, 10, 13 and
16 may receive route-construction diagnostics in that order. The first pass
ends the batch before qualification; FloorPlan17 remains blocked.
The corrected FloorPlan6 diagnostic passed from clean pushed `cef5b78`: 26
viewpoints and 404 planned actions, with the same route digest as the initial
audit-bug run and successful reset restoration. No route action, qualification,
memory variant, image or FloorPlan7+ run occurred. The first-pass stop rule is
active. Result-evidence gates pass 11/11 and the full regression passes 275/275.

R2 qualification v6 is now precommitted as a hash-guarded adapter over the v5
qualifier. Only the visual fallback constructor/version, budgeted failure names
and coordinate-free public coverage metrics change; start stability, pairing,
subgoal/trial/replay, target lock and restoration remain v5 functions. Its
authorized order is FloorPlan6, 7, 8, 10, 13, 16, with no memory variants,
images, formal aggregate or FloorPlan17+. Focused precommit tests pass 28/28;
the full offline regression passes 281/281. A clean push is the remaining
real-run gate.

The first clean FloorPlan6 v6 attempt reached a successful candidate-1 native
trial and fresh-reset replay with restoration passed, but the adapter then
raised a `TypeError` while freezing its public route because its wrapper omitted
v5's positional helper argument. The run is not counted as qualified and its
episode will not be reused. The wrapper signature and regression test are being
corrected before a separately clean fresh-reset retry; no later scene ran.

The fresh FloorPlan6 retry on clean pushed `13467da` qualified candidate 1.
All 210 selected starts passed the 3/3 stability gate; 12 candidate pairs froze
before outcomes. The selected 13-action subgoal and 403-action/26-viewpoint
budgeted fallback passed the native trial, independent fresh-reset replay and
restoration. No memory variant or image ran. R2 is now 4/6; FloorPlan7 is next
after result evidence tests and a clean push.
FloorPlan6 v6 evidence gates pass 7/7 and the full regression passes 282/282.

FloorPlan7 then qualified candidate 1 from clean pushed `97ba881`: 187/192
selected starts were stable, 12 pairs froze before outcomes, and the 11-action
subgoal plus 685-action/47-viewpoint budgeted fallback passed native trial,
fresh replay and restoration. R2 is 5/6. No memory/image/formal run occurred;
FloorPlan8 follows only after result evidence and a clean push.
FloorPlan7 evidence gates pass 8/8 and the full regression passes 283/283.

FloorPlan8 on clean `42236d4` was a registered scene skip. It had 40/78 stable
starts and froze 12 pairs, with all budgeted routes constructed at 430--437
actions and 30 viewpoints. All 12 native trials failed the task-subgoal
postcondition before fallback execution; restoration passed. This is not
evidence against budgeted visual coverage. R2 remains 5/6 and FloorPlan10 is
next after the negative evidence is tested and pushed.
FloorPlan8 evidence gates pass 9/9 and the full regression passes 284/284.

FloorPlan10 on clean `ddd255b` qualified candidate 1: 53/74 stable starts,
12 pairs frozen before outcomes, a 12-action subgoal, and a 512-action/
37-viewpoint budgeted fallback passed native trial, fresh replay and
restoration. R2 qualification is complete at 6/6: FloorPlan3, 4, 6, 7, 10,
12. FloorPlan13/16 are no longer needed. No memory variant may run until these
six action-only configurations are frozen as a new runtime-set version.
The publication gate caught and corrected a five-action-code transcription
omission without rerunning THOR; the tracked configuration now exactly equals
the ignored public output. Evidence gates pass 10/10 and full regression
285/285.

The six-configuration runtime-freeze v2 tool is precommitted without modifying
runtime v1 or the shared v1 route registry. It validates six tracked public
sources, 12 action-only routes, ignored private starts and a bound private-set
digest. Focused runtime tests pass 9/9 and full regression passes 289/289. The
tool must be committed/pushed before deterministic registry generation; no
memory variant has run.

The first clean freeze attempt stopped before writes because the collector
expanded the shared FloorPlan3/4 private draft twice and correctly rejected
duplicate configuration matches. Source-path deduplication is now an explicit
tested gate; registry generation must wait for its clean pushed fix.
The deduplication fix passes 5/5 focused and 290/290 full tests.

Clean freeze from `92cc917` generated runtime set v2 successfully: six public
configurations, 12 coordinate-free routes, and ignored private digest
`386867...457f`. All six loader joins pass with route counts
6/110, 11/110, 13/403, 11/685, 12/512 and 9/1367. Public leakage audit and v1
preservation pass. No THOR or memory variant ran.
Generated-runtime gates pass 11/11 and full regression passes 291/291.

Runtime-v2 integration probe v3 is precommitted for one excluded FloorPlan6
triplet in fixed no-memory/K2/object-memory order. It hash-freezes the runtime,
routes, memory-navigation policy and v2 runner, and changes only the loader to
runtime v2. Focused gates pass 8/8 and full regression passes 294/294. A clean
push remains required before the real probe.

The clean `64cd8bf` v3 probe retained successful 60-step no-memory and K=2
episodes, each with 13 subgoal and 45 shared fallback actions; K=2 eviction and
all information-boundary audits passed. Object memory made 14 memory-guided
actions, its record was boundedly suppressed, and the frozen fallback then
failed closed because the agent was no longer at its captured route entry.
This is an excluded shared-search transition defect, not a THOR/render or
leakage failure, and none of the v3 episodes may be reused.

The registered `phase5-shared-search-entry-recovery-v1` successor reverses a
bounded trace of successful pose-action names before shared fallback. It is
identical for all variants, capped at 64, action-only, and consumes no target,
memory-record, anchor/support, outcome, graph or evaluator coordinates. Direct
baselines execute zero recovery actions. Probe v4 is a fresh excluded
FloorPlan6 triplet with unchanged runtime/routes/task/start/checker/140-step
cap. Focused recovery and v3/v4 gates pass 24/24; full regression remains the
pre-push gate and passes 302/302. No formal result or multi-configuration run
is authorized yet.

Clean pushed `6deb0aa` probe v4 passed the complete fresh FloorPlan6 triplet.
No-memory and K=2 were unchanged at 60 steps with zero entry-recovery actions;
object memory executed 14 memory actions, 14 inverse entry-recovery actions and
the same 45 fallback actions, succeeding in 88 steps. Every information audit
passed, no route-entry mismatch remained, and no v3/partial episode was reused.
This is successful integration repair but a negative single-scene memory
outcome, explicitly excluded from formal aggregation.

The original one-configuration Phase 5B dry run is now complete. A redundant
six-configuration excluded dry run will not be run. The next engineering task
is a real-runtime formal-manifest successor: the old v1 builder publicly embeds
raw start poses and does not bind the frozen R1 anchor/setup registry or R2
runtime v2/action-only routes. Formal execution remains prohibited until a
privacy-preserving 54-cell manifest plus executor and audits are precommitted,
offline-tested, committed and pushed.
Probe-v4 result-evidence gates pass 6/6 and the full repository regression
passes 303/303.

Formal-manifest v2 is now precommitted as a separate successor; historical v1
code is hash-frozen. The public matrix is exactly 54 action-only cells with
matched R1 stable/stale sets and the six R2 runtime-v2 configurations. It uses a
common 2048-step ceiling, metric schema v3, local ignored private joins, and a
fail-closed executor that keeps task outcome separate from integrity validity.
Its initial authorization is readiness-only: `--execute` must fail before
creating output. Offline gates currently pass 7/7; full regression and a clean
push are required before the 12-runtime readiness join may run. Full regression
passes 310/310. No formal episode has run.

No-THOR readiness on clean `eba1c1f` passed: 54/54 public cells, 12/12 private
runtime joins and 18/18 action-only routes were validated; no private runtime
material was serialized. Manifest digest is `441aad54...03515`. The base config
remained execution-disabled. The next change is a hash-bound authorization
overlay only; it must not change the matrix contract. No formal episode has run.

The separate execution-authorization overlay now hash-binds the immutable base
and readiness evidence and can change only the boolean execution gate plus
provenance. Any matrix field is rejected. Focused formal-v2 gates pass 9/9.
Full regression passes 312/312; commit and push remain before a fresh internal
readiness check and episode 1. No formal episode has run.

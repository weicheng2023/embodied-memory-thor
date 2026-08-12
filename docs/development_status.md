# Development Status

## Phase 5A1 started

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

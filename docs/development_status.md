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

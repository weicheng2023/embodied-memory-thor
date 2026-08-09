# Development Status

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

The implementation is complete, but formal Phase 3 results are claimed only after the 54 episodes run from a clean Git revision and `protocol_acceptance.json` passes.

## Planned

- Phase 4: mock and OpenAI-compatible planners
- Phase 5: experiments, metrics, and ablations
- Phase 6: architecture, research report, failure cases, and scorecard

This status page distinguishes implemented work from intended interfaces. It should be updated only after the relevant acceptance commands have been run.

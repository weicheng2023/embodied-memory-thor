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

The real adapter is unit-tested with an injected controller-like object. A live AI2-THOR Unity runtime is not yet verified on the current machine because the optional dependency is not installed.

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

Phase 2R remains controlled E1 harness evidence. It does not replace the planned live AI2-THOR smoke test or demonstrate a memory improvement before Phase 3.

## Planned

- Phase 3: short-term, object-state, and action-failure memory
- Phase 4: mock and OpenAI-compatible planners
- Phase 5: experiments, metrics, and ablations
- Phase 6: architecture, research report, failure cases, and scorecard

This status page distinguishes implemented work from intended interfaces. It should be updated only after the relevant acceptance commands have been run.

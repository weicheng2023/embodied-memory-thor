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

## Planned

- Phase 2: task configuration, rule-based execution, state-based evaluation
- Phase 3: short-term, object-state, and action-failure memory
- Phase 4: mock and OpenAI-compatible planners
- Phase 5: experiments, metrics, and ablations
- Phase 6: architecture, research report, failure cases, and scorecard

This status page distinguishes implemented work from intended interfaces. It should be updated only after the relevant acceptance commands have been run.

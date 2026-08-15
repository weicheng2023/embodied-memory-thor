# Application Abstract

## Copy-ready English version (160 words)

Embodied agents must act from partial observations while remembering objects
that have left view and revising memories when the environment changes. I built
Embodied-Memory-THOR, a lightweight AI2-THOR research pipeline, to study this
problem. The system separates planner-visible observations from evaluator-only
state, supports no memory, exact two-observation memory, and persistent object
memory, and records structured action, provenance, failure, and success traces.
After adaptive scene and policy qualification, I fixed and freshly ran 18
matched configuration cells across three panels under three memory variants,
for 54 executions. All executions succeeded, so success was saturated and the
informative comparisons were efficiency and recovery behavior. Persistent
memory modestly reduced reacquisition effort in the simple Book task, but
increased total action cost in the longer ordered Cup/CoffeeMachine task despite
reducing search rotations. It also detected and corrected five explicit stale
records. The result is conditional: remembering a target can reduce blind
search, but effective embodied behavior also requires efficient
memory-conditioned navigation and uncertainty handling.

## Claim boundary

This abstract describes a deterministic metadata-planner study with six matched
configurations per panel. It is a protocol-development case study with a fixed
final internal comparison, not an externally validated benchmark. It does not
claim statistical significance, visual perception performance, a SOTA method,
or physical-robot generalization.

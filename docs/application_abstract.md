# Application Abstract

## Copy-ready English version (164 words)

Embodied agents must act from partial observations while remembering objects
that have left view and revising memories when the environment changes. I built
Embodied-Memory-THOR, a lightweight and auditable AI2-THOR research pipeline, to
study this problem. The system separates planner-visible observations from
evaluator-only state, supports no memory, exact two-observation memory, and
persistent object memory, and records structured action, provenance, failure,
and success traces. Through an adaptive, audited protocol-development process, I
qualified real simulator scenes, then froze and freshly ran a 54-episode
comparison across Book reacquisition, an ordered Cup/CoffeeMachine task, and a
stale-memory condition. All episodes succeeded with no information-boundary
violations. Persistent memory modestly reduced reacquisition effort in
the simple Book task, but increased total action cost in the longer ordered task
despite reducing search rotations. It also detected and corrected five explicit
stale records. The project therefore shows both the value and limits of memory:
remembering a target can reduce blind search, but effective embodied behavior
also requires efficient memory-conditioned navigation and uncertainty handling.

## Claim boundary

This abstract describes a deterministic metadata-planner study with six matched
configurations per panel. It is a protocol-development case study with a frozen
final internal comparison, not an externally validated benchmark. It does not
claim statistical significance, visual perception performance, a SOTA method,
or physical-robot generalization.

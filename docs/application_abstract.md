# Application Abstract

## Copy-ready English version (158 words)

Embodied agents must act from partial observations while remembering objects
that have left view and revising memories when the environment changes. I built
Embodied-Memory-THOR, a lightweight and auditable AI2-THOR research pipeline, to
study this problem. The system separates planner-visible observations from
evaluator-only state, supports no memory, exact two-observation memory, and
persistent object memory, and records structured action, provenance, failure,
and success traces. I qualified real simulator scenes and ran a fixed 54-episode
comparison across Book reacquisition, an ordered Cup/CoffeeMachine task, and a
stale-memory relocation condition. All episodes succeeded with no information-
boundary violations. Persistent memory modestly reduced reacquisition effort in
the simple Book task, but increased total action cost in the longer ordered task
despite reducing search rotations. It also detected and corrected five explicit
stale records. The project therefore shows both the value and limits of memory:
remembering a target can reduce blind search, but effective embodied behavior
also requires efficient memory-conditioned navigation and uncertainty handling.

## Claim boundary

This abstract describes a deterministic metadata-planner study with six matched
configurations per panel. It does not claim statistical significance, visual
perception performance, a SOTA method, or physical-robot generalization.

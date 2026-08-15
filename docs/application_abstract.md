# Application Abstract

## Copy-ready English version (160 words)

Embodied agents act from partial observations while remembering objects that
leave view and revising stale memories. I built Embodied-Memory-THOR, an
AI2-THOR pipeline that separates planner-visible observations from
evaluator-only state and records action traces. Phase 5 compared no memory,
exact two-observation memory, and persistent object memory across 18 matched
configuration cells in three panels, producing 54 executions. Success was
saturated. Persistent memory modestly
reduced simple Book reacquisition effort, increased total cost in the longer
Cup/CoffeeMachine task, and corrected five stale records. Phase 7A froze
the policy and evaluated six first-eligible holdout scenes without
outcome-specific repair. All variants succeeded; object memory saved one
action in five scenes and tied once, but no translation or fallback was
exercised. Phase 7B tested five variants across those configurations. K=8
recent memory matched object memory on retention and action costs, while K=2
matched no memory. These bounded results suggest that the simple-task gain
depends on retention horizon; navigation and uncertainty handling remain
necessary.

## Claim boundary

This abstract describes deterministic metadata-planner studies with six matched
configurations per panel. Phase 5 is an engineered protocol-development case
study; Phase 7A is a frozen first-six holdout; Phase 7B is a narrow mechanism
ablation. None supports statistical significance, visual perception
performance, a SOTA claim, broad equivalence between memory representations, or
physical-robot generalization.

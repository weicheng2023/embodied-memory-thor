# Phase 7 Successor Studies

Current status: Phase 7A result frozen; Phase 7B pending

Phase 7 is additive successor research. It does not correct, extend, or replace
the accepted Phase-5 formal-v5 evidence.

## Study order

1. **Phase 7A — untouched holdout evaluation.** The generic shared policy,
   candidate order, first-six eligibility rule, selected configurations,
   evaluator-only setup, action-only routes, budgets, variant order, and
   analysis contract are now frozen before comparative outcomes.
2. **Phase 7B — recent-memory horizon ablation.** Begin only after the Phase-7A
   result is frozen. Run all compared variants fresh under one revision.

Live Phase-7 status belongs here rather than in the repository README,
application abstract, or Phase-5 result files. Current-facing documents change
only after a Phase-7 result is accepted.

## Phase 7A matrix checkpoint

The first six eligible candidates, in preregistered order, were FloorPlan308
through FloorPlan313. Eligibility ran from the tagged protocol revision and did
not execute fallback routes, memory variants, or outcome comparisons. The
public evidence contains only digests and coverage summaries; exact target IDs
and start poses are isolated in the evaluator-only registry and are never
planner input.

The selected matrix ran only from a clean, pushed commit at the annotated tag
`phase7a-holdout-matrix-v1`. All 18 cells completed without integrity errors.
The result is a small descriptive efficiency difference in simple rotational
reacquisition, with final success saturated and no translation or fallback
route execution. See [holdout_results.md](holdout_results.md) for the numerical
result and its limitations.

## Invalidation policy

A protocol version is invalidated if planner input contains evaluator-only data,
candidate ordering changes after outcomes are inspected, a variant receives a
capability unavailable to the others, a route/config digest changes, the source
revision changes within a matrix, task semantics change because of a general
runtime defect, required metrics are missing, or a row cannot be tied to its
frozen manifest.

When invalidated, retain the failed evidence and reason, increment the protocol
version, freeze the successor before rerunning, and rerun every required cell.
Never reuse only favorable rows.

## Evidence boundary

- Phase-5 canonical evidence remains under its existing paths.
- Phase-7 protocols live under `docs/phase7/` and `configs/phase7/`.
- Phase-7 evidence lives under `docs/evidence/phase7/`.
- Phase-7 scripts live under `scripts/phase7/` where practical.
- The optional AI/LLM planner is outside both successor studies.

The detailed Phase-7A rules are in [holdout_protocol.md](holdout_protocol.md).
The eligibility record is in
[holdout_eligibility_v1.json](../evidence/phase7/holdout_eligibility_v1.json),
and the frozen outcome is in [holdout_results.md](holdout_results.md). Phase 7B
may now be preregistered, but no Phase-7B outcome has been run.

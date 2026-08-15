# Phase 7 Successor Studies

Current status: preregistered

Phase 7 is additive successor research. It does not correct, extend, or replace
the accepted Phase-5 formal-v5 evidence.

## Study order

1. **Phase 7A — untouched holdout evaluation.** Freeze a generic shared policy
   and deterministic candidate rule before running any comparative holdout
   outcome.
2. **Phase 7B — recent-memory horizon ablation.** Begin only after the Phase-7A
   result is frozen. Run all compared variants fresh under one revision.

Live Phase-7 status belongs here rather than in the repository README,
application abstract, or Phase-5 result files. Current-facing documents change
only after a Phase-7 result is accepted.

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
No Phase-7 outcome has been run or accepted at this checkpoint.

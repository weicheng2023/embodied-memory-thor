# Evaluator-only Phase 5 configuration

Files in this directory contain hidden intervention state. They are available to
the evaluator/intervention loader only and must never be included in a
`PlannerRequest`, memory record, ordinary `episode.jsonl`, action history, or
fallback observation.

Exact registries are local-only and ignored by Git because they contain hidden
coordinates. Coordinate-free evidence commits the opaque ID and digest. Formal
runs must receive the local registry explicitly through the evaluator path. Any
code path that imports it into a planner is an information-boundary failure.

# Evaluator-only Phase 5 configuration

Files in this directory contain hidden intervention state. They are available to
the evaluator/intervention loader only and must never be included in a
`PlannerRequest`, memory record, ordinary `episode.jsonl`, action history, or
fallback observation.

Exact registries are local-only and ignored by Git because they contain hidden
coordinates. Coordinate-free evidence commits the opaque ID and digest. Formal
runs must receive the local registry explicitly through the evaluator path. Any
code path that imports it into a planner is an information-boundary failure.

## Publication identity review (2026-08-15)

The exact formal-v5 private bundle was not published. The retained R2 runtime-v3
registry has file SHA-256
`1736aed76e5a3c4c6213f1771b225180f2e5509465cf44c32076795ce65abbf5`,
which matches the value already recorded in public Phase-5 evidence. The retained
R1 six-anchor registry reproduces the public logical content digest
`423cf8ef98d73b56d836edbda83563cf4ebdc0604063e1ccf9530f876f781d92`,
but its historical file-byte SHA-256 was not recorded in the accepted public
manifest or evidence.

Because a complete formal-v5 rerun needs both registries, the available public
record cannot prove byte-for-byte identity for the complete bundle. No registry
was therefore added to Git. In particular, the ignored one-scene v1 file already
present in some local workspaces is not a substitute for the formal-v5 six-anchor
set. This preserves the existing reproducibility limitation rather than
publishing a reconstructed or only partially verified replacement.

# Contributions, Tooling, and Reproducibility

## Purpose

This note makes the development provenance explicit. Git commit volume is not
presented as evidence that every line was typed manually, and the reviewed
integration history is not intended to replace the chronological audit trail.
The appropriate evidence of technical ownership is the ability to explain the
design, reproduce the supported paths, inspect the information boundary, and
defend the limited conclusions.

## Development workflow

Coding assistants were used extensively for implementation drafts, refactoring,
test scaffolding, documentation drafting, command orchestration, and repository
maintenance. The repository maintainer set the project goal and scope, supplied
and observed the Windows/WSL2/WSLg environment, evaluated proposed protocol
changes, authorized simulator runs and retries, made the stopping and continuation
decisions, reviewed the resulting evidence, and takes responsibility for the
claims in the final report.

Some research and engineering decisions were developed collaboratively through
discussion with coding assistants. Accordingly, Git authorship should not be
read as a line-by-line claim of unaided implementation. The mixed Phase 5 result,
failed gates, invalidated pilots, and scene exclusions are retained rather than
removed to make the project look uniformly successful.

## Maintainer research and technical ownership

The maintainer's responsibilities in this project include:

- setting the research-preparation objective and accepting the final research
  question;
- requiring a search-capable no-memory baseline, exact K=2 comparison, and
  explicit stale-memory negative condition;
- enforcing the planner-visible versus evaluator-only information boundary;
- selecting or approving protocol revisions, qualification rules, stop decisions,
  retries, and complete reruns rather than selective row reuse;
- supplying and observing the Windows/WSL2/WSLg AI2-THOR environment;
- reviewing the retained failures and accepting the mixed R1/R2 interpretation;
- taking responsibility for reproducing, explaining, and defending the final
  methods, evidence boundary, and limitations.

Coding assistants produced substantial implementation, testing, documentation,
and command-orchestration work. The list above describes decision ownership and
accountability; it is not a claim that the maintainer manually authored every
associated code path.

## Raw and reviewed histories

- The chronological Phase 5/6 development history remains in
  [PR #7](https://github.com/weicheng2023/embodied-memory-thor/pull/7).
- Its pre-integration state is permanently anchored by tag
  [`phase5-6-raw-audit-2026-08-15`](https://github.com/weicheng2023/embodied-memory-thor/tree/phase5-6-raw-audit-2026-08-15)
  at commit `3715acd58b78632d1bf9b2ed55991a51d97c3ff4`.
- The reviewed integration reorganizes that identical final tree into thematic
  commits for code review. Before this disclosure file was added, both histories
  had the same Git tree hash: `ea70ba6643d4a31a382bf81c0c2b1926233d649f`.
- No raw branch was deleted, no commit was backdated, and negative evidence was
  not dropped during the reorganization.

## What the evidence supports

The project is an audited protocol-development case study followed by one frozen,
fresh-run internal comparison. The accepted formal-v5 matrix contains 54
successful real AI2-THOR episodes over three six-configuration matched panels.
Persistent object memory modestly reduced reacquisition work in R1 stable, did
not improve the longer R2 task overall, and used bounded fallback in the stale
panel without reducing its main costs. These are descriptive results for the
engineered settings, not an externally valid benchmark, statistical significance,
broad robotics generalization, or evidence that memory is always beneficial.

The detailed boundary is stated in
[`phase5_formal_results.md`](phase5_formal_results.md). Planner inputs are limited
to current visible observations, permitted action/failure history, and the memory
available to the selected variant. Hidden intervention coordinates and global
metadata remain evaluator-only.

## Reproduction and inspection

The public checkout supports these first checks:

```powershell
python -m pytest -q
python scripts/run_episode.py --mock --task put_apple_on_countertop --planner rule_based
```

The verified real-simulator route and minimal episode commands are documented in
the repository [`README`](../README.md) and
[`ai2thor_wsl_setup.md`](ai2thor_wsl_setup.md). A complete formal-matrix rerun
also requires the evaluator-only frozen registry described in
[`configs/evaluator_only/README.md`](../configs/evaluator_only/README.md). It is
excluded from Git so hidden coordinates cannot enter ordinary planner-visible
artifacts; therefore, a public checkout alone is not sufficient to reconstruct
that private intervention state.

For an ownership review, the maintainer should be able to explain and demonstrate:

1. why the no-memory baseline retains the same systematic search capability;
2. how planner-visible data is separated from evaluator-only state;
3. why the R1 result is positive but small;
4. why R2 search-rotation savings did not reduce total task cost;
5. how stale records are detected, invalidated, and followed by shared fallback;
6. how one mock episode and one real AI2-THOR episode are launched and audited.

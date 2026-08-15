# Protected Research Artifacts

This internal working note defines the edit boundary established before the
application-calibration pass. The baseline is clean commit
`ee6ebe9f096f845f6c7f80ef630155a8945ae4af`; its offline suite passed 422 tests
and 70 generated subtests on 2026-08-15.

## Protected / historical

The following paths remain available at their existing locations and are not
rewritten, regenerated, moved, renamed, or deleted:

- accepted evidence under `docs/evidence/phase5_*`;
- formal-v5 manifests and execution/analysis contracts under
  `configs/phase5_real_formal_*`;
- accepted Phase-5 public runtime, route, policy, task, qualification, and
  candidate contracts under `configs/phase5_*`;
- raw formal results and the chronological record in
  `docs/phase5_experiment_protocol.md`;
- historical Phase-5 qualification, diagnostic, freeze, execution, and
  aggregation scripts under `scripts/`;
- frozen Phase-5 implementation paths named in the formal-v5 manifest;
- the raw branch/PR history and tag `phase5-6-raw-audit-2026-08-15`.

`docs/phase5_formal_results.md` is also canonical Phase-5 evidence. PR 1 is
authorized to make one narrow interpretation-only wording correction there;
its table, numerical values, evidence link, and Phase-5-only scope remain
protected.

The accepted formal-v5 manifest additionally records SHA-256 values for its
critical inputs. Those registered values, the completion record's manifest and
result digests, and every accepted JSON evidence value remain unchanged.

## Current-facing / mutable

The following files may summarize the canonical evidence without becoming its
source:

- `README.md`;
- `docs/application_abstract.md`;
- the current-status section at the top of `docs/development_status.md`;
- `docs/report.md`;
- narrowly scoped positioning notes in `PROJECT_SCORECARD.md`;
- new documentation and deterministic consistency checks introduced by PR 1.

Clearly labelled historical checkpoints in `docs/development_status.md` are not
updated merely because their status is old.

## New Phase-7 namespace

Successor-study material is additive and belongs under:

```text
docs/phase7/
configs/phase7/
scripts/phase7/
docs/evidence/phase7/
```

Phase 7 never overwrites a Phase-5 asset. Current-facing documents summarize a
Phase-7 result only after that result has been frozen and accepted.

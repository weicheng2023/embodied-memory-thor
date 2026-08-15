# Phase 7 Evidence Index

Phase 7 evidence is additive and must not overwrite Phase-5 canonical evidence.

- `holdout_eligibility_v1.json`: pre-outcome Phase-7A candidate eligibility and
  generic route-construction evidence. It is not a memory-comparison result.
- `holdout_summary_v1.json`: exact compact output from the frozen 18-cell
  Phase-7A execution.
- `holdout_descriptive_results_v1.json`: exact output from the preregistered
  paired descriptive aggregator.
- `holdout_execution_metadata_v1.json`: environment, command, revision, file
  hashes, result digests, cell counts, and integrity status.

The result interpretation and limitations are in
[`docs/phase7/holdout_results.md`](../../phase7/holdout_results.md).

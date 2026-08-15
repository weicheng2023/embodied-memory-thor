# Script Index

Historical Phase-5 scripts keep their original names and locations so existing
evidence and Git history remain traceable. This index explains their roles; it
does not declare every historical command safe for a new formal run.

## Primary user-facing commands

- `check_environment.py`: report local mock, AI2-THOR, and optional planner
  capabilities without exposing secret values.
- `run_episode.py`: run the mock development path.
- `run_thor_episode.py`: run one real AI2-THOR episode in formal or debug mode.
- `run_thor_batch.py`: run a declared real-episode batch.
- `smoke_ai2thor.py`: verify the live simulator/rendering path.
- `list_scene_objects.py`: inspect scene object availability.
- `run_phase3_pilot.py`: reproduce the controlled symbolic Phase-3 comparison.

## Current formal-v5 reproduction and analysis

- `run_phase5_real_formal_pilot_v5.py`: readiness-only formal-v5 gate.
- `run_phase5_real_formal_execution_v5.py`: frozen complete-matrix executor;
  requires the exact local evaluator-only registries.
- `aggregate_phase5_real_formal_v5.py`: deterministic descriptive aggregation
  of the accepted formal-v5 summary.
- `build_phase5_manifest.py`: build the earlier Phase-5 manifest contract.

Do not run the formal executor against reconstructed private inputs. The public
reproduction boundary is documented in `configs/evaluator_only/README.md`.

## Historical Phase-5 qualification and freeze tools

Scripts beginning with `census_phase5_`, `qualify_phase5_`,
`prescreen_phase5_`, `precommit_phase5_`, and `freeze_phase5_` retain the scene,
route, placement, candidate, support, and runtime qualification history. Their
versioned successors are intentionally not consolidated.

## Diagnostics and excluded probes

Scripts beginning with `diagnose_phase5_`, `isolate_phase5_`,
`probe_phase5_`, `audit_phase5_`, and most `run_phase5_*_probe` or `*_gate`
names reproduce bounded diagnostics, excluded integration probes, or historical
stop gates. They are not accepted comparative evidence unless the corresponding
canonical evidence file says otherwise.

## Superseded formal launchers

`run_phase5_real_formal_pilot_v2.py` through `v4` and
`run_phase5_real_formal_execution_v3.py` through `v4` are retained for the
invalidated protocol history. Do not use them to extend formal-v5.

## Phase-7 successor scripts

New successor-study code belongs under `scripts/phase7/`. Phase-7 scripts and
outputs must not replace, rename, or silently reuse Phase-5 artifacts.

- `phase7/qualify_holdout_candidates.py`: run the fixed pre-outcome Phase-7A
  eligibility filter and generic route construction; no memory variants.
- `phase7/run_holdout.py`: run the complete matrix-frozen 18-cell Phase-7A
  comparison from its required clean annotated tag.
- `phase7/aggregate_holdout.py`: validate and descriptively aggregate one
  complete integrity-valid Phase-7A summary.
- `phase7/run_memory_horizon.py`: run all 30 fresh Phase-7B R1 cells from the
  frozen memory-horizon matrix tag and reduce the post-hoc retention checkpoint
  to non-identifying scalars.
- `phase7/aggregate_memory_horizon.py`: validate and descriptively aggregate a
  complete integrity-valid Phase-7B capacity matrix.

## Documentation consistency

Run this before a research-facing merge:

```bash
python scripts/check_research_consistency.py
python -m pytest -q
```

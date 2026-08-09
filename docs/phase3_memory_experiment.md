# Phase 3 Controlled Memory Experiment

## Purpose and evidence boundary

Phase 3 tests whether observation-derived history changes search behavior after a target leaves the current view. It is E1 evidence from a symbolic partial-observation mock, not a real AI2-THOR benchmark.

Ordinary planners receive only the current agent observation, the shared ordered task milestone, the common `ActionSpace`, and their assigned memory provider. Full state is used only by the success checker and evaluator-side experiment harness.

## Shared planner variants

- `rule_based_no_memory`: no historical observation records; retains systematic search.
- `short_memory`: only the latest two completed transition records.
- `object_memory`: persistent last-seen region/state records with visible-observation provenance.

All three use the same task rules and fallback cycle:

```text
Kitchen → DiningArea → SinkArea → Kitchen
```

When a provider has no usable target record, the selected fallback action must be identical across variants.

## Tasks and conditions

### T1 stable

`po_slice_apple_put_plate` requires Knife acquisition, Apple reacquisition, slicing, Plate search, and placement. Step limit: 14.

### T2 stable

`po_find_book_after_distraction` starts with Book visible, requires DeskLamp toggling in a distinct region, and then requires Book reacquisition and pickup. Step limit: 10. A milestone tracker audits that the lamp action precedes Book pickup without storing object locations.

### T1 stale

Immediately after successful Knife pickup while Apple is hidden, the evaluator-side harness relocates Apple to Plate's pre-intervention region. Relocation is not an agent action and is not exposed to planners. Object memory may first direct the agent to the old region; a miss marks that record `suspected_stale`, shared fallback search resumes, and rediscovery refreshes the record. Step limit: 18 for every variant.

## Frozen matrix

Seeds `0, 1, 4, 5, 6, 7` cover all six Apple/Knife/Plate region permutations exactly once. Seeds 1, 2, and 3 are not treated as independent layouts because they produce the same current mock permutation.

```text
3 variants × 3 conditions × 6 layout signatures = 54 ordinary episodes
```

The batch runner refuses a dirty working tree by default. Before any episode it writes `run_manifest.json` with the protocol version, Git revision, constants, layout signatures, intervention rule, and metric names.

```powershell
python scripts/run_phase3_pilot.py
```

For runner development only:

```powershell
python scripts/run_phase3_pilot.py --smoke --allow-dirty
```

Smoke output is permanently labeled development-only and cannot pass formal acceptance.

## Outputs

The pilot directory contains:

- `run_manifest.json`: frozen pre-run protocol and code revision;
- `episodes/.../episode.jsonl`: exact per-step observations, decisions, memory evidence, actions, interventions, and goal verdicts;
- `episodes/.../summary.json`: per-episode behavior and audit metrics;
- `pilot_results.csv`: flat per-layout comparison rows;
- `pilot_results.json`: rows plus descriptive aggregates;
- `protocol_acceptance.json`: machine-readable acceptance checks;
- `pilot_report.md`: concise human-readable result table and evidence boundary;
- `run_completion.json`: completion time and episode count.

## Permitted interpretation

Report individual layouts, counts, means, and ranges. Retain mixed, negative, and failed episodes. Phase 3 cannot establish statistical significance, broad task generalization, or memory improvement in real AI2-THOR; those require larger repeated E3 experiments.

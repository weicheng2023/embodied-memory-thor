# Phase 7B Memory-Horizon Result

Status: result frozen; complete and integrity-valid

Phase 7B ran all five conditions fresh on the six fixed R1-stable
configurations from commit `5cecc728812e85e10ef56e60adb23f893cfdc543`,
tagged `phase7b-memory-horizon-matrix-v1`. No Phase-5 or Phase-7A episode was
reused, and no configuration-specific repair was made after outcomes began.

## Descriptive result

| Variant | Target retained at reacquisition | Success@18 | Eventual success | Mean steps | Mean reacquisition actions |
| --- | ---: | ---: | ---: | ---: | ---: |
| `no_memory` | 0/6 | 6/6 | 6/6 | 7.500 | 5.333 |
| `recent_memory_k2` | 0/6 | 6/6 | 6/6 | 7.500 | 5.333 |
| `recent_memory_k4` | 2/6 | 6/6 | 6/6 | 7.667 | 5.500 |
| `recent_memory_k8` | 6/6 | 6/6 | 6/6 | 6.667 | 4.500 |
| `object_memory` | 6/6 | 6/6 | 6/6 | 6.667 | 4.500 |

Success was saturated at all preregistered budgets. K=2 matched no memory on
total and reacquisition actions in all six configurations. K=4 crossed the
retention boundary in only two configurations; relative to no memory, its
paired total-action differences were `[0, 2, -1, 0, 0, 0]` (one better, four
ties, one worse). Retaining a record therefore did not guarantee lower cost in
this deterministic policy.

K=8 retained the target in all six configurations. Its paired total and
reacquisition differences versus no memory were
`[-1, 0, -1, -1, -1, -1]` (five better, one tie, zero worse; mean -0.833
action). Object memory produced the same six total-action differences, the same
six reacquisition differences, and the same 6/6 retention count. Object memory
and K=8 tied on total and reacquisition actions in every configuration.

## Interpretation

Within the common recent-observation provider, behavior changed when capacity
became long enough to retain the target through the 4-5 action distraction
horizon. In this simple rotational reacquisition panel, a K=8 recent window
reproduced the small efficiency pattern observed with persistent object memory.
The study therefore provides no evidence here that object memory's structured
representation or retrieval adds benefit beyond sufficient recent-context
length.

That is a bounded negative result, not a claim that structured object memory is
generally unnecessary. All 30 episodes succeeded, translation count and
distance were zero in every condition, and the panel did not exercise long
navigation, stale correction, cluttered search, or multi-object interference.
Object memory still differs from recent memory in persistence, representation,
and retrieval, so the design does not fully isolate those properties. Six
paired configurations support descriptive mechanism evidence, not a population
estimate or significance claim.

Phase 7B is a separate successor study. It neither changes nor retroactively
reinterprets the canonical Phase-5 numbers, and it does not replace the limited
Phase-7A holdout result.

## Integrity and provenance

- Matrix: 30/30 cells complete; 30 successes, 0 task failures, 0 integrity
  errors.
- Environment: AI2-THOR 5.0.0; Python 3.10.12; WSL2 Linux x86-64.
- Matrix manifest digest:
  `2052b196b3abbf398c29f9db543b4c37c4ce9b3324ec70c2f6a407e19d35014e`.
- Result digest:
  `57e2d64e3324c7ab13ed517043d5d95709b977252ca53c19af474d3ce3b94f17`.
- No prior episode was reused; no images or GUI output were produced.
- Public result files contain no target IDs, start actions, coordinates,
  anchors, or reachable graphs.

Canonical evidence:

- [memory_horizon_summary_v1.json](../evidence/phase7/memory_horizon_summary_v1.json)
- [memory_horizon_descriptive_results_v1.json](../evidence/phase7/memory_horizon_descriptive_results_v1.json)
- [memory_horizon_execution_metadata_v1.json](../evidence/phase7/memory_horizon_execution_metadata_v1.json)

All reported comparisons are descriptive over six paired configurations. No
significance test or broad-generalization claim is made.

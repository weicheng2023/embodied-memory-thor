# Phase 7A Holdout Result

Status: result frozen; complete and integrity-valid

Phase 7A evaluated the unchanged three-condition R1 policy on the first six
configurations that passed the preregistered eligibility rule: FloorPlan308
through FloorPlan313. All 18 episodes were executed fresh from commit
`3d5b76796b15b10ceb1b0daf2c943df9e87e8038`, tagged
`phase7a-holdout-matrix-v1`. No scene-specific repair was made after outcomes
were observed.

## Descriptive result

| Variant | Success@18 | Success@72 | Eventual success | Mean steps | Mean reacquisition actions |
| --- | ---: | ---: | ---: | ---: | ---: |
| `no_memory` | 6/6 | 6/6 | 6/6 | 7.500 | 5.333 |
| `short_memory_k2` | 6/6 | 6/6 | 6/6 | 7.500 | 5.333 |
| `object_memory` | 6/6 | 6/6 | 6.667 | 4.500 |

Success was saturated at every preregistered budget. Relative to no memory,
object memory used one fewer total and reacquisition action in five
configurations and tied in one: paired differences were
`[-1, 0, -1, -1, -1, -1]` for both measures (mean -0.833 action). It also
reduced repeated-viewpoint counts in five configurations and tied in one. The
K=2 condition matched no memory on these cost measures; its target record was
confirmed evicted before reacquisition in all six configurations. Object-memory
episodes recorded memory-guided actions, while no-memory and K=2 episodes did
not.

## Interpretation boundary

This is a small conditional efficiency difference in simple rotational
reacquisition, not evidence of higher final success or broad embodied
navigation performance. Every episode had zero translation actions, zero
search rotations, zero route-recovery actions, zero invalid actions, and zero
failed interactions. Consequently, the generic fallback routes were available
under the same contract but were not exercised by these outcomes. The study
does not establish a navigation advantage, a difficult-scene advantage, or a
statistically general population effect.

"Untouched holdout" has the operational meaning fixed in the protocol: these
scenes had no prior comparative memory outcomes and received no Phase-7
scene-specific repair after outcomes. It does not mean that the simulator scene
family was never queried; the pre-outcome eligibility process used evaluator
metadata and generic route construction, and earlier Phase-5 coordinate-free
prescreens of the scene family are disclosed in the protocol.

The complete-condition confound remains: K=2 and object memory differ in more
than capacity alone. Phase 7B therefore evaluates recent-memory horizons in a
fresh, separately frozen mechanism study. This Phase 7A result does not modify,
extend, or replace the Phase-5 formal-v5 result.

## Integrity and provenance

- Matrix: 18/18 cells complete; 18 successes, 0 task failures, 0 integrity
  errors.
- Environment: AI2-THOR 5.0.0; Python 3.10.12; WSL2 Linux x86-64.
- Matrix manifest digest:
  `59952fc657e129d30a3aaa258731de4b8de6da0a6c8f79230133fceca59f0f48`.
- Result digest:
  `5e69f91fac4590641aa74880f5649344117bf005bfe918504df21a21b8262770`.
- No prior episode was reused; no images or GUI output were produced.
- Planner-visible data did not contain target IDs, evaluator start poses,
  coordinates, anchors, or reachable graphs.

Canonical evidence:

- [holdout_summary_v1.json](../evidence/phase7/holdout_summary_v1.json)
- [holdout_descriptive_results_v1.json](../evidence/phase7/holdout_descriptive_results_v1.json)
- [holdout_execution_metadata_v1.json](../evidence/phase7/holdout_execution_metadata_v1.json)
- [holdout_eligibility_v1.json](../evidence/phase7/holdout_eligibility_v1.json)

All reported comparisons are descriptive over six paired configurations. No
significance test or broad-generalization claim is made.

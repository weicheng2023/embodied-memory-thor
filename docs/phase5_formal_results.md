# Phase 5 Formal-v5 Results

## Study type

Formal-v5 is the frozen endpoint of an adaptive, audited protocol-development
case study. Earlier simulator failures informed scene qualification, route
construction, recovery policies, and successor protocol versions. Those changes
were committed before their subsequent runs, and v2-v4 rows were discarded
rather than selectively reused; nevertheless, the overall study was not fixed
once at the outset. The final matrix supports a controlled internal comparison
within the engineered settings, not external-validity or preregistered-benchmark
claims.

## Outcome

The fixed real AI2-THOR matrix completed 54/54 episodes with 54 task successes,
no integrity errors, and a clean information boundary. The formal result is
mixed: persistent object memory helped the simple R1 reacquisition metric, did
not improve the longer R2 task overall, and recovered safely from stale records
without improving the main stale-panel costs.

All values below are descriptive over six matched configurations per panel.
`Object - No` is a paired cost difference, so negative is better for object
memory. K=2 and no-memory were identical on all six primary metrics in every
panel; object-versus-K=2 therefore equals object-versus-no-memory here.

| Panel | Success (No / K=2 / Object) | Mean steps (No / K=2 / Object) | Object - No steps: mean (better/tie/worse) | Mean reacquisition actions (No / K=2 / Object) | Object - No reacquisition: mean (better/tie/worse) |
| --- | ---: | ---: | ---: | ---: | ---: |
| R1 stable | 6/6 / 6/6 / 6/6 | 7.33 / 7.33 / 7.17 | -0.17 (2/3/1) | 5.00 / 5.00 / 4.50 | -0.50 (3/3/0) |
| R2 stable | 6/6 / 6/6 / 6/6 | 28.50 / 28.50 / 32.00 | +3.50 (1/1/4) | 21.50 / 21.50 / 23.83 | +2.33 (1/3/2) |
| R1 stale | 6/6 / 6/6 / 6/6 | 43.33 / 43.33 / 43.33 | 0.00 (0/6/0) | 41.00 / 41.00 / 41.00 | 0.00 (0/6/0) |

## Interpretation

R1 stable provides a small conditional efficiency gain in simple reacquisition.
Object memory reduced target reacquisition by one action in three configurations
and tied in three, for a mean reduction of 0.5 actions. Total episode steps
changed only slightly: two improvements, three ties, and one regression, with a
mean reduction of 0.17. Repeated viewpoint visits fell by one on average.

R2 stable is the important counter-result. Object memory reduced search
rotations by 3.17 on average and did use remembered information, but this did
not translate into a cheaper episode. It increased mean total steps by 3.5,
reacquisition actions by 2.33, translation actions by 2.17, translation distance
by 0.54 m, and repeated viewpoints by 1.33. FloorPlan4 improved substantially,
while FloorPlan6 regressed substantially and required 14 shared entry-recovery
actions. The evidence therefore supports a narrower conclusion: memory can
reduce blind search, but a weak memory-to-navigation policy can erase or reverse
that benefit.

R1 stale shows robust task completion and bounded fallback. Object memory made
14 guided actions and produced five explicit old-viewpoint misses followed by
five stale-record recoveries. Main costs were exactly equal to both baselines;
repeated viewpoints increased by one in one configuration. FloorPlan303 is a
declared limitation: after relocation, restoring the remembered camera horizon
made the moved Book visible immediately, so that episode did not emit an
old-viewpoint miss even though the evaluator intervention succeeded and had
initially hidden the Book.

## Evidence boundary

These are repeated real-simulator results, but each panel contains only six
deterministic matched configurations. No significance test or panel pooling was
performed, and the result does not establish broad task, scene, perception, or
robotics generalization. Because tasks, scenes, routes, and recovery policies were
co-developed through qualification, the result also does not estimate performance
on untouched settings. The supported claim is conditional: persistent memory
helped simple reacquisition in the tested R1 settings; it was not unconditionally
better, and R2 exposes navigation overhead that should be addressed next.

The compact public evidence is
[`evidence/phase5_real_formal_v5_descriptive_results.json`](evidence/phase5_real_formal_v5_descriptive_results.json).
It retains per-configuration paired-difference vectors for all six primary
metrics and binds the full generated analysis by SHA-256 and analysis digest.

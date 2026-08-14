# Phase 3 Results: Controlled Memory Pilot

## Result status

- Protocol: `phase3-v2`
- Formal implementation revision: `1af6c9c9ef954fd710fdb22c1561da6cd494a460`
- Matrix: 3 variants × 3 conditions × 6 unique layouts = 54 episodes
- Formal acceptance: PASS
- Evidence level: E1 controlled symbolic partial-observation mock

The formal run was launched from a clean working tree. Its local audit directory is `outputs/phase3_pilot/formal_v2_1af6c9c`; generated episode logs remain ignored by Git, while this result record preserves the protocol, per-layout outcomes, aggregate values, and interpretation boundary.

## Acceptance audit

| Check | Result |
| --- | --- |
| Complete 54-episode matrix | PASS |
| All ordinary information-leak audits | 54/54 PASS |
| T2 DeskLamp-before-Book ordered audit | 18/18 PASS |
| Capable no-memory systematic search | 18/18 successful |
| Matched evaluator-side stale intervention | 18/18 applied once |
| ObjectMemory guides behavior in both stable tasks | PASS |
| Stale miss, fallback, rediscovery, correction | 6/6 ObjectMemory stale episodes |
| Invalid actions | 0 across 54 episodes |

## Aggregate descriptive results

| Condition | Variant | Success | Mean steps | Step range | Mean moves | Move range | Mean revisits | Mean memory-guided actions | Mean stale misses | Mean recoveries |
| --- | --- | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: |
| T1 stable | no memory | 6/6 | 9.50 | 9–10 | 4.50 | 4–5 | 2.50 | 0.00 | 0.00 | 0.00 |
| T1 stable | short memory, K=2 | 6/6 | 9.50 | 9–10 | 4.50 | 4–5 | 2.50 | 0.00 | 0.00 | 0.00 |
| T1 stable | object memory | 6/6 | 9.00 | 9–9 | 4.00 | 4–4 | 2.00 | 1.50 | 0.00 | 0.00 |
| T2 stable | no memory | 6/6 | 5.00 | 5–5 | 3.00 | 3–3 | 1.00 | 0.00 | 0.00 | 0.00 |
| T2 stable | short memory, K=2 | 6/6 | 5.00 | 5–5 | 3.00 | 3–3 | 1.00 | 0.00 | 0.00 |
| T2 stable | object memory | 6/6 | 4.50 | 4–5 | 2.50 | 2–3 | 1.00 | 1.00 | 0.00 | 0.00 |
| T1 stale | no memory | 6/6 | 11.00 | 10–12 | 6.00 | 5–7 | 4.00 | 0.00 | 0.00 | 0.00 |
| T1 stale | short memory, K=2 | 6/6 | 11.00 | 10–12 | 6.00 | 5–7 | 4.00 | 0.00 | 0.00 | 0.00 |
| T1 stale | object memory | 6/6 | 10.00 | 9–11 | 5.00 | 4–6 | 3.00 | 1.50 | 1.00 | 1.00 |

## Per-layout steps / region moves

| Condition | Variant | Seed 0 | Seed 1 | Seed 4 | Seed 5 | Seed 6 | Seed 7 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 stable | no memory | 9 / 4 | 10 / 5 | 9 / 4 | 10 / 5 | 9 / 4 | 10 / 5 |
| T1 stable | short memory | 9 / 4 | 10 / 5 | 9 / 4 | 10 / 5 | 9 / 4 | 10 / 5 |
| T1 stable | object memory | 9 / 4 | 9 / 4 | 9 / 4 | 9 / 4 | 9 / 4 | 9 / 4 |
| T2 stable | no memory | 5 / 3 | 5 / 3 | 5 / 3 | 5 / 3 | 5 / 3 | 5 / 3 |
| T2 stable | short memory | 5 / 3 | 5 / 3 | 5 / 3 | 5 / 3 | 5 / 3 | 5 / 3 |
| T2 stable | object memory | 5 / 3 | 4 / 2 | 5 / 3 | 4 / 2 | 5 / 3 | 4 / 2 |
| T1 stale | no memory | 12 / 7 | 10 / 5 | 12 / 7 | 10 / 5 | 12 / 7 | 10 / 5 |
| T1 stale | short memory | 12 / 7 | 10 / 5 | 12 / 7 | 10 / 5 | 12 / 7 | 10 / 5 |
| T1 stale | object memory | 11 / 6 | 9 / 4 | 11 / 6 | 9 / 4 | 11 / 6 | 9 / 4 |

Each cell reports `steps / region moves`.

## Findings

1. In both stable task structures, persistent ObjectMemory changed actions using last-seen records and reduced mean steps and region moves by 0.5 relative to the capable no-memory baseline. The improvement occurred on three of six layouts in each task; it was not universal.
2. Short memory with K=2 matched no memory in every condition because the initially observed Apple or Book had left the two-transition window before reacquisition was required.
3. In all six stale ObjectMemory episodes, the planner used the remembered Apple region, received negative evidence there, marked the record `suspected_stale`, used common fallback search, rediscovered Apple, and refreshed the record from a visible observation.
4. Stale information imposed a local detour, but whole-episode cost remained topology-dependent. ObjectMemory stale episodes added 0 or 2 steps relative to their own matched stable layouts and still averaged one fewer step/move than no/short memory in the stale condition. The evidence therefore supports conditional stale-risk and recovery, not a claim that stale memory always loses to no memory.

## Invalidated v1 audit

The first completed 54-episode run used protocol v1 and moved Apple into Plate's region. That made the downstream placement subgoal easier and could cancel the stale-location detour in total-step comparisons. The run was not selectively edited: all traces remain locally under `outputs/phase3_pilot/formal_0e73366`, the confound is documented, the protocol version was incremented, a new clean revision was committed, and all 54 episodes were rerun.

## Interpretation limit

These values are descriptive results across six deterministic symbolic layouts. They do not establish statistical significance, broad task generalization, pixel-level perception performance, physical-navigation performance, or memory improvement in real AI2-THOR. Those require repeated E3 experiments in a later phase.

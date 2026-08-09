# Controlled Partial-Observability Harness

## Purpose

The Phase 2R mock is a deterministic research harness for testing information flow before memory is implemented. It is not a visual simulator, physics simulator, or substitute for live AI2-THOR evidence.

Its purpose is to make the memory question testable: an object can be observed, leave the current view, and later need to be found again.

## Information boundary

```text
Full environment state
├── get_observation()      visible objects + agent pose/region → planner
└── get_evaluator_state()  all objects → success checker/debug oracle only
```

Ordinary planners never receive evaluator state. Every episode step records:

- `agent_observation_before_action`;
- `planner_received_object_ids`;
- `agent_observation_after_action`;
- evaluator-derived goal status, without logging hidden full state as planner input;
- whether the planner is explicitly privileged.

## Controlled environment

The mock contains three regions:

- `Kitchen`
- `DiningArea`
- `SinkArea`

For each seed, Apple, Knife, and Plate are reproducibly assigned to distinct regions. The agent starts where the Apple is visible. Region moves and rotations update the current view. Object interactions require the target to be visible and within the interaction distance.

`MoveToRegion` is a high-level abstract navigation action. It does not model path planning, collision, or physical locomotion and must not be described as such.

## Phase 2R task

`po_slice_apple_put_plate` requires the agent to:

1. observe and leave the Apple;
2. search for and pick up the Knife;
3. return to the Apple and slice it;
4. search for the Plate;
5. place the sliced Apple on the Plate.

## Baselines

### `rule_based_no_memory`

Receives only the current observation. When a required object is absent, it follows a fixed region cycle and retains no visited-region or last-seen-object history.

### `oracle_debug`

Receives privileged evaluator state and moves directly to hidden target regions. It is an upper-bound solvability check, not a valid memory baseline or research result.

## Commands

Inspect one partial observation:

```powershell
python scripts/list_scene_objects.py --mock --partial-observability --seed 0
```

Run the observation-only baseline:

```powershell
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner rule_based_no_memory
```

Run the privileged debug upper bound:

```powershell
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner oracle_debug
```

## Verified Phase 2R smoke results

| Planner | Seeds | Success | Steps by seed | Region moves by seed | Evidence use |
| --- | --- | ---: | --- | --- | --- |
| `rule_based_no_memory` | 0, 1, 2 | 3/3 | 9, 10, 10 | 4, 5, 5 | E1 harness baseline |
| `oracle_debug` | 0, 1, 2 | 3/3 | 8, 8, 8 | 3, 3, 3 | Privileged solvability check only |

These values verify the harness and information boundary. They do not show a memory benefit because Phase 3 memory variants do not yet exist.

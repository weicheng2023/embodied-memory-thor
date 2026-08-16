# Embodied-Memory-THOR

**Controlled evaluation of persistent object memory for partially observable embodied agents in AI2-THOR.**

## Problem

Embodied agents lose access to previously observed objects once those objects
leave the current view. Persistent memory may help, but a comparison is easily
confounded: a memory agent can appear stronger because its baseline cannot
search, or because it reads privileged simulator state unavailable to an actual
agent.

This project asks how to measure memory itself while holding search capability,
action execution, recovery logic, and success evaluation as constant as
possible.

## Research question

> In matched partially observable AI2-THOR tasks, does persistent visible-history
> object memory reduce target reacquisition effort relative to a capable
> no-memory search policy and exact-K short-term memory?

## Related work and positioning

[Kolve et al. (2017)](https://arxiv.org/abs/1712.05474) introduced AI2-THOR as
an interactive 3D environment for agents that navigate and manipulate household
objects. Long-term object memory is also established prior work:
[Fukushima et al. (2022)](https://arxiv.org/abs/2203.14708) proposed the Object
Memory Transformer for Object Goal Navigation. This project therefore does not
claim a novel memory architecture. It asks a narrower evaluation question:
whether lightweight persistent visible-history memory produces measurable
benefit when baseline search capability and privileged simulator state are
controlled.

## Approach

Phase 5 and Phase 7A use three variants behind the same deterministic planner
and action interface:

| Variant | Historical information available to the planner |
| --- | --- |
| `no_memory` | No earlier observation; retains the full systematic search policy |
| `short_memory_k2` | Exactly the two most recent safe observation snapshots |
| `object_memory` | Persistent visible-derived object and last-seen camera records |

Phase 7B preserves those conditions and adds generalized exact K=4 and K=8
recent-observation windows in a separate fresh-run ablation.

The controlled comparison keeps the following shared across variants:

- the same task, start, action space, target-lock, fallback search, recovery
  policies, step limit, and state-based evaluator;
- planner input limited to current visible-derived state, permitted history, and
  the memory exposed by the selected variant;
- evaluator-only global state and stale-relocation coordinates isolated from
  planner requests, ordinary traces, and memory records;
- stale memory tested explicitly rather than reporting only favorable stable
  cases.

## Evidence chronology

### Phase 5: controlled internal evaluation

The accepted formal-v5 evaluation contains:

```text
18 matched configuration cells across 3 panels
x 3 memory variants = 54 executions
```

- **R1 stable:** reacquire a previously seen Book;
- **R2 stable:** complete a CoffeeMachine subgoal, then reacquire a Cup;
- **R1 stale:** revisit an outdated Book record, fall back, and correct it.

All 54 real AI2-THOR executions completed successfully. Success was therefore
saturated and does not distinguish the variants; the informative comparisons
are task/action efficiency, reacquisition effort, search rotations,
translation/navigation overhead, and stale-memory recovery. These executions
reuse six deterministic matched configurations per panel and are not 54
independent environments or independent samples. Automated checks confirmed
that hidden evaluator state was not exposed to the planner.

#### Phase-5 results

| Panel | Success: No / K=2 / Object | Mean steps: No / K=2 / Object | Mean reacquisition actions: No / K=2 / Object |
| --- | ---: | ---: | ---: |
| R1 stable | 6/6 / 6/6 / 6/6 | 7.33 / 7.33 / **7.17** | 5.00 / 5.00 / **4.50** |
| R2 stable | 6/6 / 6/6 / 6/6 | 28.50 / 28.50 / **32.00** | 21.50 / 21.50 / **23.83** |
| R1 stale | 6/6 / 6/6 / 6/6 | 43.33 / 43.33 / 43.33 | 41.00 / 41.00 / 41.00 |

Persistent memory produced a small conditional efficiency gain in simple R1
reacquisition. In the longer R2 task it reduced search rotations but increased
movement, route re-entry, and total action cost. In the stale panel it detected
and corrected five explicit outdated records, then matched the baselines on the
main costs.

### Phase 7A: frozen holdout evaluation

The unchanged three-condition R1 policy was evaluated on the first six
configurations passing a rule fixed before outcomes (FloorPlan308-FloorPlan313).
All 18 fresh episodes succeeded without scene-specific repair. Object memory
used one fewer total and reacquisition action in five configurations and tied in
one; K=2 matched no memory. This is a small conditional result in rotational
reacquisition: no episode used translation or a fallback route. See the
[Phase-7A result](docs/phase7/holdout_results.md).

### Phase 7B: memory-horizon mechanism ablation

All five variants were rerun fresh on the same six configurations, for 30 new
executions under one frozen revision.

| Variant | Target retained at reacquisition | Mean steps | Mean reacquisition actions |
| --- | ---: | ---: | ---: |
| No memory | 0/6 | 7.500 | 5.333 |
| Recent memory K=2 | 0/6 | 7.500 | 5.333 |
| Recent memory K=4 | 2/6 | 7.667 | 5.500 |
| Recent memory K=8 | 6/6 | 6.667 | 4.500 |
| Object memory | 6/6 | 6.667 | 4.500 |

K=8 and object memory matched on retention, total actions, and reacquisition
actions in every configuration. In this simple task, retaining the target long
enough reproduced the observed efficiency pattern; the study does not
demonstrate an additional benefit from structured object records or establish
that the two memory systems are generally equivalent. See the
[Phase-7B result](docs/phase7/memory_horizon_results.md).

## Takeaway

> **Memory storage alone is insufficient. Useful embodied memory must be coupled
> with efficient memory-conditioned navigation and uncertainty-aware revision.**

Across the three studies, retrieving the right location can reduce blind search,
yet a weak policy for exploiting that location can erase or reverse the benefit.
The horizon ablation further shows that the small simple-task gain does not, by
itself, establish a benefit from structured representation beyond sufficient
recent-context length.

The project begins with a controlled internal case study developed through
adaptive qualification, then adds a frozen holdout and a separate mechanism
ablation. Together they support conditional evidence in narrow deterministic
settings, not statistical significance or broad external validity. See the
[Phase-5 result](docs/phase5_formal_results.md) and
[Phase-7 evidence index](docs/phase7/README.md).

## System at a glance

```mermaid
flowchart LR
    THOR[AI2-THOR] --> OBS[Visible observation parser]
    OBS --> MEM[Selected memory provider]
    OBS --> REQ[PlannerRequest]
    MEM --> REQ
    REQ --> PLAN[Shared planner and recovery policy]
    PLAN --> ACT[Action executor]
    ACT --> THOR
    REQ --> TRACE[Planner-visible audit trace]
    ACT --> TRACE
    THOR -. evaluator-only full state .-> EVAL[Intervention and success checker]
    EVAL --> PRIVATE[Private evaluator audit]
```

The dashed evaluator path is unavailable to the planner. The full architecture
and field-level information boundary are documented in
[`docs/architecture.md`](docs/architecture.md).

![Real AI2-THOR FloorPlan1 frame with a visible Book](docs/assets/ai2thor_smoke/floorplan1.png)

*A real AI2-THOR integration-smoke frame captured from the in-memory RGB array.
It confirms the simulator/rendering path; it is not presented as formal memory-
comparison evidence.*

## Why a deterministic visible-metadata planner?

The formal study deliberately holds perception and open-ended planning constant
so that memory access is the primary changing variable. Current visible
AI2-THOR metadata replaces a learned detector, and deterministic action logic
avoids mixing visual errors or LLM sampling variance into the memory comparison.

This is an experimental-control choice, not a claim that metadata planning is a
complete embodied-agent solution. A natural successor is to replace it with a
structured LLM/VLM planner and RGB perception behind the same observation-memory
interface, then evaluate broader randomized holdout tasks with real navigation.

## Project status

Phases 0-7 are complete:

- Phase 3 established the controlled symbolic partial-observation harness;
- Phase 4 established the real AI2-THOR loop and planner/evaluator boundary;
- Phase 5 completed the adaptive protocol-development process and the fresh
  54-execution formal-v5 comparison;
- Phase 6 assembled the architecture, results, failure analysis, application
  abstract, scorecard, and reproducibility documentation;
- Phase 7A completed a frozen first-six holdout evaluation, and Phase 7B
  completed a fresh K=2/K=4/K=8 memory-horizon ablation.

Formal-v2, v3, and v4 were invalidated after distraction, pickup-recovery, and
route-execution defects. Their rows were not selectively reused; formal-v5 was
rerun from cell 1 after the successor rules were fixed. The complete
chronology remains in [`docs/phase5_experiment_protocol.md`](docs/phase5_experiment_protocol.md).

## Quick reproduction

### Offline tests

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

The accepted checkpoint passes **448 tests plus 70 generated subtests**.

### Minimal mock episode

This path requires neither AI2-THOR nor an external API:

```powershell
python scripts/run_episode.py --mock --task put_apple_on_countertop --planner rule_based
```

Each run writes `episode.jsonl` and `summary.json` under a unique
`outputs/runs/<timestamp>/` directory.

### Real AI2-THOR integration smoke test

The verified Windows-host route uses Ubuntu 22.04 under WSL2/WSLg:

```powershell
wsl --distribution Ubuntu-22.04 --user research -- bash -lc "cd /mnt/d/path/to/embodied-memory-thor && ~/embodied-memory-thor-runtime/.venv/bin/python scripts/smoke_ai2thor.py --scenes FloorPlan1 FloorPlan10"
```

See [`docs/ai2thor_wsl_setup.md`](docs/ai2thor_wsl_setup.md) for the tested
environment and dependency record.

### Auditable real episode trace

```bash
python scripts/run_thor_episode.py \
  --scene FloorPlan1 \
  --task thor_book_reacquire \
  --planner object_memory \
  --mode formal \
  --trace-html
```

RGB is a human-audit artifact; the formal planner consumes visible metadata.
Setup actions and optional evaluator debug state are logged separately from
planner metrics. A complete formal-matrix rerun additionally requires the local
evaluator-only historical registry described in
[`configs/evaluator_only/README.md`](configs/evaluator_only/README.md).

## Installation and environment

Requirements:

- Python 3.10 or newer;
- Windows, macOS, or Linux for the mock/offline path;
- Ubuntu 22.04 WSL2/WSLg for the verified live AI2-THOR path;
- no API key unless the optional OpenAI-compatible planner is used.

Create and activate a virtual environment, then install the package:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

On macOS or Linux, activate with `source .venv/bin/activate`. Optional extras:

```powershell
python -m pip install -e ".[dev]"
python -m pip install -e ".[thor]"
```

Optional OpenAI-compatible configuration belongs in an untracked `.env` file:

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
```

The environment diagnostic reports capability without exposing secret values:

```powershell
python scripts/check_environment.py
python scripts/check_environment.py --json
```

## Additional evaluation entry points

Inspect mock or real scene objects:

```powershell
python scripts/list_scene_objects.py --mock
python scripts/list_scene_objects.py --scene FloorPlan1
```

Run the controlled symbolic memory variants:

```powershell
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner rule_based_no_memory
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner short_memory
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner object_memory
```

The privileged `oracle_debug` variant is a solvability upper bound only. Phase 3
is symbolic E1 evidence, not proof of real-simulator memory improvement. See
[`docs/phase3_memory_experiment.md`](docs/phase3_memory_experiment.md) and
[`docs/phase3_results.md`](docs/phase3_results.md).

## Repository map

```text
configs/                         Public task, protocol, and route contracts
configs/evaluator_only/          Schema only; hidden frozen registries stay local
docs/evidence/                   Compact public qualification and result evidence
docs/phase5_experiment_protocol.md  Chronological protocol-development audit
docs/phase5_formal_results.md     Accepted descriptive result and claim boundary
docs/phase7/                      Frozen successor protocols and accepted results
outputs/                         Generated run artifacts (ignored except .gitkeep)
scripts/                         Diagnostics, qualification, execution, aggregation
src/embodied_memory_thor/        Environment, memory, planner, evaluator, trace code
tests/                           Offline contracts and regression coverage
```

## Research presentation package

- [`docs/application_abstract.md`](docs/application_abstract.md): copy-ready
  project summary;
- [`docs/report.md`](docs/report.md): complete research narrative;
- [`docs/architecture.md`](docs/architecture.md): system and information-flow
  design;
- [`docs/phase5_formal_results.md`](docs/phase5_formal_results.md): result table
  and interpretation;
- [`docs/phase7/README.md`](docs/phase7/README.md): Phase-7 holdout and
  memory-horizon evidence;
- [`docs/failure_cases.md`](docs/failure_cases.md): retained failures and lessons.

## Development provenance and ownership

AI tools were used to assist with implementation drafts, tests, documentation
drafting, and command orchestration. The maintainer set the project objective,
required fair search-capable baselines and an explicit stale-memory negative
condition, enforced planner/evaluator separation, selected or approved protocol
revisions and stop/rerun decisions, provided and observed the
Windows/WSL2/WSLg environment, and takes responsibility for the final
interpretation and limitations.

The raw chronological PR and immutable audit tag remain public. See
[`docs/CONTRIBUTIONS_AND_REPRODUCIBILITY.md`](docs/CONTRIBUTIONS_AND_REPRODUCIBILITY.md)
for the detailed division of responsibility, history mapping, and reproduction
boundary.

## Limitations and next step

- Six deterministic matched configurations per panel support descriptive,
  task-specific evidence only.
- Tasks, scenes, routes, and recovery policies were co-developed during
  qualification, limiting external validity.
- The complete-condition comparison does not separately isolate memory
  persistence, capacity, representation structure, and retrieval; exact K=2 and
  persistent object memory differ along more than one of these dimensions.
- Phase 7A adds only six holdout configurations in the same simple R1 structure;
  it exercised rotation but no translation, fallback route, or difficult
  recovery behavior.
- Phase 7B shows an exact K=8/object-memory behavioral tie only on that narrow
  deterministic panel; it does not establish representational equivalence.
- The formal planner uses visible metadata rather than RGB perception or an LLM.
- AI2-THOR results do not establish physical-robot performance.

The strongest next study would extend the frozen-policy approach to broader,
randomized tasks that require translation and recovery, report failures without
task-specific repair, and separately evaluate structured LLM/VLM planning and
RGB perception.

# Embodied-Memory-THOR

A lightweight memory and evaluation layer for LLM-based embodied agents in AI2-THOR.

## Status

Phases 0–3 are complete. The formal `phase3-v2` controlled pilot ran 54/54 successful episodes from a clean revision, with all information-boundary and protocol checks passing. Results are descriptive E1 mock evidence, not a real AI2-THOR memory claim. LLM planners remain later work.

## Motivation and scope

This project explores how structured object state, recent interaction context, and action-failure history can support small embodied-agent pipelines. Its intended end-to-end loop is:

```text
AI2-THOR environment
→ observation parsing
→ memory update
→ planner decision
→ action execution
→ state-based success evaluation
→ logging and report generation
```

The project is a lightweight research preparation project. It is not a state-of-the-art method, does not train a large VLA or diffusion-policy model, and is not a reproduction of a paper from James Cheng's group. Its focus is systems engineering, memory/context design, robust evaluation, and reproducibility.

## Requirements

- Python 3.10 or newer
- Windows, macOS, or Linux for the mock path; live AI2-THOR is verified on Ubuntu 22.04 WSL2/WSLg rather than native Windows
- AI2-THOR is optional during Phase 0
- An OpenAI-compatible API key is optional and will not be needed for the mock path

## Installation

Create and activate a virtual environment, then install the local package:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

On macOS or Linux, activate with `source .venv/bin/activate`.

Optional development and AI2-THOR dependencies can be installed with:

```powershell
python -m pip install -e ".[dev]"
python -m pip install -e ".[thor]"
```

## Environment configuration

Copy `.env.example` to `.env` if a later phase will use an OpenAI-compatible endpoint. The project never commits `.env` and diagnostics report only whether variables are set, never their values.

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
```

## Run the Phase 0 diagnostic

Human-readable output:

```powershell
python scripts/check_environment.py
```

Machine-readable output:

```powershell
python scripts/check_environment.py --json
```

Use strict mode in CI or when checking readiness for all optional capabilities:

```powershell
python scripts/check_environment.py --strict
```

The default command succeeds when optional components are absent and explains the appropriate fallback. Strict mode returns a non-zero status if AI2-THOR, its controller, an API key, or likely graphical display support is unavailable.

## Tests

The Phase 0 tests use only the Python standard library:

```powershell
python -m unittest discover -s tests -v
```

They are also compatible with `pytest` after installing the development extra.

## Inspect scene objects

The deterministic mock path requires no AI2-THOR installation or graphical display:

```powershell
python scripts/list_scene_objects.py --mock
python scripts/list_scene_objects.py --mock --json
```

If the optional AI2-THOR dependency and graphical environment are available:

```powershell
python scripts/list_scene_objects.py --scene FloorPlan1
```

The real-environment command reports an actionable error when AI2-THOR or Unity rendering is unavailable. The mock path remains usable in that case.

## Run the verified live AI2-THOR smoke test

The verified Windows-host route uses Ubuntu 22.04 on WSL2/WSLg because upstream AI2-THOR does not officially list native Windows support. Setup details and exact dependency records are in [`docs/ai2thor_wsl_setup.md`](docs/ai2thor_wsl_setup.md).

```powershell
wsl --distribution Ubuntu-22.04 --user research -- bash -lc "cd /mnt/d/path/to/embodied-memory-thor && ~/embodied-memory-thor-runtime/.venv/bin/python scripts/smoke_ai2thor.py --scenes FloorPlan1 FloorPlan10"
```

The verified run started both scenes, recorded real metadata and pose, changed visible observations through movement/rotation, completed a valid object interaction, captured an intentional failed interaction, and saved RGB frames. This is E2 integration evidence, not a memory experiment.

## Run the minimal episode

Run the Phase 2 acceptance task without AI2-THOR or external APIs:

```powershell
python scripts/run_episode.py --mock --task put_apple_on_countertop --planner rule_based
```

Other configured tasks are:

```text
put_apple_on_plate
wash_apple_put_countertop
slice_apple_put_plate
po_slice_apple_put_plate
po_find_book_after_distraction
```

Each run creates a unique directory under `outputs/runs/<timestamp>/` containing:

- `episode.jsonl`: one record per attempted action, including visible objects, action outcome, decision trace, before/after memory snapshots, provenance, task milestones, interventions, latency, and goal state
- `summary.json`: success, steps, invalid-action, search/revisit, memory-hint, stale-recovery, audit, and latency metrics

Task success is evaluated only from object metadata. Planner text is never treated as evidence of success.

## Run the controlled partially observable harness

The Phase 2R mock assigns Apple, Knife, and Plate to distinct seeded regions and exposes only the current region/view to ordinary planners:

```powershell
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner rule_based_no_memory
```

The privileged oracle is available only as a solvability/debug upper bound:

```powershell
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner oracle_debug
```

The mock remains an abstract state harness: `MoveToRegion` does not simulate locomotion, collision, vision pixels, or physics. Phase 2R results are preliminary E1 harness evidence, not proof of AI2-THOR performance or memory benefit. See [`docs/partial_observability.md`](docs/partial_observability.md).

## Run Phase 3 memory variants

The three ordinary variants share one task policy and one deterministic fallback search cycle. They differ only in historical observation access:

```powershell
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner rule_based_no_memory
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner short_memory
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner object_memory
```

Run the controlled stale-memory condition:

```powershell
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner object_memory --stale-intervention
```

Run the frozen 54-episode pilot from a clean Git revision:

```powershell
python scripts/run_phase3_pilot.py
```

See [`docs/phase3_memory_experiment.md`](docs/phase3_memory_experiment.md) for the information boundary, constants, output files, and interpretation limits.

The accepted aggregate and per-layout results are in [`docs/phase3_results.md`](docs/phase3_results.md). Object memory reduced mean stable-task steps/moves by 0.5 in both task structures, while all stale ObjectMemory episodes exposed and recovered from an outdated last-seen record. These small deterministic results are reported without significance or broad-generalization claims.

## Repository layout

```text
configs/tasks.yaml              Validated Phase 2 task definitions
docs/                            Public-facing project documentation
outputs/                         Generated run artifacts (ignored except .gitkeep)
scripts/check_environment.py     Environment diagnostic CLI
scripts/smoke_ai2thor.py         Live AI2-THOR E2 integration smoke CLI
scripts/list_scene_objects.py    Real/mock scene inspection CLI
scripts/run_episode.py           Single-episode execution and logging CLI
scripts/run_phase3_pilot.py      Frozen Phase 3 matrix, manifest, aggregation, and acceptance
src/embodied_memory_thor/        Installable Python package
tests/                           Automated tests
```

See [`docs/development_status.md`](docs/development_status.md) for the phase-by-phase status.

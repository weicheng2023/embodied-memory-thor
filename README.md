# Embodied-Memory-THOR

A lightweight memory and evaluation layer for LLM-based embodied agents in AI2-THOR.

## Status

Phases 0–1 are implemented: project scaffolding, non-destructive environment diagnostics, a deterministic mock kitchen, a lazy AI2-THOR adapter, safe object parsing, and scene-object inspection. Task execution, memory, planners, and experiments are planned for later phases and are not yet claimed as complete.

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
- Windows, macOS, or Linux
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

The Phase 2 target episode command is not available yet:

```powershell
python scripts/run_episode.py --mock --task put_apple_on_countertop --planner rule_based
```

## Repository layout

```text
configs/                         Task and planner configuration (later phases)
docs/                            Public-facing project documentation
outputs/                         Generated run artifacts (ignored except .gitkeep)
scripts/check_environment.py     Environment diagnostic CLI
scripts/list_scene_objects.py    Real/mock scene inspection CLI
src/embodied_memory_thor/        Installable Python package
tests/                           Automated tests
```

See [`docs/development_status.md`](docs/development_status.md) for the phase-by-phase status.

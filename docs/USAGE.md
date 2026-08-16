# Usage and reproduction

This guide contains the operational material intentionally kept out of the
research-facing README. Choose the shortest path that matches what you want to
verify.

| Goal | Recommended path |
| --- | --- |
| Understand the research claim | Start with the [README](../README.md), then read the [research report](report.md). |
| Check the code without AI2-THOR | Install the development extra and run the offline test suite. |
| Inspect the observation-memory-planner loop | Run a mock episode; no simulator or API key is required. |
| Verify the real simulator | Follow the tested WSL2/WSLg setup and run the AI2-THOR smoke test. |
| Audit accepted results | Read the Phase-5 and Phase-7 result documents before attempting a formal rerun. |

## Requirements

- Python 3.10 or newer;
- Windows, macOS, or Linux for the mock/offline path;
- Ubuntu 22.04 under WSL2/WSLg for the verified live AI2-THOR path;
- no API key unless the optional OpenAI-compatible planner is used.

## Installation

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

## Offline validation

Run the repository-facing research checks before changing evidence or claims:

```powershell
python scripts/check_research_consistency.py
python -m pytest -q
```

These checks do not require AI2-THOR or an external API.

## Mock development path

Run one minimal episode:

```powershell
python scripts/run_episode.py --mock --task put_apple_on_countertop --planner rule_based
```

Each run writes `episode.jsonl` and `summary.json` under a unique
`outputs/runs/<timestamp>/` directory.

Run the controlled symbolic partial-observation variants:

```powershell
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner rule_based_no_memory
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner short_memory
python scripts/run_episode.py --mock --partial-observability --seed 0 --task po_slice_apple_put_plate --planner object_memory
```

The privileged `oracle_debug` variant is a solvability upper bound only. Phase
3 is symbolic E1 evidence, not proof of real-simulator memory improvement. See
the [Phase-3 protocol](phase3_memory_experiment.md) and
[results](phase3_results.md).

## Real AI2-THOR integration

The verified Windows-host route uses Ubuntu 22.04 under WSL2/WSLg. Complete the
[tested environment setup](ai2thor_wsl_setup.md), then run:

```powershell
wsl --distribution Ubuntu-22.04 --user research -- bash -lc "cd /mnt/d/path/to/embodied-memory-thor && ~/embodied-memory-thor-runtime/.venv/bin/python scripts/smoke_ai2thor.py --scenes FloorPlan1 FloorPlan10"
```

The smoke test is the public, bounded check for simulator startup, RGB rendering,
metadata, movement, interaction, and an intentional failure path.

### Auditable episode trace

The general trace interface can be exercised with:

```bash
python scripts/run_thor_episode.py \
  --scene FloorPlan1 \
  --task thor_book_reacquire \
  --planner object_memory \
  --mode debug \
  --trace-html
```

This is a diagnostic interface example, not an accepted formal row. Its task
outcome can depend on the current scene layout and distraction preconditions.
RGB is a human-audit artifact; the planner consumes visible metadata. Setup
actions and optional evaluator debug state are kept separate from planner
metrics.

Inspect mock or real scene objects with:

```powershell
python scripts/list_scene_objects.py --mock
python scripts/list_scene_objects.py --scene FloorPlan1
```

## README research visuals

The architecture figure and Phase-7B chart are deterministic, code-generated
SVGs:

```bash
python scripts/render_readme_assets.py
```

The presentation GIF additionally requires the verified real-THOR runtime and
the local evaluator-only Phase-7 registry:

```bash
python scripts/run_readme_demo.py
python scripts/render_readme_assets.py \
  --trace-dir outputs/readme_presentation_source
```

The GIF is explanatory presentation material, not a formal comparison row. Its
role and hashes are documented in the
[visual-asset manifest guide](assets/readme/README.md).

## Formal evidence boundary

Accepted Phase-5 and Phase-7 results are already published as compact summaries
under `docs/evidence/`. A complete formal-matrix rerun additionally requires the
historical local evaluator-only registries described in
[`configs/evaluator_only/README.md`](../configs/evaluator_only/README.md).

Do not reconstruct missing private inputs and present the resulting run as the
accepted checkpoint. The public repository supports:

- full offline validation of planner/evaluator boundaries and aggregation;
- inspection of frozen public protocol and route contracts;
- live AI2-THOR integration checks;
- deterministic regeneration of public descriptive summaries and diagrams.

The detailed script roles and historical/superseded entry points are indexed in
[`scripts/README.md`](../scripts/README.md).

## Environment diagnostics and optional planner

Optional OpenAI-compatible configuration belongs in an untracked `.env` file:

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
```

Report capabilities without exposing secret values:

```powershell
python scripts/check_environment.py
python scripts/check_environment.py --json
```

## Repository map

```text
configs/                            Public task, protocol, and route contracts
configs/evaluator_only/             Schema only; hidden frozen registries stay local
docs/evidence/                      Compact public qualification and result evidence
docs/phase5_experiment_protocol.md  Chronological protocol-development audit
docs/phase5_formal_results.md       Accepted descriptive result and claim boundary
docs/phase7/                        Frozen successor protocols and accepted results
outputs/                            Generated run artifacts, ignored except .gitkeep
scripts/                            Diagnostics, execution, aggregation, presentation
src/embodied_memory_thor/           Environment, memory, planner, evaluator, trace code
tests/                              Offline contracts and regression coverage
```

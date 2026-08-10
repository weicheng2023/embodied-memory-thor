# Phase 4 Real-THOR Execution and Trace

Implementation status: protocol-v2 corrected single live case passed; broader offline acceptance remains pending.

Phase 4 connects the visible-observation memory path to a real AI2-THOR episode
while preserving a strict planner/evaluator boundary. A successful first run will
be E2 closed-loop integration evidence, not evidence that memory outperforms a
no-memory baseline.

## Controlled task

The initial task is `thor_book_reacquire` on `FloorPlan1`:

1. record reset observation through planner-safe metadata and in-memory RGB statistics;
2. when Book is absent, run the fixed planner-independent setup `RotateRight`, `MoveAhead`, `RotateRight` and log it separately;
3. make the resulting visible/pickupable Book view `observation:0` and write its object/camera-pose record;
4. rotate until Book leaves the visible set, retrieve the record, and return toward its last-seen camera pose;
5. reacquire Book and issue `PickupObject` using its currently visible ID;
6. use full metadata only in the evaluator to calculate the final success boolean.

Setup actions use no hidden metadata and are excluded from planner steps, latency, and memory-guided action counts. A setup failure still leaves a complete `setup.jsonl` record.

`configs/phase4_tasks.yaml` keeps this real task separate from the frozen mock task
panel. `configs/phase4_acceptance.yaml` contains exactly one first acceptance case.

## Information boundary

The runner creates an exact `PlannerRequest` containing only:

- task instruction and visible-observation-derived task stage;
- current whitelisted agent pose and inventory;
- normalized objects currently marked visible;
- supported action names;
- retrieved visible-history memory with observation provenance;
- recent action success/failure records.

The request is hashed and audited before each planner call. The audit rejects
hidden objects, known evaluator-only keys, a sentinel evaluator canary, or memory
whose source object was not visible in the cited observation.

The metadata planner does not consume the RGB frame. Every visual artifact is
labeled:

> Agent camera frame — human-visible artifact; not consumed by the metadata planner

The ordinary `episode.jsonl` stores only the planner-safe request and evaluator
success boolean. If `--save-evaluator-debug` is explicitly enabled, complete
metadata is written to a separate `evaluator_debug.jsonl` labeled:

> EVALUATOR ONLY — NOT PLANNER INPUT

## One engine, two presentations

`ThorEpisodeRunner` owns reset, observation, retrieval, planning, action execution,
memory update, and success checking. Formal and debug modes call this same engine.

- Formal mode adds no window or artificial delay.
- Debug mode prints the four trace panels to the console.
- `--visualize` optionally opens only the current RGB frame through OpenCV.
- Frame saving, console output, HTML rendering, and delay occur outside the planner.
- `compare_trace_parity` can compare formal/debug semantic records while ignoring
  timestamps, frame paths, and presentation timing.

## Outputs

```text
outputs/thor_runs/<timestamp>/<episode_id>/
  run_manifest.json
  setup.jsonl
  episode.jsonl
  summary.json
  frames/                     # optional; absent by default
    step_001_observation.png
  trace.html
  evaluator_debug.jsonl    # only when explicitly enabled
```

`setup.jsonl` records reset/setup safe observations, fixed actions, outcomes, and RGB-array diagnostics separately from evaluated planner steps. Each step in `episode.jsonl` has four aligned sections:

- `observation`: in-memory RGB shape/hash/brightness diagnostics, optional frame path/hash, and RGB boundary label;
- `planner_input`: exact request plus information-boundary audit;
- `planner_decision`: validated action, memory provenance, reason, and planner time;
- `environment_feedback`: result/error, post-action safe observation, memory diff,
  task progress, and evaluator-only success boolean.

Planner, simulator-action, and artifact-capture timings are recorded separately.

## Planners

The first acceptance route uses `ThorBookReacquirePlanner`, a deterministic planner
that receives only `PlannerRequest`. It restores the last-seen position, heading,
and camera horizon, and falls back to a systematic rotation scan when memory is
unavailable.

An optional OpenAI-compatible planner uses the Responses API structured-output
path and validates its result through the same action, visibility, and memory
provenance checks. It is not used by the first acceptance case and never receives
RGB or evaluator metadata.

## First bounded test result

The following single formal case was run once on 2026-08-10:

```bash
python scripts/run_thor_episode.py \
  --scene FloorPlan1 \
  --task thor_book_reacquire \
  --planner object_memory \
  --mode formal \
  --trace-html
```

Equivalent manifest command, also limited to one case by default:

```bash
python scripts/run_thor_batch.py \
  --manifest configs/phase4_acceptance.yaml \
  --mode formal \
  --limit 1
```

It reached live AI2-THOR and stopped before the planner at
`initial_visible_book_missing`. The formal output contained a manifest, summary,
empty `episode.jsonl`, and HTML trace, but no observation-0 frame. This is a failed
acceptance gate and a task-initialization/auditability finding, not a planner or
memory result.

Protocol v2 implements that correction without desktop capture. It records raw
`event.frame` array shape, dtype, hash, byte statistics, near-black fraction, and
all-black suspicion; PNG saving remains optional. The fixed setup sequence is
stored separately and excluded from planner metrics. One targeted local test and
one rerun of this same live case are the only next checks; debug mode, no-memory
comparison, external-planner calls, additional scenes, and repeated runs remain
out of scope.

## Corrected bounded result

The v2 rerun completed successfully with no visualizer and no saved image files.
Setup used three separately logged actions. The evaluated trace then executed
`RotateRight`, memory-guided `RotateLeft`, and `PickupObject`, all successfully.
All seven direct RGB arrays were `300x300x3`, had distinct hashes and nonzero
variation, and were not classified as all black. The information-boundary audit
passed with zero invalid actions. This is one-case E2 evidence only; offline
failure/parity/regression gates still precede any Phase 5 comparison.

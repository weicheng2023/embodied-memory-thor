# Persistent Object Memory in Partially Observable AI2-THOR Tasks

## Project type

This is a lightweight research preparation project about memory, context, and
auditable evaluation in embodied agents. It is not a state-of-the-art method,
does not train a vision-language-action model, and does not claim transfer to a
physical robot. Its contribution is a controlled case study developed through
adaptive protocol qualification, followed by a fixed real-simulator comparison
and two separately frozen successor studies in which memory access is isolated
from search capability and hidden evaluator state. It is not positioned as an
externally valid preregistered benchmark.

## Motivation

An embodied agent acts from a local view. When a target leaves the camera, the
current observation no longer says where it was, whether a previous interaction
failed, or whether the world may have changed. A useful context system should
preserve relevant visible history, help the agent reacquire targets, and stop
trusting a record when new evidence contradicts it.

Showing that behavior rigorously is harder than building a successful demo. A
memory agent can appear better if the no-memory baseline is forbidden to search,
if the planner secretly reads global metadata, or if only one hand-selected
scene is shown. This project therefore focuses on matched capabilities,
planner/evaluator separation, fixed scene qualification, negative stale-memory
cases, and complete reruns after protocol corrections.

## Research question

In matched partially observable AI2-THOR tasks, does persistent visible-history
object memory reduce target reacquisition effort relative to a capable no-memory
search policy and exact-K short-term memory?

The tested comparison uses a deterministic metadata planner. It studies memory
access and downstream navigation, not pixel perception or LLM reasoning quality.

## Related work and positioning

[Kolve et al. (2017)](https://arxiv.org/abs/1712.05474) introduced AI2-THOR as
an interactive 3D environment for visual agents that can navigate and manipulate
objects. Persistent semantic/object memory is not new: the
[Object Memory Transformer](https://arxiv.org/abs/2203.14708) of Fukushima et
al. (2022), for example, uses long-term object and scene observations for Object
Goal Navigation. Embodied-navigation research also includes broader semantic and
spatial mapping approaches. This project makes no architecture-novelty claim;
its narrower contribution is a controlled comparison of lightweight
visible-history memory against search-capable baselines while excluding
privileged simulator state from planner decisions.

## System design

One episode engine connects an environment, safe observation parser, memory
provider, structured planner, action executor, task-progress tracker,
state-based evaluator, and trace writer. The same engine serves formal batch and
debug presentation modes.

In Phase 5 and Phase 7A, three memory variants share the same task, start,
action space, planner logic, target lock, systematic fallback, recovery
policies, limits, and evaluator:

- `no_memory` stores no historical observation but can execute the complete
  target-independent search route;
- `short_memory_k2` stores exactly the last two safe observations, causing the
  initial target record to be evicted after the controlled distraction;
- `object_memory` stores persistent visible-derived last-seen object and camera
  records, and can mark a record suspected stale after a remembered-view miss.

The planner receives only current visible objects, safe agent/inventory state,
retrieved visible-history memory, available actions, and ordinary action/failure
history. Full metadata is available only to setup and success evaluation.
Evaluator-only relocation destinations and native actions are stored separately.
The exact planner request is hashed and checked on every step.

The architecture and information boundary are detailed in
[architecture.md](architecture.md).

## Tasks and experimental panels

The accepted Phase-5 matrix contains 18 matched configuration cells across
three panels (six per panel), each evaluated under three variants, for 54
executions total. These are not 54 independent environments or independent
samples.

### R1 stable: Book reacquisition

The agent first observes a pickupable Book. A target-independent turn and
absolute-horizon distraction hides it and evicts the initial observation from
K=2. The agent must reacquire and pick up the Book. This is the simplest test of
whether persistent last-seen context avoids part of a fallback search.

### R2 stable: ordered Cup/CoffeeMachine task

The agent first observes a Cup, must find and toggle a CoffeeMachine while Cup
is out of view, then reacquire and pick up Cup. The intermediate subgoal makes
this longer and exposes whether memory guidance composes efficiently with
navigation and task order.

### R1 stale: hidden Book relocation

After the initial Book is hidden, an evaluator-only intervention moves it to a
prequalified frozen anchor. The planner never receives the destination. Object
memory may revisit the remembered view, mark a miss, fall back to the same
systematic search as the baselines, rediscover Book, and refresh its record.

## Qualification and reproducibility

Scene availability was not inferred from object stereotypes. R1 and R2 scenes,
starts, target-independent routes, and stale anchors were qualified in fixed
orders with rejected candidates retained. Public route contracts contain action
names and digests; private coordinates remain in Git-ignored evaluator registries.

This qualification was adaptive protocol development. Book availability, route
budgets, candidate visibility, camera horizons, pickup collisions, and frozen
route failures all informed later task and policy contracts. Success in the final
panels is therefore conditional on substantial scene/task engineering and should
not be interpreted as out-of-sample benchmark performance.

The formal manifest fixed one clean pushed revision, 54-execution ordering,
controller parameters, policies, 72 required metrics, no-image/no-GUI output,
and a 2048-action ceiling. An integrity failure invalidated a partial matrix and
required a new protocol version plus a complete fresh rerun. Formal-v2, v3, and
v4 were each retained and excluded after discovering, respectively, distraction,
pickup recovery, and route-execution defects. Formal-v5 completed 54/54.

The result summary was hash-frozen before a separately committed deterministic
aggregator read it. Two aggregations produced byte-identical JSON and Markdown.

## Metrics

Primary outcomes were task success, evaluated steps, actions from the hidden
milestone to target rediscovery, translation actions/distance, search rotations,
and repeated viewpoint visits. Integrity and mechanism metrics included invalid
planner/native actions, information-boundary checks, K=2 eviction, memory-guided
actions, shared fallback/entry recovery, old-viewpoint misses, stale recovery,
and target-lock recovery.

With only six deterministic matched configurations per panel, analysis was
predefined as descriptive: per-configuration paired differences, means,
medians, ranges, and better/tie/worse counts. Panels were not pooled. No
significance test was performed.

## Results

All 54 executions succeeded and all information-boundary checks passed. Final
success was therefore saturated and is not evidence that one memory condition
was superior. The informative outcomes are action efficiency, reacquisition
effort, search rotations, translation/navigation overhead, and stale-memory
recovery. K=2 and no-memory were identical on every primary metric in all three
panels, consistent with the target record being evicted before reacquisition.

| Panel | Mean steps: No / K=2 / Object | Object - No steps | Mean reacquisition actions: No / K=2 / Object | Object - No reacquisition |
| --- | ---: | ---: | ---: | ---: |
| R1 stable | 7.33 / 7.33 / 7.17 | -0.17; 2 better, 3 ties, 1 worse | 5.00 / 5.00 / 4.50 | -0.50; 3 better, 3 ties |
| R2 stable | 28.50 / 28.50 / 32.00 | +3.50; 1 better, 1 tie, 4 worse | 21.50 / 21.50 / 23.83 | +2.33; 1 better, 3 ties, 2 worse |
| R1 stale | 43.33 / 43.33 / 43.33 | 0.00; 6 ties | 41.00 / 41.00 / 41.00 | 0.00; 6 ties |

For R1 stable, persistent memory produced a small conditional reacquisition-
efficiency gain: three configurations saved one reacquisition action and three
tied. Repeated viewpoint visits also fell by one on average. Overall episode
steps improved only slightly because one native interaction required an extra
action.

For R2 stable, memory reduced mean search rotations by 3.17, showing that the
agent did use last-seen context instead of only blind scanning. Yet translation,
route re-entry, and target approach costs dominated: total steps increased by
3.5 and reacquisition actions by 2.33 on average. FloorPlan4 improved strongly,
whereas FloorPlan6 regressed strongly and used 14 entry-recovery actions.

In R1 stale, object memory completed every task and matched baseline principal
costs after fallback. Five configurations produced explicit old-viewpoint misses
and five stale-record corrections. In FloorPlan303, restoring the remembered
camera horizon directly revealed the relocated Book, so no stale miss was
emitted; this limitation is retained in the result.

Exact paired vectors and mechanism totals are available in
[phase5_formal_results.md](phase5_formal_results.md) and the linked JSON evidence.

## Phase 7 successor evidence

Phase 7A tested the unchanged three-condition R1 policy on the first six
configurations passing a rule fixed before outcomes. FloorPlan308 through
FloorPlan313 received no scene-specific repair after comparative execution
began. All 18 fresh episodes succeeded. Object memory used one fewer total and
reacquisition action in five configurations and tied in one; K=2 again matched
no memory. This is a frozen holdout result, but a narrow one: every episode used
rotation only, with no translation, fallback route, invalid action, or failed
interaction.

Phase 7B then evaluated no memory, recent-observation K=2/K=4/K=8, and object
memory in 30 fresh episodes under one separately frozen revision. The target was
retained in 0/6 K=2, 2/6 K=4, and 6/6 K=8 conditions. K=8 and object memory
matched on retention, total actions, and reacquisition actions in all six
configurations. In this simple rotational panel, sufficient recent-context
length reproduced the small efficiency pattern; the study provides no evidence
of an additional benefit from structured object representation or retrieval.
It does not establish that the memory systems are generally equivalent.

The holdout and horizon results, exact paired vectors, integrity metadata, and
limitations are under [phase7/](phase7/README.md). They are additive successor
evidence and do not alter the Phase-5 canonical result.

## Failure analysis

The development history exposed three broad lessons.

First, task initialization and visibility must be empirically qualified. The
first live task failed because Book was not visible at reset, and later
distraction templates failed because initial horizon and near-field geometry
violated simple assumptions.

Second, native simulator actions and fixed routes require bounded, explicit
failure handling. Pickup collision once caused repeated actions to the limit;
a persistent FloorPlan10 obstacle survived stabilization and retry. Both were
treated as protocol defects or scene ineligibility, not favorable memory data.

Third, a correct memory record does not guarantee efficient control. R2 object
memory reduced scanning but sometimes moved the agent away from a frozen route
entry and paid recovery cost. This is the most useful negative result because it
turns a vague "memory helps" story into a concrete navigation research question.

The full taxonomy and evidence links are in [failure_cases.md](failure_cases.md).

## Limitations

- Six deterministic configurations per panel support only task-specific
  descriptive evidence.
- The planner consumes metadata, not pixels; visual perception errors are not
  tested.
- The formal policy is deterministic and hand-engineered. The optional
  OpenAI-compatible planner was not part of the comparison.
- AI2-THOR is a simulator; object placement, physics, and navigation do not
  establish real-robot performance.
- R1 is short and often needs only camera actions, producing a small ceilinged
  advantage. R2 reveals larger route-policy dependence.
- Stale anchors were qualified, but one scene did not force an explicit stale
  miss across the full remembered camera-restoration sequence.
- Tasks, scenes, routes, and recovery policies were co-developed through a long
  qualification process. This improves internal auditability but limits external
  validity and leaves a larger engineering surface than an ideal minimal study.
- The three complete conditions do not independently isolate memory persistence,
  capacity, representation structure, or retrieval mechanism. In particular,
  exact K=2 recent observations and persistent object records differ along
  several dimensions, so Phase 5 cannot assign the paired differences to any
  one memory property.

## Future work

1. Replace direct last-seen pose restoration with uncertainty-aware viewpoint
   ranking that accounts for path cost and route re-entry.
2. Add stronger stale anchors that remain hidden across every remembered camera
   restoration, then test stale cost as a controlled independent variable.
3. Extend the frozen-policy holdout design to broader scenes, layouts, target
   types, translation-heavy tasks, and randomized initial conditions; retain
   failures without task-specific repair, then use inferential analysis only if
   sample size supports it.
4. Add pixel-based object detection while preserving the same planner/evaluator
   boundary, allowing perception and memory errors to be separated.
5. Evaluate the optional structured LLM planner as a distinct study, reporting
   tokens, latency, invalid actions, and prompt/context ablations.
6. Reduce legacy qualification scripts into a smaller reproducible evaluation
   command without deleting historical evidence.

## Conclusion

The project establishes a reproducible real AI2-THOR pipeline in which persistent
object memory can be compared fairly with capable limited/no-memory baselines.
Its primary contribution remains the controlled protocol-development case and
the internal validity of the fixed comparisons, not an externally validated
benchmark. Phase 5 found a small Book-reacquisition gain, worse overall cost in
the longer ordered Cup task, and bounded stale correction. Phase 7A reproduced a
small action difference on six frozen holdout configurations but exercised no
navigation, while Phase 7B found that K=8 recent memory reproduced object-memory
behavior in the same simple setting. The main lesson is that retention horizon,
representation, and memory-conditioned navigation must be evaluated separately:
remembering the right place matters only when the agent retains and exploits the
information efficiently.

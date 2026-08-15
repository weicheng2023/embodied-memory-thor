# Persistent Object Memory in Partially Observable AI2-THOR Tasks

## Project type

This is a lightweight research preparation project about memory, context, and
auditable evaluation in embodied agents. It is not a state-of-the-art method,
does not train a vision-language-action model, and does not claim transfer to a
physical robot. Its contribution is an audited protocol-development case study
followed by a frozen real-simulator comparison in which memory access is isolated
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

## System design

One episode engine connects an environment, safe observation parser, memory
provider, structured planner, action executor, task-progress tracker,
state-based evaluator, and trace writer. The same engine serves formal batch and
debug presentation modes.

Three memory variants share the same task, start, action space, planner logic,
target lock, systematic fallback, recovery policies, limits, and evaluator:

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
The exact planner request is hashed and audited on every step.

The architecture and information boundary are detailed in
[architecture.md](architecture.md).

## Tasks and experimental panels

The accepted matrix contains three panels, each with six frozen matched
configurations and three variants, for 54 episodes total.

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

The formal manifest fixed one clean pushed revision, 54-cell ordering,
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

All 54 episodes succeeded and all integrity audits passed. K=2 and no-memory
were identical on every primary metric in all three panels, consistent with the
target record being evicted before reacquisition.

| Panel | Mean steps: No / K=2 / Object | Object - No steps | Mean reacquisition actions: No / K=2 / Object | Object - No reacquisition |
| --- | ---: | ---: | ---: | ---: |
| R1 stable | 7.33 / 7.33 / 7.17 | -0.17; 2 better, 3 ties, 1 worse | 5.00 / 5.00 / 4.50 | -0.50; 3 better, 3 ties |
| R2 stable | 28.50 / 28.50 / 32.00 | +3.50; 1 better, 1 tie, 4 worse | 21.50 / 21.50 / 23.83 | +2.33; 1 better, 3 ties, 2 worse |
| R1 stale | 43.33 / 43.33 / 43.33 | 0.00; 6 ties | 41.00 / 41.00 / 41.00 | 0.00; 6 ties |

For R1 stable, persistent memory produced a small, clean reacquisition benefit:
three configurations saved one reacquisition action and three tied. Repeated
viewpoint visits also fell by one on average. Overall episode steps improved
only slightly because one native interaction required an extra action.

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

## Failure analysis

The development history exposed three broad lessons.

First, task initialization and visibility must be empirically qualified. The
first live task failed because Book was not visible at reset, and later
distraction templates failed because initial horizon and near-field geometry
violated simple assumptions.

Second, native simulator actions and frozen routes require bounded, auditable
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

## Future work

1. Replace direct last-seen pose restoration with uncertainty-aware viewpoint
   ranking that accounts for path cost and route re-entry.
2. Add stronger stale anchors that remain hidden across every remembered camera
   restoration, then test stale cost as a controlled independent variable.
3. Freeze a successor before touching new holdout scenes, layouts, target types,
   and randomized initial conditions; report holdout failures without
   task-specific repair, then use inferential analysis only if sample size
   supports it.
4. Add pixel-based object detection while preserving the same planner/evaluator
   boundary, allowing perception and memory errors to be separated.
5. Evaluate the optional structured LLM planner as a distinct study, reporting
   tokens, latency, invalid actions, and prompt/context ablations.
6. Reduce legacy qualification scripts into a smaller reproducible evaluation
   command without deleting historical evidence.

## Conclusion

The project establishes a reproducible real AI2-THOR pipeline in which persistent
object memory can be compared fairly with capable limited/no-memory baselines.
Its primary research contribution is the audited protocol-development case and
the internal validity of the final frozen comparison, not an externally validated
benchmark. The result is deliberately conditional: object memory helped simple
Book reacquisition, did not improve the longer ordered Cup task overall, and
recovered from stale information without task failure. The main research lesson
is that memory representation and memory-conditioned navigation must be evaluated
together; remembering the right place is useful only when the agent can exploit
that information efficiently.

# Failure Cases and Engineering Lessons

Failures were retained as evidence rather than erased after a fix. The table
separates simulator/task problems from memory effects, because treating every
failure as an agent failure would produce misleading comparisons.

| Failure class | Observed example | Diagnosis | Response and remaining lesson |
| --- | --- | --- | --- |
| Target not visible under an assumed start | The first real Phase 4 run reached AI2-THOR but stopped at `initial_visible_book_missing`. | The scene was rendering; the task's start-view assumption was wrong. | Added planner-independent setup with separate logs and direct RGB-array diagnostics. Availability must be qualified, not assumed from scene semantics. |
| Relative camera action invalid at a horizon limit | FloorPlan303's first distraction successor failed on `LookDown` because the start was already at the lower horizon bound. | A relative action template was not invariant to initial camera state. | Replaced it with absolute-horizon alignment from planner-safe pose, including tolerance and action caps. |
| Object remains visible after distraction | Formal-v2 stopped when a half-turn did not hide the near-field Book in FloorPlan303. | Yaw-only occlusion was not guaranteed at a steep downward horizon. | Introduced target-independent absolute-horizon distraction v4 and reran the complete matrix; no partial row was reused. |
| Valid interaction rejected by simulator | Formal-v3's FloorPlan306 object-memory cell reacquired Book, but pickup collided at horizon 0 and the old policy retried until the limit. | Error classification matched a stack-trace substring and recovery was unbounded. | Target-lock v2 reads only the ordinary first-line error, restores a fixed -30-degree horizon, retries once, and terminates explicitly on failure. One legal rejection remains a performance event, not hidden. |
| Frozen route blocked at execution | Formal-v4 stopped when FloorPlan10 rejected `MoveAhead` at coverage index 200, even though qualification replay had passed. | A persistent obstacle made the route execution-ineligible; one `Pass` plus exact retry also failed. | Preserved the failure, excluded FloorPlan10 under a preregistered rule, qualified FloorPlan17, and reran all 54 cells from scratch. Scene physics can invalidate a previously valid path. |
| Search construction exceeds budget | The original visual fallback scanned every reachable node at two horizons and exceeded the 2048 bound in several R2 scenes. | Complete dense coverage was too expensive, not a memory failure. | Added deterministic target-independent viewpoint sampling and a fixed scan template. Over-budget construction is classified and skipped before memory variants run. |
| Memory-guided route entry mismatch | In the excluded FloorPlan6 probe, object memory moved away from the captured fallback entry; the shared route then failed closed. | Memory navigation and a route with a fixed entry contract were composed without transition recovery. | Added bounded action-only inverse entry recovery shared by all variants. It restored correctness, but the formal result showed 14 extra recovery actions and worse R2 cost. |
| Stale memory does not always yield an explicit miss | In formal stale FloorPlan303, the Book was relocated and initially hidden, but restoring the remembered horizon made its new location visible. | The moved object was observable from the old position at a different camera horizon. | Reported only 5/6 explicit stale misses/recoveries. The episode is valid, but the panel does not prove a stale miss in every configuration. Stronger future anchors should require hiddenness across the full remembered camera-restoration sequence. |
| GUI fails while simulator works | An early `cv2.imshow()` debug run hit Qt's `xcb` platform-plugin abort under WSL/headless display conditions. | Presentation process failure, not AI2-THOR or planner failure. | Moved OpenCV to a child process and made saved frames/JSON/HTML authoritative. Formal experiments use no GUI or screenshots. |
| Read-only-looking simulator query perturbs or exposes noisy state | Support census work found state-digest changes around spawn-coordinate queries, while matched controls also showed natural settling noise. | The original digest/query assumptions were too strong for causal attribution. | Used fresh-reset matched controls, then adopted semantic support policy plus real native placement qualification. Query data remains evaluator-only and is never used online by the planner. |

## Failure taxonomy used in interpretation

- **Setup/qualification failure:** the requested task instance cannot be fairly
  initialized; no memory comparison is run.
- **Planner/schema failure:** an illegal action or information leak; the episode
  and, under formal rules, the partial matrix are invalid.
- **Native action rejection:** a legal action rejected by AI2-THOR. This is
  visible agent performance unless a frozen integrity contract says otherwise.
- **Task failure:** the episode remains integrity-valid but does not meet the
  environment-state goal; it stays in a fixed aggregate.
- **Infrastructure/presentation failure:** GUI, frame rendering, dependency, or
  artifact errors are isolated from task semantics and reported separately.
- **Memory failure:** stale guidance, nonprogress, or extra navigation caused by
  historical context. It must be separated from a deliberately weakened baseline.

## Most important negative result

The formal R2 panel shows why memory retrieval alone is insufficient. Object
memory reduced blind search rotations, but its navigation and route re-entry
overhead increased total steps in four of six configurations. This is not a
failed experiment. It identifies the next research problem: how to convert a
correct last-seen record into an efficient, uncertainty-aware navigation policy.

Detailed chronological evidence is preserved in
[the Phase 5 protocol](phase5_experiment_protocol.md) and its linked JSON files.

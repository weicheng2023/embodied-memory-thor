# Configuration

`tasks.yaml` contains the validated household task definitions. Each task declares its name, natural-language instruction, required object types, metadata-based goal conditions, and step limit.

`po_slice_apple_put_plate` is the Phase 2R controlled partial-observability task. Apple, Knife, and Plate occupy distinct seeded regions, forcing the agent to leave and revisit information that is no longer in its current observation.

`po_find_book_after_distraction` is the structurally different Phase 3 task. Book begins with Apple, DeskLamp begins with Knife, and an ordered milestone audit requires the lamp to be toggled before Book pickup.

`phase4_tasks.yaml` isolates controlled real-AI2-THOR task definitions from the
frozen Phase 0–3 mock task panel. `phase4_acceptance.yaml` currently contains
exactly one cautious acceptance case: `FloorPlan1`, `thor_book_reacquire`, and
the deterministic object-memory planner. It is not a Phase 5 comparison matrix.
The Phase 4 v2 case disables frame-file saving by default; it retains lightweight
in-memory RGB diagnostics and a raw array hash, which do not depend on desktop
window visibility or screenshots.

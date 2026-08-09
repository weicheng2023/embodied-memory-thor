# Configuration

`tasks.yaml` contains the validated household task definitions. Each task declares its name, natural-language instruction, required object types, metadata-based goal conditions, and step limit.

`po_slice_apple_put_plate` is the Phase 2R controlled partial-observability task. Apple, Knife, and Plate occupy distinct seeded regions, forcing the agent to leave and revisit information that is no longer in its current observation.

`po_find_book_after_distraction` is the structurally different Phase 3 task. Book begins with Apple, DeskLamp begins with Knife, and an ordered milestone audit requires the lamp to be toggled before Book pickup.

Scene and planner configuration files will be added only when later phases require them.

# Project Scorecard

Self-assessment date: 2026-08-14

Final score: **91/100 (A level)**

This is a conservative self-assessment against the original `guide.md` rubric.
The score reflects a complete, auditable real-simulator study, while retaining
deductions for limited scene count, metadata perception, deterministic formal
planning, and a large historical engineering surface.

| Category | Score | Evidence | Remaining gaps |
| --- | ---: | --- | --- |
| Reproducibility and environment robustness | 14/15 | [`docs/ai2thor_wsl_setup.md`](docs/ai2thor_wsl_setup.md), hash-bound formal manifests and stop rules in [`docs/phase5_experiment_protocol.md`](docs/phase5_experiment_protocol.md), clean 54/54 run in [`docs/evidence/phase5_real_formal_v5_complete.json`](docs/evidence/phase5_real_formal_v5_complete.json) | Verified primarily on one Windows 11 + Ubuntu 22.04 WSL2/WSLg machine; a second machine/container reproduction is still needed. |
| AI2-THOR / embodied environment integration | 14/15 | `ThorEnv`, visible-object parsing, action execution, RGB-array QA, JSONL/HTML traces, and crash-isolated viewer documented in [`docs/architecture.md`](docs/architecture.md) and [`docs/phase4_execution_trace.md`](docs/phase4_execution_trace.md) | Formal planner is metadata-based; pixel perception and cross-platform native rendering are not evaluated. |
| Task execution and success evaluation | 14/15 | R1 Book, R2 Cup/CoffeeMachine, and stale relocation panels; state-based evaluator; ordered-subgoal and target-lock audits; 54/54 formal successes | Only two target/task structures and 12 frozen real runtime configurations; no open-ended language task suite. |
| Memory/context system | 18/20 | Fair no-memory, exact K=2, and persistent object memory; provenance, failure history, stale marking/correction, and planner input audits; results in [`docs/phase5_formal_results.md`](docs/phase5_formal_results.md) | Memory retrieval is simple object-key lookup; no learned retrieval, uncertainty calibration, semantic consolidation, or long-horizon forgetting study. |
| Experiment and ablation quality | 13/15 | Fixed 54-cell matched matrix; six primary metrics, mechanism/integrity metrics, negative stale panel, retained invalidated runs, paired descriptive analysis, no selective reuse | Six configurations per panel do not support strong inference; formal study excludes LLM and perception ablations; no latency/token comparison for LLM planners. |
| Documentation and research communication | 9/10 | Complete README plus [`docs/report.md`](docs/report.md), [`docs/architecture.md`](docs/architecture.md), [`docs/failure_cases.md`](docs/failure_cases.md), and [`docs/application_abstract.md`](docs/application_abstract.md) | A shorter slide/poster version and independent reader feedback would improve presentation readiness. |
| Code quality and maintainability | 9/10 | Modular environment/action/memory/planner/evaluator/logging packages; structured configs; privacy gates; 422 passing tests plus 70 subtests at Phase 6 completion | Qualification history created many versioned scripts/configs; a smaller stable benchmark CLI and CI matrix would reduce maintenance cost. |
| **Total** | **91/100** | **A level: suitable for GitHub and a research-preparation application when claims retain the documented boundary.** | **The strongest next investment is a preregistered memory-to-navigation successor with more scenes, not a cosmetic rerun of the existing matrix.** |

## Why this is not scored higher

The project demonstrates serious experimental discipline, real AI2-THOR
integration, and an honest mixed result. It does not demonstrate robust visual
perception, learned planning, statistical generalization, physical deployment,
or independent reproduction. Those omissions are substantive research limits,
not documentation details, so a perfect or near-perfect score would be
misleading.

## Recommended evidence package for a supervisor

1. [`docs/application_abstract.md`](docs/application_abstract.md) for the short
   project summary.
2. [`docs/report.md`](docs/report.md) for the research narrative.
3. [`docs/phase5_formal_results.md`](docs/phase5_formal_results.md) for the result
   table and interpretation.
4. [`docs/architecture.md`](docs/architecture.md) for the information boundary
   and implementation design.
5. [`docs/failure_cases.md`](docs/failure_cases.md) for negative evidence and
   engineering judgment.
6. [`docs/phase5_experiment_protocol.md`](docs/phase5_experiment_protocol.md) and
   [`docs/evidence/phase5_real_formal_v5_descriptive_results.json`](docs/evidence/phase5_real_formal_v5_descriptive_results.json)
   for detailed auditability.

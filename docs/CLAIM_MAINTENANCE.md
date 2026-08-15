# Claim Maintenance

This note identifies the source of truth for each research claim. Summary files
may point to canonical evidence; they do not replace it.

| Claim or record | Canonical owner |
| --- | --- |
| Phase-5 numerical results | `docs/phase5_formal_results.md` and `docs/evidence/phase5_*.json` |
| Phase-5 chronological protocol history | `docs/phase5_experiment_protocol.md` |
| Current development/research status | the top current-status section of `docs/development_status.md` |
| Current application-facing short summary | `docs/application_abstract.md` |
| Current public front door | `README.md` |
| Architecture and information boundary | `docs/architecture.md` |
| Development/tooling ownership | `docs/CONTRIBUTIONS_AND_REPRODUCIBILITY.md` |
| Phase-7 protocol and results | `docs/phase7/*` and `docs/evidence/phase7/*` |

## Rules

1. A new experiment never rewrites an older canonical result file.
2. Clearly labelled historical files may retain statements that were accurate at
   their recorded checkpoint.
3. Current-facing documents summarize canonical evidence; they are not primary
   evidence.
4. A numerical result has one canonical source. Other documents link to or
   accurately summarize it.
5. Current-facing documents are updated once after a successor study is accepted,
   not repeatedly during experiment development.
6. Phase-7 development status, rejected candidates, invalidations, and live notes
   stay in the Phase-7 namespace.
7. Invalidated experiments and negative outcomes remain documented and are not
   silently replaced or selectively reused.

Run `python scripts/check_research_consistency.py` with the offline test suite
before merging a research-facing change.

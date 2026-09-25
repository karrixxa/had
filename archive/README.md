# Original contributions

These supplied folders were moved intact during consolidation:

| Original location | Preserved location |
| --- | --- |
| `hfd_eda/` | `contributions/hfd_eda/` |
| `HFD_EDA_Peikun/` | `contributions/HFD_EDA_Peikun/` |

Both contain byte-identical `scripts/prepare.py` and `scripts/eda.py`. The `hfd_eda` contribution adds `eda_extra.py`, the pipeline diagram, tables, and a report draft. Peikun's contribution includes prepared data, an HTML report, core figures, and core statistics.

Original scripts and results remain unchanged for provenance. Their expected `data/8mergedtrain_w_coords.csv` input was absent in both delivered folders, so these are historical references rather than the active entry point. Original processed data and cached map data remain local and are ignored by Git.

The original root report draft moved to `docs/HFD_initial_report_draft_sections.md`; its source text matched the preserved `hfd_eda` draft, and a status note now links to current findings. Use `analysis/run_eda.py` for the current reproducible analysis. Earlier forecast scores and strong sensor/causal claims should be read with the qualifications in `docs/EDA_REVIEW.md`.

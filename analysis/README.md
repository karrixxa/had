# Active exploratory analysis

Run from the project root:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m analysis.run_eda
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m analysis.validate_outputs
```

The command works offline and reads the existing coordinate-enriched focused and full-network exports under `data/processed/`. Override their paths using `--input` and `--full-input`, and the report destination using `--output`. It fails on a missing schema or a focus set different from `config/eight_streets.json`. The downloader may emit dated filenames, which can be passed using these options.

Results: [readable report](../reports/eda/README.md), [browser report](../reports/eda/report.html), figures, aggregate CSV tables, and input hashes in `reports/eda/manifest.json`. The daily exposure table is generated locally and ignored by Git.

## Definitions

- Invalid: missing identifier/name/start, nonnumeric/nonfinite duration, or duration <= 0. Duplicates use FRA ID + parsed start + duration. Original source files are never overwritten.
- Episode: union of overlapping or touching half-open intervals at one crossing. A positive clear gap is not part of baseline blocked time.
- Span: first valid start through last valid end at that crossing.
- Eligible exposure: span minus entire clear gaps longer than 24 hours, a retrospective assumption rather than observed uptime. Alternate thresholds are sensitivity scenarios.
- Burden: exact union blocked minutes / eligible minutes. Calendar allocation splits intervals at midnight. Rates are computed from summed numerators and denominators.
- State: whether a crossing is blocked at an exact minute tick. Sub-minute intervals may contain no ticks. State metrics therefore differ from continuous-time burden.
- Matched season: July–August 2025 versus July–August 2026. Bootstrap intervals use 1,000 whole-day resamples of days with >=12 eligible hours, seed 20260925. They omit dependence between days and uncertainty in sensor status.
- Forecast diagnostics: issue timestamps sampled every five minutes; entire issue-to-target interval must be eligible. Training targets precede 2025-01-01; validation issue/target timestamps lie within 2025-01-01–2025-07-01; test starts 2025-07-01. Telephone is excluded from fitted baselines because it has no training data in this design.

No train identity, dispatch delay, causal relationship, or verified uptime is inferred from event records alone. See [review of the contributed analyses](../docs/EDA_REVIEW.md).

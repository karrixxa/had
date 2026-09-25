# Review of the contributed HFD analyses

## Scope and provenance

Reviewed both supplied preparation scripts, both core EDA scripts, extended EDA code, JSON results, summary tables, and the draft report. The preparation and core EDA scripts match byte for byte across the contributions, as do the two draft Markdown files. These represent a shared analytical foundation, not independent replications.

Peikun's core work covers spatial context, coverage, duration, time of day, residual wait, lead–lag, concurrency, and XGBoost forecasting. The extended contribution adds full-network inventory, merge/outage sensitivity, state transitions, day-of-week patterns, monthly patterns, split coverage, and report text. These are valuable exploratory questions; the consolidated workflow retains the raw inputs and revisits the measurement assumptions.

## Corrections and qualifications

| Finding in the contributed code | Why it matters | Consolidated treatment |
| --- | --- | --- |
| Both scripts expect an absent `data/8mergedtrain_w_coords.csv`; extended code expects another absent relative input | A clean checkout cannot reproduce the supplied outputs | Explicit CLI inputs default to available coordinate-enriched exports; input hashes recorded |
| Negative durations are clipped to zero, then the minute grid assigns at least one minute to each episode | An invalid event can become an apparent blockage | Exclude nonpositive/invalid durations; exact ticks and continuous intervals are separate |
| Episode gaps <=2 min are filled | Some observed clear time becomes labeled blocked, affecting targets and rates | Baseline unions overlaps only; 0/1/2/5-minute scenarios quantify added clear time |
| `build_outages` sorts starts and ends independently | Nesting can pair a start with the wrong preceding end and mismeasure gaps | Derive gaps from ordered disjoint union intervals |
| >24h silence is called downtime and other time is called reporting | Event-only data cannot distinguish a quiet crossing from a failed sensor | Use “assumed eligible exposure”; report alternative denominators |
| Suspect fault days use a centered rolling median of 29 active days | It uses future information and is not a 29-calendar-day baseline | Preserve as a retrospective hypothesis; retain days in the primary analysis |
| Minute bins floor starts, ceil ends, and force a minimum of one minute | Inflates occupancy, especially for sub-minute events | Burden uses continuous duration; discrete state samples exact minute ticks |
| `fig_predict`: `how` is already sampled every five minutes, then indexed using full-minute `th` values | This can raise an out-of-bounds error or select the wrong target-hour values | New baselines index the full timeline; archived model figures are not accepted as a verified rerun |
| Model split classifies training by issue time only | Training labels near the boundary can extend into the held-out period | Training cutoff applies to target time; evaluation issue and target stay within split |
| Only horizon endpoints are checked for observation | A target can cross a missing-data interval | Require every tick of the horizon to be eligible |
| Climatology feature is computed using the same training labels it predicts | In-sample target encoding requires additional care when used by a flexible learner | New climatology is a standalone train-only baseline, evaluated on later targets |
| Telephone has no data in the extended pre-2025 training split | Pooled headline scores conceal a cold-start crossing | Report split availability; omit Telephone from baselines requiring that training history |
| Concurrency figure only shows counts 0–5 | Higher counts are omitted if they occur | Include every count 0–8 and verify totals |
| Lead–lag plot labels peaks as “times more likely than chance” using distant lags as baseline | Distant lag counts do not establish a conditional probability or a randomized null; selection across many pairs/lags matters | Preserve as hypothesis-generating; new pairwise table reports joint denominators and descriptive lift |
| Draft calls a long duration impossible and infers timezone from missing spring-forward events | Neither explanation is established by the export alone | Flag long records for investigation and document naive timestamps/DST uncertainty |

## What was added

1. Exact overlap-union blocked time and midnight allocation, with per-crossing reconciliation.
2. Long-tail contribution to total blocked time, duration survival curves, and residual-time sample sizes.
3. Joint sensitivity of merge thresholds and silence thresholds, including no silence exclusion.
4. Monthly exposure and matched July–August year comparisons, with descriptive day-bootstrap intervals.
5. Pairwise joint blockage, all-nine-category concurrency, and hourly state estimates with eligible counts.
6. Small, reproducible forecast baselines with explicit temporal cutoffs and horizon eligibility.
7. Full/focus multiset reconciliation, stable duplicate-feed signatures, and hashed input provenance.

## Interpretation for the HFD project

Crossing blocked time measures a potential obstacle. Actual emergency response impact also depends on dispatch time, route choice, alternate crossings, queues, station assignment and travel time. The current export cannot measure that impact directly. Obtain sensor health and timestamp documentation before treating an inferred clear state as operational ground truth. Validate network connectivity and direction before using cross-crossing associations for route planning.

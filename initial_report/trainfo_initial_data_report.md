# Initial TrainFo Data Report

## Scope

This initial report documents the event-level TrainFo data currently available in the workspace. The all-crossing source contains records for 67 crossing IDs; the catalog contains 68 crossing IDs. The eight-street subset contains Commerce Street, Hirsch Road, Leeland Street, Lockwood Street, Market Street, Polk Street, Telephone Road, and York Street.

The raw files are retained unchanged as source snapshots. The cleaned event files are analysis inputs, not yet the final minute-level machine-learning table.

## Data integration

Each event is keyed by the FRA crossing number and includes the crossing name, latitude, longitude, blockage date, blockage start time, and reported duration. The source URL is retained for traceability. The blank export column in the raw CSV is omitted from the cleaned analysis table.

## Coverage

| Dataset | Raw rows | Clean rows | Crossings with data | First date | Last date |
|---|---:|---:|---:|---|---|
| All crossings | 283,913 | 283,308 | 67 | 2022-09-07 | 2026-09-09 |
| Eight-street subset | 152,547 | 152,411 | 8 | 2022-09-07 | 2026-09-12 |

The catalog includes 1 crossing ID with no records in the current all-crossing file: 023207W.

## Cleaning rules

The cleaned event tables apply only two automatic rules:

1. Exact duplicate event rows are retained once.
2. Events with a missing, invalid, or nonpositive duration are excluded from the cleaned event table and counted in the audit.

Long durations are not automatically deleted because they may represent genuine extended occupancy. Sensor gaps are not imputed at this stage because an absent event does not prove that a crossing was clear.

| Dataset | Invalid duration rows | Exact duplicate rows removed |
|---|---:|---:|
| All crossings | 486 | 119 |
| Eight-street subset | 17 | 119 |

The cleaned files add `blockageEndDate` and `blockageEndTime`, calculated from the reported start timestamp and duration.

## Modeling readiness

The current cleaned tables are event-level tables. They are suitable for descriptive summaries, duration analysis, crossing comparisons, and quality checks. They are not yet the final prediction table because the proposal's targets require a synchronized time grid and a defined treatment for sensor gaps.

The next modeling-preparation step is to convert events into one-minute crossing states, define whether an event occupies each minute, flag intervals affected by missing sensor coverage, and create `target_5m`, `target_10m`, `target_15m`, and `target_30m` using only information available at prediction time.

## Initial variable dictionary

| Variable | Type | Description |
|---|---|---|
| `FRA Number` | categorical | Crossing identifier used to link records and metadata. |
| `Crossing Name` | categorical | Street or crossing name. |
| `Latitude`, `Longitude` | numeric | Crossing coordinates. |
| `blockageDate` | date | Date on which the blockage began. |
| `blockageStartTime` | time | Time at which the blockage began. |
| `duration (min)` | numeric | Reported blockage duration in minutes. |
| `blockageEndDate`, `blockageEndTime` | derived date/time | End timestamp calculated from start plus duration. |
| `Google Maps` | reference | Coordinate-based map link. |
| `Trainfo CSV` | reference | Original source URL for traceability. |

The empty raw export column is not used as a predictor. Final modeling variables such as current state, time in current state, recent blocked fraction, neighboring states, and future targets will be documented after the minute-level state construction and gap policy are finalized.

## Generated files

- `trainfo_all_events_clean.csv`
- `trainfo_8streets_events_clean.csv`
- `trainfo_data_quality_by_crossing.csv`
- `trainfo_initial_data_report.md`

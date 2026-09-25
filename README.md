# Houston TrainFo Crossing Data Pipeline

This repository downloads TrainFo crossing event data, preserves the raw source files, and produces reproducible merged outputs for all catalog crossings and the eight-street analysis subset.

## Project layout

```text
config/
  eight_streets.json       FRA IDs for the focused eight-street subset
initial_report/
  trainfo_initial_data_report.md
  README.md
src/trainfo_pipeline/
  config.py                Paths and pipeline configuration
  downloader.py            Authenticated raw CSV downloads
  transform.py             Event normalization and subset selection
  outputs.py               CSV and formatted Excel exports
download_trainfo.py        Command-line refresh entry point
prepare_initial_report.py  Data-quality audit and report artifact generation
crossings.xlsx             Catalog of crossing names and TrainFo URLs
```

Raw downloads and generated datasets are intentionally excluded from Git. They can be recreated locally by following the workflow below.

## Setup

Use Python 3.9 or newer and create a virtual environment:

```zsh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pandas requests openpyxl
```

Create a local credential file outside the repository:

```zsh
mkdir -p "$HOME/.config"
cp trainfo.env.example "$HOME/.config/trainfo.env"
chmod 600 "$HOME/.config/trainfo.env"
open -e "$HOME/.config/trainfo.env"
```

Set `TRAININFO_API_USER` and `TRAININFO_API_KEY` using credentials supplied by TrainFo. Never commit or paste those values into the repository.

## Refresh workflow

Run a complete refresh from the repository root:

```zsh
./run_trainfo_refresh.sh
```

The command downloads every crossing listed in `crossings.xlsx` and writes:

- Raw source CSVs to `data/raw/`
- All-crossing CSV/XLSX outputs to `data/processed/`
- Eight-street CSV/XLSX outputs to `data/processed/`

The Excel outputs include a title, last-updated date, frozen headers, and a formatted table. A failed crossing stops the run before outputs are reported as complete, and the terminal lists the failed crossing.

To merge an already-downloaded raw snapshot without contacting TrainFo:

```zsh
.venv/bin/python merge_raw_snapshot.py
```

The current September 20, 2026 merged files are:

- `data/processed/trainfo_all_merged_2026-09-20.csv` — 285,263 event rows from 67 crossings with available raw data.
- `data/processed/trainfo_8streets_merged_2026-09-20.csv` — 153,141 event rows from the original eight focus crossings.
- `data/processed/trainfo_all_updated_2026-09-20.csv` — the same all-crossing events in the simple five-column format: `FRA Number`, `location`, `blockageDate`, `blockageStartTime`, and `duration (min)`.

The catalog contains one additional crossing, Alameda/Genoa, whose TrainFo source was unavailable during this scrape. Hughes Street is not in the catalog, so it is not included in the focused file.

For a deterministic date label during a reproducibility check:

```zsh
.venv/bin/python download_trainfo.py --date 2026-09-20
```

## Initial report workflow

The existing raw/merged snapshot can be audited without contacting TrainFo:

```zsh
.venv/bin/python prepare_initial_report.py
```

This creates cleaned event tables and a crossing-level data-quality audit in `initial_report/`. The cleaning step removes exact duplicate event keys and invalid/nonpositive durations, but does not remove long durations or impute sensor gaps. See `initial_report/trainfo_initial_data_report.md` for the before/after counts and limitations.

The cleaned event tables are not yet the minute-level machine-learning matrix. That later workflow must define sensor-gap handling, a one-minute state grid, historical features, neighboring-crossing features, and 5/10/15/30-minute targets without future leakage.

## Crossing map visualization

Generate an ArcGIS-style local map from the fresh raw scrape:

```zsh
.venv/bin/python create_crossing_map.py
```

Open `visualizations/crossing_activity_map.html` in a browser. The map provides a selected-street focus selector, an all-crossings view, search by street/FRA ID, clickable markers, last blockage time, last duration, event counts, and average duration. It uses the crossing metadata coordinates and does not require an ArcGIS account or API token. The current selected set is the original eight streets because Hughes Street is not present in the catalog or scrape. The HTML is generated locally and ignored by Git; the Python script is the reproducible artifact.

## Crossing activity analysis

Generate quantitative summaries and an interactive dashboard:

```zsh
python analyze_crossing_activity.py
```

This produces crossing-level metrics, rankings by cumulative blocked hours and exposure-adjusted event rate, an event-rate/duration scatterplot, and a monthly event-count distribution with a descriptive Poisson baseline. The analysis reports the variance-to-mean dispersion ratio; a large ratio indicates that a simple Poisson model is inadequate and that negative binomial, quasi-Poisson, or crossing-specific exposure features should be considered. The generated files are local analysis artifacts and are ignored by Git.

Generate static figures for Section 4:

```zsh
python create_report_figures.py
```

The figures are written to `initial_report/figures/` and cover duration skew, crossing event burden, monthly coverage, and crossing locations.

Create an ArcGIS-ready point layer:

```zsh
python create_arcgis_geojson.py
```

The GeoJSON output is local and ignored by Git. Upload instructions are in `visualizations/ARCGIS_UPLOAD.md`.

## Reproducibility and Git policy

- `crossings.xlsx`, `Trainfo Crossing Info - Sheet1.csv`, code, configuration, and documentation may be versioned.
- Raw downloads, generated datasets, logs, virtual environments, and credentials are ignored by `.gitignore`.
- The raw source snapshot should be archived outside Git when a report result depends on it.
- Use branches for changes and keep the default branch runnable.

## Validation

Run the basic code checks:

```zsh
python -m py_compile download_trainfo.py prepare_initial_report.py src/trainfo_pipeline/*.py
zsh -n run_trainfo_refresh.sh
```

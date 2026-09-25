# Local data directories

The refresh pipeline creates two local directories here:

- `raw/`: untouched TrainFo CSV downloads, one file per catalog crossing.
- `processed/`: merged all-crossing and eight-street CSV/XLSX outputs.

Both directories are ignored by Git because they contain generated data. Keep a dated copy outside Git when a report result depends on a specific scrape.

The current consolidated EDA reads `processed/mergedtrain_with_coords8.csv` (focused eight crossings) and `processed/mergedtrainfo_with_coords_ALL.csv` (full network). Both use the nine-column coordinate-enriched pipeline schema. `processed/trainfo_all_updated_2026-09-20.csv` is the older five-column convenience export and is not the default analysis input.

See `../analysis/README.md` for input overrides and measurement definitions. Original contribution datasets remain under `../archive/contributions/` for provenance; the current analysis rebuilds from the merged source exports.

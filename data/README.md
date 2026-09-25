# Local data directories

The refresh pipeline creates two local directories here:

- `raw/`: untouched TrainFo CSV downloads, one file per catalog crossing.
- `processed/`: merged all-crossing and eight-street CSV/XLSX outputs.

Both directories are ignored by Git because they contain generated data. Keep a dated copy outside Git when a report result depends on a specific scrape.

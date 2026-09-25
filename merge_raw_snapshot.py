"""Merge one local raw TrainFo snapshot with crossing metadata."""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

OUTPUT_COLUMNS = [
    "FRA Number", "Crossing Name", "Latitude", "Longitude", "blockageDate",
    "blockageStartTime", "duration (min)", "Google Maps", "Trainfo CSV",
]


def parse_crossing(value):
    """Split a catalog label into crossing name and FRA ID."""
    parts = value.rsplit(" - ", 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (value.strip(), "")


def format_date(value):
    """Convert TrainFo's ISO date to the merged-table date format."""
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def read_csv(path):
    """Read a UTF-8/BOM CSV as dictionaries."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def merge_snapshot(project_root, raw_dir, output_dir):
    """Join raw events to metadata and write all/eight-street merged CSVs."""
    catalog = pd.read_excel(project_root / "crossings.xlsx")
    metadata_rows = read_csv(project_root / "Trainfo Crossing Info - Sheet1.csv")
    metadata_by_id = {row["FRA Number"].strip(): row for row in metadata_rows}
    with (project_root / "config/eight_streets.json").open(encoding="utf-8") as handle:
        selected_ids = set(json.load(handle)["fra_ids"])

    records = []
    for _, catalog_row in catalog.iterrows():
        name, fra_id = parse_crossing(str(catalog_row["Crossing"]))
        source = raw_dir / f"{name.replace('/', '_')}_{fra_id}.csv"
        if not source.exists():
            continue
        metadata = metadata_by_id.get(fra_id, {})
        for event in read_csv(source):
            records.append(
                {
                    "FRA Number": fra_id,
                    "Crossing Name": name,
                    "Latitude": metadata.get("Latitude", ""),
                    "Longitude": metadata.get("Longitude", ""),
                    "blockageDate": format_date(event["blockageDate"]),
                    "blockageStartTime": event["blockageStartTime"],
                    "duration (min)": event["duration"],
                    "Google Maps": f"https://www.google.com/maps?q={metadata.get('Latitude', '')},{metadata.get('Longitude', '')}",
                    "Trainfo CSV": str(catalog_row["CSV"]).strip(),
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    all_path = output_dir / "trainfo_all_merged_2026-09-20.csv"
    eight_path = output_dir / "trainfo_8streets_merged_2026-09-20.csv"
    frame.to_csv(all_path, index=False, encoding="utf-8-sig")
    frame[frame["FRA Number"].isin(selected_ids)].to_csv(eight_path, index=False, encoding="utf-8-sig")
    print(f"All crossings: {len(frame):,} rows -> {all_path}")
    print(f"Eight streets: {len(frame[frame['FRA Number'].isin(selected_ids)]):,} rows -> {eight_path}")
    print(f"Crossings represented: {frame['FRA Number'].nunique()}")


def main():
    """Merge the dated local raw snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    merge_snapshot(
        args.project_root,
        args.raw_dir or args.project_root / "raw_scrapes/fresh_2026-09-20",
        args.output_dir or args.project_root / "data/processed",
    )


if __name__ == "__main__":
    main()

"""Create a simple all-crossings TrainFo event table."""

import argparse
import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

OUTPUT_COLUMNS = [
    "FRA Number",
    "location",
    "blockageDate",
    "blockageStartTime",
    "duration (min)",
]


def parse_crossing(value):
    """Split a crossing catalog label into name and FRA ID."""
    parts = value.rsplit(" - ", 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (value.strip(), "")


def format_date(value):
    """Convert TrainFo's ISO date to the existing M/D/YYYY format."""
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def main():
    """Build the simple all-crossings CSV from a dated raw snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root
    raw_dir = args.raw_dir or root / "raw_scrapes/fresh_2026-09-20"
    output = args.output or root / "data/processed/trainfo_all_updated_2026-09-20.csv"
    catalog = pd.read_excel(root / "crossings.xlsx")
    records = []
    for _, row in catalog.iterrows():
        name, fra_id = parse_crossing(str(row["Crossing"]))
        source = raw_dir / f"{name.replace('/', '_')}_{fra_id}.csv"
        if not source.exists():
            continue
        with source.open(newline="", encoding="utf-8-sig") as handle:
            for event in csv.DictReader(handle):
                records.append(
                    {
                        "FRA Number": fra_id,
                        "location": event.get("location", name),
                        "blockageDate": format_date(event["blockageDate"]),
                        "blockageStartTime": event["blockageStartTime"],
                        "duration (min)": event["duration"],
                    }
                )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    print(f"Wrote {len(records):,} rows from {len(set(row['FRA Number'] for row in records))} crossings to {output}")


if __name__ == "__main__":
    main()

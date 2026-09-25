"""Create an ArcGIS-ready GeoJSON layer of TrainFo crossings."""

import argparse
import csv
import json
from pathlib import Path


def parse_crossing(value):
    """Split a catalog label into crossing name and FRA ID."""
    parts = value.rsplit(" - ", 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (value.strip(), "")


def read_csv(path):
    """Read a UTF-8/BOM CSV into dictionaries."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main():
    """Write crossing points and useful ArcGIS popup attributes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root
    output = args.output or root / "visualizations/crossings_for_arcgis.geojson"
    selected_ids = set(json.loads((root / "config/eight_streets.json").read_text(encoding="utf-8"))["fra_ids"])
    metrics_path = root / "visualizations/crossing_activity_metrics.csv"
    metrics = {row["FRA Number"]: row for row in read_csv(metrics_path)} if metrics_path.exists() else {}
    features = []
    for row in read_csv(root / "Trainfo Crossing Info - Sheet1.csv"):
        name, fra_id = parse_crossing(str(row.get("Crossing", "")))
        if not fra_id:
            fra_id = row.get("FRA Number", "").strip()
        metric = metrics.get(fra_id, {})
        if metrics and not metric.get("raw_available", "").lower() == "true":
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(row["Longitude"]), float(row["Latitude"])]},
                "properties": {
                    "crossing_name": name,
                    "fra_number": fra_id,
                    "selected_eight": fra_id in selected_ids,
                    "selected_group": "Selected eight crossings" if fra_id in selected_ids else "Other available crossings",
                    "event_count": int(metric.get("valid_events", 0) or 0),
                    "blocked_hours": float(metric.get("total_blocked_hours", 0) or 0),
                    "average_duration_min": float(metric.get("average_duration_minutes", 0) or 0),
                    "events_per_30_days": float(metric.get("events_per_30_days", 0) or 0),
                    "latitude": float(row["Latitude"]),
                    "longitude": float(row["Longitude"]),
                },
            }
        )
    geojson = {"type": "FeatureCollection", "name": "TrainFo Houston Crossings", "features": features}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(geojson, indent=2), encoding="utf-8")
    print(f"Wrote {len(features)} crossing features to {output}")


if __name__ == "__main__":
    main()

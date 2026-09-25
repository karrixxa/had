"""Create static figures for Section 4 from the fresh TrainFo raw snapshot."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SELECTED_COLOR = "#2563eb"
OTHER_COLOR = "#94a3b8"
DARK = "#1e293b"


def parse_crossing(value):
    """Split a catalog label into crossing name and FRA ID."""
    parts = value.rsplit(" - ", 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (value.strip(), "")


def read_raw_events(raw_dir):
    """Read valid positive-duration events from all raw files."""
    events = []
    for path in sorted(raw_dir.glob("*.csv")):
        if path.name.startswith("README"):
            continue
        name, fra_id = path.stem.rsplit("_", 1)
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                try:
                    duration = float(row["duration"])
                    if duration <= 0:
                        continue
                    event_date = datetime.strptime(row["blockageDate"], "%Y-%m-%d").date()
                except (KeyError, TypeError, ValueError):
                    continue
                events.append({"name": name.replace("_", " "), "fra_id": fra_id, "date": event_date, "duration": duration})
    return pd.DataFrame(events)


def load_metadata(path):
    """Load crossing coordinates from the crossing-information file."""
    rows = pd.read_csv(path, encoding="utf-8-sig")
    records = []
    for row in rows.to_dict("records"):
        name, fra_id = parse_crossing(str(row.get("Crossing", "")))
        if not fra_id:
            fra_id = str(row.get("FRA Number", "")).strip()
        records.append({"name": name, "fra_id": fra_id, "latitude": float(row["Latitude"]), "longitude": float(row["Longitude"])})
    return pd.DataFrame(records)


def save(fig, output_dir, name):
    """Save a publication-friendly PNG."""
    fig.savefig(output_dir / name, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def duration_figure(events, output_dir):
    """Plot linear and log-scale views of the blockage-duration distribution."""
    durations = events["duration"].to_numpy()
    fig, (ax, tail_ax) = plt.subplots(1, 2, figsize=(11, 5.2), gridspec_kw={"width_ratios": [1.35, 1]})
    short_durations = durations[durations <= 60]
    ax.hist(short_durations, bins=40, color=SELECTED_COLOR, alpha=0.85, edgecolor="white", linewidth=0.4)
    ax.set_xlim(0, 60)
    ax.set_xlabel("Duration (minutes)")
    ax.set_ylabel("Number of valid events")
    ax.set_title("Blockage Duration Distribution")
    ax.grid(axis="y", alpha=0.2)
    bins = np.logspace(np.log10(0.05), np.log10(durations.max()), 55)
    tail_ax.hist(durations, bins=bins, color="#64748b", alpha=0.85, edgecolor="white", linewidth=0.4)
    tail_ax.set_xscale("log")
    tail_ax.set_xlabel("Duration (minutes, log scale)")
    tail_ax.set_title("Blockage Duration Distribution (Log Scale)")
    tail_ax.grid(axis="y", alpha=0.2)
    median = np.percentile(durations, 50)
    p90 = np.percentile(durations, 90)
    ax.axvline(median, color="#f59e0b", linestyle="--", label=f"Median: {median:.2f} min")
    ax.axvline(p90, color="#dc2626", linestyle=":", label=f"90th percentile: {p90:.2f} min")
    tail_ax.axvline(median, color="#f59e0b", linestyle="--", label=f"Median: {median:.2f} min")
    tail_ax.axvline(p90, color="#dc2626", linestyle=":", label=f"90th percentile: {p90:.2f} min")
    tail_ax.text(
        0.98,
        0.96,
        f"Orange dashed = median ({median:.2f} min)\nRed dotted = 90th percentile ({p90:.2f} min)",
        transform=tail_ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        color=DARK,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8, "pad": 3},
    )
    fig.suptitle("TrainFo Blockage Duration Analysis", y=1.02)
    fig.tight_layout()
    save(fig, output_dir, "figure_4_1_duration_distribution.png")


def burden_figure(events, output_dir, selected_ids):
    """Plot event counts by crossing and highlight the focused subset."""
    summary = events.groupby(["fra_id", "name"], as_index=False).agg(events=("duration", "size"), blocked_hours=("duration", lambda values: values.sum() / 60))
    summary = summary.sort_values("events", ascending=False).head(20).sort_values("events")
    colors = [SELECTED_COLOR if fra in selected_ids else OTHER_COLOR for fra in summary["fra_id"]]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.barh(summary["name"], summary["events"], color=colors)
    ax.set_xlabel("Valid blockage events")
    ax.set_ylabel("")
    ax.set_title("Crossings with the most recorded blockage events")
    ax.grid(axis="x", alpha=0.2)
    max_events = summary["events"].max()
    ax.set_xlim(0, max_events * 1.05)
    for index, (_, row) in enumerate(summary.iterrows()):
        ax.text(1.01, index, f"{int(row['events']):,}", transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=8, clip_on=False)
    ax.text(1.01, 1.01, "Events", transform=ax.transAxes, ha="left", va="bottom", fontsize=9, color=DARK)
    ax.text(0.99, 0.02, "Blue = selected eight-street focus", transform=ax.transAxes, ha="right", color=DARK, fontsize=9)
    fig.subplots_adjust(right=0.84)
    save(fig, output_dir, "figure_4_2_crossing_event_burden.png")


def monthly_figure(events, output_dir):
    """Plot monthly valid event volume for all crossings and the focus subset."""
    selected = {"288129A", "755640L", "288224V", "859523F", "755709E", "288039B", "288051H", "859517C"}
    events = events.copy()
    events["month"] = events["date"].map(lambda value: value.strftime("%Y-%m"))
    all_monthly = events.groupby("month").size()
    selected_monthly = events[events["fra_id"].isin(selected)].groupby("month").size()
    months = pd.date_range(events["date"].min().replace(day=1), events["date"].max().replace(day=1), freq="MS").strftime("%Y-%m")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(months, [all_monthly.get(month, 0) for month in months], color=OTHER_COLOR, linewidth=2, label="All available crossings")
    ax.plot(months, [selected_monthly.get(month, 0) for month in months], color=SELECTED_COLOR, linewidth=2, label="Selected eight crossings")
    ax.set_xlabel("Month")
    ax.set_ylabel("Valid blockage events")
    ax.set_title("Blockage-event volume over the observation period")
    tick_positions = np.arange(0, len(months), 6)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([months[index] for index in tick_positions], rotation=45, ha="right")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    save(fig, output_dir, "figure_4_3_monthly_event_coverage.png")


def map_figure(events, metadata, output_dir, selected_ids):
    """Plot the crossing locations and distinguish the selected subset."""
    counts = events.groupby("fra_id").size().rename("events")
    locations = metadata.join(counts, on="fra_id").fillna({"events": 0})
    fig, ax = plt.subplots(figsize=(8.5, 7))
    other = locations[~locations["fra_id"].isin(selected_ids)]
    selected = locations[locations["fra_id"].isin(selected_ids)]
    ax.scatter(other["longitude"], other["latitude"], s=np.maximum(25, other["events"] / 250), color=OTHER_COLOR, alpha=0.75, edgecolor="white", linewidth=0.6, label="Other catalog crossings")
    ax.scatter(selected["longitude"], selected["latitude"], s=np.maximum(55, selected["events"] / 180), color=SELECTED_COLOR, alpha=0.9, edgecolor="white", linewidth=0.9, label="Selected eight crossings")
    label_offsets = {
        "Commerce Street": (-72, 8), "Hirsch Road": (8, 12),
        "Leeland Street": (8, -14), "Lockwood Street": (8, 8),
        "Market Street": (8, 18), "Polk Street": (8, -22),
        "Telephone Road": (8, -12), "York Street": (8, 2),
    }
    for _, row in selected.iterrows():
        ax.annotate(row["name"], (row["longitude"], row["latitude"]), xytext=label_offsets.get(row["name"], (5, 5)), textcoords="offset points", fontsize=8, color=DARK)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Spatial distribution of TrainFo crossing locations")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False, loc="best")
    ax.text(0.01, 0.01, "Marker size represents valid event count; map is schematic, not a street basemap.", transform=ax.transAxes, fontsize=8, color="#64748b")
    save(fig, output_dir, "figure_4_4_crossing_location_distribution.png")


def main():
    """Create all Section 4 figures from the current raw snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    root = args.project_root
    output_dir = root / "initial_report" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    events = read_raw_events(root / "raw_scrapes/fresh_2026-09-20")
    metadata = load_metadata(root / "Trainfo Crossing Info - Sheet1.csv")
    with (root / "config/eight_streets.json").open(encoding="utf-8") as handle:
        selected_ids = set(json.load(handle)["fra_ids"])
    duration_figure(events, output_dir)
    burden_figure(events, output_dir, selected_ids)
    monthly_figure(events, output_dir)
    map_figure(events, metadata, output_dir, selected_ids)
    print(f"Wrote four figures to {output_dir}")


if __name__ == "__main__":
    main()

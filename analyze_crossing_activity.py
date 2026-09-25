"""Quantify crossing activity and build a report-ready Plotly dashboard."""

import argparse
import csv
import json
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def parse_args():
    """Parse local raw-data and output paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def read_csv(path):
    """Read a UTF-8/BOM CSV into dictionaries."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def parse_crossing(value):
    """Split a catalog label into display name and FRA ID."""
    parts = value.rsplit(" - ", 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (value.strip(), "")


def month_range(first, last):
    """Return every YYYY-MM month between two dates, inclusive."""
    current = first.replace(day=1)
    final = last.replace(day=1)
    months = []
    while current <= final:
        months.append(current.strftime("%Y-%m"))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return months


def poisson_pmf(value, rate):
    """Compute a Poisson probability without requiring SciPy."""
    if rate <= 0:
        return 1.0 if value == 0 else 0.0
    log_probability = -rate + value * math.log(rate) - math.lgamma(value + 1)
    return math.exp(log_probability)


def build_metrics(metadata_path, raw_dir, selected_ids):
    """Build crossing metrics and equal-exposure monthly event counts."""
    metrics = []
    monthly_counts = []
    for crossing in read_csv(metadata_path):
        name, fra_id = parse_crossing(crossing.get("Crossing", ""))
        if not fra_id:
            fra_id = crossing.get("FRA Number", "").strip()
        raw_path = raw_dir / f"{name.replace('/', '_')}_{fra_id}.csv"
        rows = read_csv(raw_path) if raw_path.exists() else []
        valid = []
        invalid_count = 0
        for row in rows:
            try:
                duration = float(row["duration"])
                started = datetime.strptime(row["blockageDate"], "%Y-%m-%d").date()
                if duration <= 0:
                    raise ValueError
                valid.append((started, duration))
            except (KeyError, TypeError, ValueError):
                invalid_count += 1
        valid.sort(key=lambda item: item[0])
        if valid:
            first_date = valid[0][0]
            last_date = valid[-1][0]
            observed_days = (last_date - first_date).days + 1
            months = month_range(first_date, last_date)
            month_counter = Counter(item[0].strftime("%Y-%m") for item in valid)
            monthly_counts.extend(month_counter.get(month, 0) for month in months)
        else:
            first_date = last_date = None
            observed_days = 0
        total_minutes = sum(item[1] for item in valid)
        metrics.append(
            {
                "FRA Number": fra_id,
                "Crossing Name": name,
                "Latitude": float(crossing["Latitude"]),
                "Longitude": float(crossing["Longitude"]),
                "selected": fra_id in selected_ids,
                "raw_events": len(rows),
                "valid_events": len(valid),
                "invalid_events": invalid_count,
                "total_blocked_minutes": round(total_minutes, 2),
                "total_blocked_hours": round(total_minutes / 60, 2),
                "average_duration_minutes": round(total_minutes / len(valid), 2) if valid else 0,
                "median_duration_minutes": round(sorted(item[1] for item in valid)[len(valid) // 2], 2) if valid else 0,
                "observed_days": observed_days,
                "events_per_observed_day": round(len(valid) / observed_days, 4) if observed_days else 0,
                "events_per_30_days": round(len(valid) * 30 / observed_days, 2) if observed_days else 0,
                "first_event_date": str(first_date) if first_date else "",
                "last_event_date": str(last_date) if last_date else "",
                "raw_available": raw_path.exists(),
            }
        )
    return metrics, monthly_counts


def write_metrics(path, metrics):
    """Write the crossing-level metrics CSV."""
    fields = list(metrics[0].keys()) if metrics else []
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(metrics)


def build_dashboard(metrics, monthly_counts, output_path):
    """Create a four-panel interactive Plotly analysis dashboard."""
    available = [item for item in metrics if item["raw_available"]]
    selected = [item for item in available if item["selected"]]
    ranked = sorted(available, key=lambda item: item["total_blocked_hours"], reverse=True)[:15]
    lambda_month = sum(monthly_counts) / len(monthly_counts) if monthly_counts else 0
    max_count = max(monthly_counts, default=0)
    count_values = list(range(max_count + 1))
    expected = [len(monthly_counts) * poisson_pmf(value, lambda_month) for value in count_values]
    variance = sum((value - lambda_month) ** 2 for value in monthly_counts) / len(monthly_counts) if monthly_counts else 0
    dispersion = variance / lambda_month if lambda_month else 0

    figure = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Top crossings by total blocked hours",
            "Exposure-adjusted event rate vs. average duration",
            "Monthly event counts vs. Poisson baseline",
            "Focused eight-street ranking",
        ),
        specs=[[{}, {}], [{}, {"type": "table"}]],
        vertical_spacing=0.14,
        horizontal_spacing=0.1,
    )
    figure.add_trace(
        go.Bar(
            x=[item["Crossing Name"] for item in ranked][::-1],
            y=[item["total_blocked_hours"] for item in ranked][::-1],
            marker_color=["#2563eb" if item["selected"] else "#94a3b8" for item in ranked][::-1],
            customdata=[[item["valid_events"], item["events_per_30_days"]] for item in ranked][::-1],
            hovertemplate="%{x}<br>Total blocked: %{y:.1f} hours<br>Events: %{customdata[0]:,}<br>Rate: %{customdata[1]:.2f}/30 days<extra></extra>",
        ),
        row=1,
        col=1,
    )
    for items, color, label in ((available, "#94a3b8", "All crossings"), (selected, "#2563eb", "Selected eight")):
        figure.add_trace(
            go.Scatter(
                x=[item["events_per_30_days"] for item in items],
                y=[item["average_duration_minutes"] for item in items],
                mode="markers",
                name=label,
                marker={"color": color, "size": [max(7, min(28, item["total_blocked_hours"] / 100)) for item in items], "line": {"color": "white", "width": 1}},
                text=[item["Crossing Name"] for item in items],
                customdata=[[item["valid_events"], item["total_blocked_hours"]] for item in items],
                hovertemplate="%{text}<br>Rate: %{x:.2f} events/30 days<br>Average duration: %{y:.2f} min<br>Events: %{customdata[0]:,}<br>Total blocked: %{customdata[1]:.1f} hours<extra></extra>",
            ),
            row=1,
            col=2,
        )
    figure.add_trace(
        go.Histogram(x=monthly_counts, name="Observed crossing-month counts", marker_color="#64748b", opacity=0.8),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=count_values, y=expected, name=f"Poisson baseline (lambda={lambda_month:.2f})", mode="lines+markers", line={"color": "#2563eb", "width": 3}),
        row=2,
        col=1,
    )
    focused = sorted(selected, key=lambda item: item["total_blocked_hours"], reverse=True)
    figure.add_trace(
        go.Table(
            header={"values": ["Crossing", "Events", "Blocked hours", "Rate / 30d"], "fill_color": "#1e293b", "font": {"color": "white"}},
            cells={"values": [[item["Crossing Name"] for item in focused], [item["valid_events"] for item in focused], [item["total_blocked_hours"] for item in focused], [item["events_per_30_days"] for item in focused]], "fill_color": "#f8fafc"},
        ),
        row=2,
        col=2,
    )
    figure.update_layout(
        title=f"Houston Crossing Activity | {len(available)} crossings with raw data | Poisson dispersion: {dispersion:.1f}",
        height=900,
        template="plotly_white",
        legend={"orientation": "h", "y": 1.06},
        margin={"l": 60, "r": 30, "t": 110, "b": 80},
    )
    figure.update_xaxes(title_text="Crossing", row=1, col=1, tickangle=-45)
    figure.update_yaxes(title_text="Total blocked hours", row=1, col=1)
    figure.update_xaxes(title_text="Valid events per 30 observed days", row=1, col=2)
    figure.update_yaxes(title_text="Average duration (minutes)", row=1, col=2)
    figure.update_xaxes(title_text="Valid events per crossing-month", row=2, col=1)
    figure.update_yaxes(title_text="Number of crossing-months", row=2, col=1)
    figure.write_html(output_path, include_plotlyjs="cdn")
    return lambda_month, dispersion


def write_summary(path, metrics, lambda_month, dispersion):
    """Write the interpretation notes for the dashboard."""
    available = [item for item in metrics if item["raw_available"]]
    top_hours = sorted(available, key=lambda item: item["total_blocked_hours"], reverse=True)[:5]
    top_rate = sorted(available, key=lambda item: item["events_per_30_days"], reverse=True)[:5]
    lines = [
        "# Crossing Activity Analysis", "",
        "This analysis uses the fresh TrainFo raw scrape as a historical snapshot, not a live operational feed.", "",
        "## Measures", "",
        "- **Total blocked hours**: sum of valid event durations; this identifies cumulative burden.",
        "- **Events per 30 observed days**: valid events scaled to each crossing's observed date span; this improves comparison when coverage differs.",
        "- **Average duration**: typical blockage length among valid events.",
        "- **Problematic crossing candidates**: crossings that rank high on cumulative burden, exposure-adjusted rate, or duration should be investigated together rather than labeled by one metric alone.",
        "", "## Highest cumulative burden", "",
    ]
    lines.extend(f"- {item['Crossing Name']}: {item['total_blocked_hours']:.1f} blocked hours across {item['valid_events']:,} valid events." for item in top_hours)
    lines.extend(["", "## Highest exposure-adjusted event rate", ""])
    lines.extend(f"- {item['Crossing Name']}: {item['events_per_30_days']:.2f} events per 30 observed days; average duration {item['average_duration_minutes']:.2f} minutes." for item in top_rate)
    lines.extend([
        "", "## Poisson baseline", "",
        f"A descriptive Poisson baseline was fit to valid event counts in crossing-month bins. The estimated lambda is {lambda_month:.2f} events per crossing-month, while the variance-to-mean dispersion ratio is {dispersion:.2f}.",
        "",
        "A ratio near 1 would be consistent with a simple Poisson count model. The observed ratio is much larger than 1, indicating overdispersion. For modeling, consider negative binomial or quasi-Poisson approaches, or include crossing-specific exposure and metadata rather than treating all crossings as exchangeable.",
        "",
        "The interactive dashboard is generated in `visualizations/crossing_activity_analysis.html`; the metric table is `visualizations/crossing_activity_metrics.csv`.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    """Generate crossing metrics, dashboard, and interpretation summary."""
    args = parse_args()
    root = args.project_root
    raw_dir = args.raw_dir or root / "raw_scrapes/fresh_2026-09-20"
    output_dir = args.output_dir or root / "visualizations"
    with (root / "config/eight_streets.json").open(encoding="utf-8") as handle:
        selected_ids = set(json.load(handle)["fra_ids"])
    metrics, monthly_counts = build_metrics(root / "Trainfo Crossing Info - Sheet1.csv", raw_dir, selected_ids)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_metrics(output_dir / "crossing_activity_metrics.csv", metrics)
    lambda_month, dispersion = build_dashboard(metrics, monthly_counts, output_dir / "crossing_activity_analysis.html")
    write_summary(output_dir / "crossing_activity_analysis.md", metrics, lambda_month, dispersion)
    print(f"Analyzed {sum(item['raw_available'] for item in metrics)} crossings with raw data.")
    print(f"Poisson baseline lambda={lambda_month:.2f}; dispersion={dispersion:.2f}.")


if __name__ == "__main__":
    main()

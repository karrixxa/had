"""Build a local interactive crossing-activity map from raw TrainFo CSVs."""

import argparse
import csv
import json
from datetime import datetime
from html import escape
from pathlib import Path


def parse_args():
    """Parse source and output paths for the map workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def read_csv(path):
    """Read a UTF-8/BOM CSV into dictionaries."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def parse_crossing(value):
    """Split a catalog crossing label into display name and FRA ID."""
    parts = value.rsplit(" - ", 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (value.strip(), "")


def event_timestamp(row):
    """Parse either HH:MM or HH:MM:SS TrainFo timestamps."""
    date_value = datetime.strptime(row["blockageDate"], "%Y-%m-%d")
    time_value = row["blockageStartTime"]
    for time_format in ("%H:%M:%S", "%H:%M"):
        try:
            parsed_time = datetime.strptime(time_value, time_format).time()
            return datetime.combine(date_value.date(), parsed_time)
        except ValueError:
            continue
    return None


def collect_crossing_stats(metadata_path, raw_dir, selected_ids):
    """Combine crossing coordinates with event summaries for map markers."""
    metadata = read_csv(metadata_path)
    features = []
    for crossing in metadata:
        name, fra_id = parse_crossing(crossing.get("Crossing", ""))
        if not fra_id:
            fra_id = crossing.get("FRA Number", "").strip()
        filename = f"{name.replace('/', '_')}_{fra_id}.csv"
        raw_path = raw_dir / filename
        if not raw_path.exists():
            continue
        events = read_csv(raw_path) if raw_path.exists() else []
        valid_events = []
        invalid_events = 0
        for event in events:
            try:
                duration = float(event["duration"])
                timestamp = event_timestamp(event)
                if duration <= 0 or timestamp is None:
                    raise ValueError
                valid_events.append((timestamp, duration))
            except (KeyError, TypeError, ValueError):
                invalid_events += 1
        valid_events.sort(key=lambda item: item[0])
        last_event = valid_events[-1] if valid_events else None
        latitude = float(crossing["Latitude"])
        longitude = float(crossing["Longitude"])
        features.append(
            {
                "fra_id": fra_id,
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "selected": fra_id in selected_ids,
                "source_available": raw_path.exists(),
                "event_count": len(events),
                "valid_event_count": len(valid_events),
                "invalid_event_count": invalid_events,
                "average_duration": round(sum(item[1] for item in valid_events) / len(valid_events), 2) if valid_events else None,
                "last_blockage": last_event[0].strftime("%Y-%m-%d %H:%M:%S") if last_event else None,
                "last_duration": round(last_event[1], 2) if last_event else None,
                "source_file": filename,
            }
        )
    return features


def build_html(features, output_path):
    """Write the self-contained crossing-activity map HTML file."""
    payload = json.dumps(features, ensure_ascii=True)
    title = escape("Houston Crossing Activity")
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root {{ --green:#087f23; --ink:#1f2933; --muted:#64748b; --line:#d8dee7; --panel:#f8fafc; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--ink); font-family:Arial, sans-serif; background:#e5e7eb; }}
.app {{ display:grid; grid-template-columns:330px 1fr; height:100vh; min-height:620px; }}
.sidebar {{ display:flex; flex-direction:column; min-width:0; background:var(--panel); border-right:1px solid var(--line); }}
.header {{ padding:20px 18px 14px; border-bottom:1px solid var(--line); background:white; }}
h1 {{ margin:0 0 5px; font-size:22px; letter-spacing:.2px; }}
.subtitle {{ color:var(--muted); font-size:12px; line-height:1.4; }}
.controls {{ display:grid; gap:8px; padding:14px 18px; border-bottom:1px solid var(--line); background:#fff; }}
label {{ color:var(--muted); font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.6px; }}
select, input {{ width:100%; padding:9px 10px; border:1px solid #cbd5e1; border-radius:5px; background:white; color:var(--ink); }}
.stats {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:12px 18px; }}
.stat {{ padding:9px; border:1px solid var(--line); border-radius:5px; background:#fff; }}
.stat strong {{ display:block; font-size:18px; color:var(--green); }}
.stat span {{ color:var(--muted); font-size:10px; text-transform:uppercase; }}
.list {{ overflow:auto; padding:0 10px 16px; }}
.item {{ padding:12px 9px; border-top:1px solid var(--line); cursor:pointer; }}
.item:hover, .item.active {{ background:#eaf5ec; }}
.item h2 {{ margin:0 0 7px; color:var(--green); font-size:15px; }}
.item p {{ margin:3px 0; font-size:12px; }}
.item .muted {{ color:var(--muted); }}
#map {{ height:100%; min-height:620px; }}
.leaflet-tile-pane {{ filter: grayscale(0.65) saturate(0.65) brightness(1.08) contrast(0.92); }}
.marker {{ display:flex; align-items:center; justify-content:center; width:24px; height:24px; border:2px solid white; border-radius:50%; box-shadow:0 1px 4px #94a3b8; color:transparent; }}
.marker.selected {{ width:28px; height:28px; border:3px solid #991b1b; }}
.popup h3 {{ margin:0 0 7px; color:var(--green); }}
.popup p {{ margin:4px 0; }}
.notice {{ margin:0 18px 12px; padding:8px 10px; border-left:3px solid #d97706; color:#92400e; background:#fff7ed; font-size:11px; }}
@media (max-width:800px) {{ .app {{ grid-template-columns:1fr; grid-template-rows:390px 1fr; }} .sidebar {{ order:2; }} #map {{ order:1; min-height:360px; }} }}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
  <div class="header"><h1>Crossing Activity</h1><div class="subtitle">TrainFo event snapshot with selected crossings highlighted.</div></div>
  <div class="controls">
    <label for="scope">Show crossings</label>
    <select id="scope"><option value="selected">Selected-street focus</option><option value="all">All catalog crossings</option><option value="available">All with raw data</option></select>
    <label for="search">Find a crossing</label>
    <input id="search" type="search" placeholder="Street name or FRA ID">
  </div>
  <div class="stats"><div class="stat"><strong id="visibleCount">0</strong><span>visible crossings</span></div><div class="stat"><strong id="totalEvents">0</strong><span>event records</span></div></div>
    <div class="subtitle" style="padding:0 18px 10px">Red = selected streets &nbsp; Blue = other available crossings</div>
  <div id="list" class="list"></div>
</aside>
<main id="map"></main>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const crossings = {payload};
const map = L.map('map').setView([29.75, -95.35], 11);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom:19, attribution:'&copy; OpenStreetMap contributors' }}).addTo(map);
const markerLayer = L.layerGroup().addTo(map);
const markerById = new Map();
const list = document.getElementById('list');
const scope = document.getElementById('scope');
const search = document.getElementById('search');
const money = value => value === null ? 'Unavailable' : `${{value}} min`;
const lastText = value => value ? value.replace('T',' ') : 'Unavailable';
function markerColor(item) {{
    return item.selected ? '#dc2626' : '#2563eb';
}}
function popup(item) {{
  return `<div class="popup"><h3>${{item.name}}</h3><p><b>FRA:</b> ${{item.fra_id}}</p><p><b>Last blockage:</b> ${{lastText(item.last_blockage)}}</p><p><b>Last duration:</b> ${{money(item.last_duration)}}</p><p><b>Average duration:</b> ${{money(item.average_duration)}}</p><p><b>Events:</b> ${{item.event_count.toLocaleString()}}</p><p><b>Valid events:</b> ${{item.valid_event_count.toLocaleString()}}</p></div>`;
}}
function visibleItems() {{
  const query = search.value.trim().toLowerCase();
  return crossings.filter(item => {{
    const scopeMatch = scope.value === 'all' || (scope.value === 'available' && item.source_available) || (scope.value === 'selected' && item.selected);
    const searchMatch = !query || `${{item.name}} ${{item.fra_id}}`.toLowerCase().includes(query);
    return scopeMatch && searchMatch;
  }});
}}
function render() {{
  markerLayer.clearLayers(); markerById.clear(); list.innerHTML = '';
  const items = visibleItems();
  let totalEvents = 0;
  items.forEach(item => {{
    totalEvents += item.event_count;
    const size = item.selected ? 28 : 24;
    const icon = L.divIcon({{ className:'', html:`<div class="marker ${{item.selected ? 'selected' : ''}}" style="background:${{markerColor(item)}}"></div>`, iconSize:[size,size], iconAnchor:[size / 2,size / 2] }});
    const marker = L.marker([item.latitude, item.longitude], {{icon}}).bindPopup(popup(item)).addTo(markerLayer);
    markerById.set(item.fra_id, marker);
    const row = document.createElement('article'); row.className='item'; row.dataset.id=item.fra_id;
    row.innerHTML = `<h2>${{item.name}}</h2><p><b>Last blockage:</b> ${{lastText(item.last_blockage)}}</p><p><b>Duration:</b> ${{money(item.last_duration)}}</p><p class="muted">${{item.event_count.toLocaleString()}} event records</p>`;
    row.onclick = () => {{ map.setView([item.latitude,item.longitude], 14); marker.openPopup(); document.querySelectorAll('.item').forEach(el => el.classList.remove('active')); row.classList.add('active'); }};
    list.appendChild(row);
  }});
  document.getElementById('visibleCount').textContent = items.length;
  document.getElementById('totalEvents').textContent = totalEvents.toLocaleString();
}}
scope.onchange = render; search.oninput = render; render();
</script>
</body>
</html>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def main():
    """Generate the map HTML from local raw data."""
    args = parse_args()
    root = args.project_root
    raw_dir = args.raw_dir or root / "raw_scrapes/fresh_2026-09-20"
    output = args.output or root / "visualizations/crossing_activity_map.html"
    with (root / "config/eight_streets.json").open(encoding="utf-8") as handle:
        selected_ids = set(json.load(handle)["fra_ids"])
    features = collect_crossing_stats(root / "Trainfo Crossing Info - Sheet1.csv", raw_dir, selected_ids)
    build_html(features, output)
    available = sum(item["source_available"] for item in features)
    print(f"Wrote {output} with {len(features)} catalog crossings ({available} with raw data).")


if __name__ == "__main__":
    main()


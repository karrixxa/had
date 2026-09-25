"""Create a GeoJSON layer ranking COH fire stations near severe crossings."""

import argparse
import json
import math
from pathlib import Path

import requests


STATION_QUERY_URL = (
    "https://mycity2.houstontx.gov/gisweb01/rest/services/"
    "HoustonMap/Public_safety/MapServer/10/query"
)


def distance_miles(latitude_one, longitude_one, latitude_two, longitude_two):
    """Return the great-circle distance between two WGS 84 points."""
    earth_radius_miles = 3958.8
    lat_one = math.radians(latitude_one)
    lat_two = math.radians(latitude_two)
    delta_lat = math.radians(latitude_two - latitude_one)
    delta_lon = math.radians(longitude_two - longitude_one)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_one) * math.cos(lat_two) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_miles * math.asin(math.sqrt(haversine))


def read_crossings(path):
    """Read crossing points and retain the most blockage-heavy crossings."""
    data = json.loads(path.read_text(encoding="utf-8"))
    crossings = []
    for feature in data["features"]:
        properties = feature["properties"]
        latitude = float(properties["latitude"])
        longitude = float(properties["longitude"])
        crossings.append(
            {
                "name": properties["crossing_name"],
                "fra_number": properties["fra_number"],
                "blocked_hours": float(properties.get("blocked_hours", 0) or 0),
                "average_duration_min": float(properties.get("average_duration_min", 0) or 0),
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    return sorted(crossings, key=lambda crossing: crossing["blocked_hours"], reverse=True)


def fetch_stations():
    """Fetch the current public COH fire-station layer."""
    response = requests.get(
        STATION_QUERY_URL,
        params={
            "where": "1=1",
            "outFields": "LABEL,TEXT_,ADDRESS,LAT,LONG,LADDERS",
            "returnGeometry": "false",
            "f": "json",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "features" not in payload:
        raise RuntimeError(f"COH station service returned an error: {payload}")
    return [feature["attributes"] for feature in payload["features"]]


def classify_risk(total_blocked_hours, nearby_crossing_count):
    """Assign a simple display category for the ArcGIS layer."""
    if nearby_crossing_count == 0:
        return "No nearby severe crossings"
    if total_blocked_hours >= 2000 or nearby_crossing_count >= 3:
        return "High"
    if total_blocked_hours >= 500:
        return "Medium"
    return "Low"


def build_features(stations, crossings, radius_miles):
    """Create station features with nearby crossing summary fields."""
    features = []
    for station in stations:
        latitude = float(station["LAT"])
        longitude = float(station["LONG"])
        nearby = [
            crossing
            for crossing in crossings
            if distance_miles(latitude, longitude, crossing["latitude"], crossing["longitude"])
            <= radius_miles
        ]
        total_blocked_hours = round(sum(item["blocked_hours"] for item in nearby), 2)
        maximum_delay = round(
            max((item["average_duration_min"] for item in nearby), default=0), 2
        )
        nearest_distance = min(
            (
                distance_miles(latitude, longitude, item["latitude"], item["longitude"])
                for item in nearby
            ),
            default=0,
        )
        risk = classify_risk(total_blocked_hours, len(nearby))
        properties = {
            "station_number": int(station["LABEL"]),
            "station_address": station["ADDRESS"],
            "nearby_crossing_count": len(nearby),
            "nearby_blocked_hours": total_blocked_hours,
            "max_average_delay_min": maximum_delay,
            "nearest_crossing_miles": round(nearest_distance, 2),
            "risk_category": risk,
            "risk_basis": f"Top {len(crossings)} crossings by blocked hours within {radius_miles:g} mile",
            "source_station_layer": "COH Fire Stations",
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                "properties": properties,
            }
        )
    return features


def main():
    """Write the station risk GeoJSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--top-crossings", type=int, default=10)
    parser.add_argument("--radius-miles", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root
    output = args.output or root / "visualizations/fire_station_crossing_risk.geojson"
    severe_crossings = read_crossings(root / "visualizations/crossings_for_arcgis.geojson")[
        : args.top_crossings
    ]
    features = build_features(fetch_stations(), severe_crossings, args.radius_miles)
    geojson = {
        "type": "FeatureCollection",
        "name": "COH Fire Station Crossing Risk",
        "features": features,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(geojson, indent=2), encoding="utf-8")
    print(
        f"Wrote {len(features)} stations using {len(severe_crossings)} severe crossings "
        f"and a {args.radius_miles:g}-mile radius to {output}"
    )


if __name__ == "__main__":
    main()
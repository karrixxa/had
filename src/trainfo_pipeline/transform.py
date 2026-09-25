"""Transform raw TrainFo events into stable merged records."""

from io import StringIO
from typing import Mapping

import pandas as pd

from .config import DEFAULT_OUTPUT_COLUMNS
from .downloader import parse_crossing


def load_metadata(metadata_path) -> dict[str, Mapping[str, object]]:
    """Load crossing metadata keyed by FRA crossing number."""
    metadata_frame = pd.read_csv(metadata_path, encoding="utf-8-sig")
    return {
        str(row["FRA Number"]).strip(): row
        for row in metadata_frame.to_dict("records")
    }


def format_date(value: object) -> str:
    """Format a TrainFo event date as ``M/D/YYYY``."""
    parsed = pd.to_datetime(value)
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def normalize_events(
    event_frames: list[pd.DataFrame],
    metadata: Mapping[str, Mapping[str, object]],
) -> pd.DataFrame:
    """Combine raw event frames with coordinates and source traceability."""
    records: list[dict[str, object]] = []
    for events in event_frames:
        if events.empty:
            continue
        crossing_name = str(events.iloc[0]["crossing_name"])
        fra_id = str(events.iloc[0]["crossing_id"])
        metadata_row = metadata.get(fra_id, {})
        latitude = metadata_row.get("Latitude", "")
        longitude = metadata_row.get("Longitude", "")
        source_url = str(metadata_row.get("CSV", ""))
        if not source_url:
            source_url = str(metadata_row.get("Trainfo CSV", ""))
        for event in events.to_dict("records"):
            records.append(
                {
                    "FRA Number": fra_id,
                    "Crossing Name": crossing_name,
                    "Latitude": latitude,
                    "Longitude": longitude,
                    "blockageDate": format_date(event["blockageDate"]),
                    "blockageStartTime": event["blockageStartTime"],
                    "duration (min)": event["duration"],
                    "Google Maps": f"https://www.google.com/maps?q={latitude},{longitude}",
                    "Trainfo CSV": source_url,
                }
            )
    return pd.DataFrame(records, columns=DEFAULT_OUTPUT_COLUMNS)


def normalize_metadata_urls(
    frame: pd.DataFrame,
    crossings: pd.DataFrame,
) -> pd.DataFrame:
    """Fill source URLs from the catalog after event normalization."""
    url_by_id = {}
    for _, row in crossings.iterrows():
        _, fra_id = parse_crossing(str(row["Crossing"]))
        url_by_id[fra_id] = str(row["CSV"]).strip()
    frame = frame.copy()
    frame["Trainfo CSV"] = frame["FRA Number"].map(url_by_id).fillna(frame["Trainfo CSV"])
    return frame


def select_eight_streets(frame: pd.DataFrame, selected_ids: set[str]) -> pd.DataFrame:
    """Return only records belonging to the configured eight FRA IDs."""
    return frame[frame["FRA Number"].isin(selected_ids)].copy()

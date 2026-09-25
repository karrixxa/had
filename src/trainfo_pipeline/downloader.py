"""Download raw TrainFo crossing CSV files."""

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from time import sleep
from typing import Optional

import pandas as pd
import requests


@dataclass(frozen=True)
class DownloadFailure:
    """Describe a crossing that could not be downloaded or parsed."""

    crossing_name: str
    fra_id: str
    reason: str


def parse_crossing(raw_name: str) -> tuple[str, str]:
    """Split a catalog value such as ``Airport Blvd - 023228P``."""
    parts = raw_name.rsplit(" - ", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return raw_name.strip(), ""


def create_session(api_user: str, api_key: str) -> requests.Session:
    """Create an HTTP session with TrainFo authentication headers."""
    session = requests.Session()
    session.headers.update(
        {
            "User": api_user,
            "Key": api_key,
            "X-API-User": api_user,
            "X-API-Key": api_key,
        }
    )
    return session


def download_text(
    session: requests.Session,
    url: str,
    api_user: str,
    api_key: str,
    timeout_seconds: int = 45,
) -> Optional[str]:
    """Download CSV text using the supported TrainFo authentication methods."""
    attempts = (
        lambda: session.get(url, timeout=timeout_seconds),
        lambda: session.get(
            url,
            params={"user": api_user, "key": api_key},
            timeout=timeout_seconds,
        ),
        lambda: requests.get(url, auth=(api_user, api_key), timeout=timeout_seconds),
        lambda: requests.get(
            url,
            headers={"Authorization": "Bearer " + api_key},
            timeout=timeout_seconds,
        ),
    )
    for request in attempts:
        try:
            response = request()
            if response.status_code == 200 and len(response.text.strip()) > 10:
                return response.text
        except requests.RequestException:
            continue
    return None


def download_crossings(
    crossings: pd.DataFrame,
    raw_output_dir: Path,
    session: requests.Session,
    api_user: str,
    api_key: str,
    delay_seconds: float = 0.3,
) -> tuple[list[pd.DataFrame], list[DownloadFailure]]:
    """Download all catalog crossings and preserve each raw CSV locally.

    Returns:
        A list of parsed event frames and a list of download/parse failures.
    """
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    failures: list[DownloadFailure] = []

    for index, row in crossings.iterrows():
        crossing_name, fra_id = parse_crossing(str(row["Crossing"]))
        url = str(row["CSV"]).strip()
        print(f"[{index + 1}/{len(crossings)}] {crossing_name} ({fra_id})...", flush=True)
        csv_text = download_text(session, url, api_user, api_key)
        if not csv_text:
            failures.append(DownloadFailure(crossing_name, fra_id, "download failed"))
            continue

        filename = f"{crossing_name.replace('/', '_')}_{fra_id}.csv"
        (raw_output_dir / filename).write_text(csv_text, encoding="utf-8")
        try:
            frame = pd.read_csv(StringIO(csv_text))
            frame.insert(0, "crossing_name", crossing_name)
            frame.insert(1, "crossing_id", fra_id)
            frames.append(frame)
            print(f"  {len(frame)} rows")
        except (pd.errors.ParserError, ValueError, KeyError) as error:
            failures.append(DownloadFailure(crossing_name, fra_id, f"parse error: {error}"))
        sleep(delay_seconds)

    return frames, failures

"""Command-line entry point for the TrainFo refresh pipeline."""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# Allow this script to run directly from a cloned repository without installation.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from trainfo_pipeline.config import PipelineConfig
from trainfo_pipeline.downloader import create_session, download_crossings
from trainfo_pipeline.outputs import write_dataset_outputs
from trainfo_pipeline.transform import (
    load_metadata,
    normalize_events,
    normalize_metadata_urls,
    select_eight_streets,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line options for one refresh run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).parent,
        help="Repository root containing crossings.xlsx and config/.",
    )
    parser.add_argument(
        "--date",
        type=lambda value: date.fromisoformat(value),
        default=date.today(),
        help="Output date stamp in YYYY-MM-DD format; defaults to today.",
    )
    return parser.parse_args()


def load_credentials() -> tuple[str, str]:
    """Read TrainFo credentials from environment variables without printing them."""
    api_user = os.environ.get("TRAININFO_API_USER")
    api_key = os.environ.get("TRAININFO_API_KEY")
    if not api_user or not api_key:
        raise RuntimeError(
            "Set TRAININFO_API_USER and TRAININFO_API_KEY before running."
        )
    return api_user, api_key


def load_selected_ids(path: Path) -> set[str]:
    """Load FRA IDs used to build the eight-street subset."""
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    return {str(value) for value in config["fra_ids"]}


def run_refresh(config: PipelineConfig, updated: date) -> None:
    """Download crossings and write all-crossing/eight-street outputs."""
    api_user, api_key = load_credentials()
    config.ensure_directories()
    crossings = pd.read_excel(config.catalog_path)
    metadata = load_metadata(config.metadata_path)
    session = create_session(api_user, api_key)
    frames, failures = download_crossings(
        crossings=crossings,
        raw_output_dir=config.raw_output_dir,
        session=session,
        api_user=api_user,
        api_key=api_key,
    )
    if failures:
        details = "\n".join(
            f"- {failure.crossing_name} ({failure.fra_id}): {failure.reason}"
            for failure in failures
        )
        raise RuntimeError(f"Refresh incomplete:\n{details}")
    if not frames:
        raise RuntimeError("No crossing data was downloaded.")

    merged = normalize_events(frames, metadata)
    merged = normalize_metadata_urls(merged, crossings)
    selected_ids = load_selected_ids(config.selected_ids_path)
    eight_streets = select_eight_streets(merged, selected_ids)
    write_dataset_outputs(merged, config.output_dir, "all", updated)
    write_dataset_outputs(eight_streets, config.output_dir, "8streets", updated)
    print(f"Wrote all crossings: {len(merged):,} rows")
    print(f"Wrote eight streets: {len(eight_streets):,} rows")


def main() -> int:
    """Run the refresh and return a shell-compatible status code."""
    args = parse_args()
    try:
        run_refresh(PipelineConfig.from_project_root(args.project_root), args.date)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

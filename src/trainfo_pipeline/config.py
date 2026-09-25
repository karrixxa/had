"""Configuration objects and project defaults for the TrainFo pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet


DEFAULT_OUTPUT_COLUMNS = (
    "FRA Number",
    "Crossing Name",
    "Latitude",
    "Longitude",
    "blockageDate",
    "blockageStartTime",
    "duration (min)",
    "Google Maps",
    "Trainfo CSV",
)


@dataclass(frozen=True)
class PipelineConfig:
    """Paths and output settings for one pipeline run.

    Args:
        project_root: Repository directory containing the catalog and metadata.
        catalog_path: Excel file with crossing names and TrainFo CSV URLs.
        metadata_path: CSV file with crossing coordinates and identifiers.
        raw_output_dir: Directory where untouched downloaded CSVs are saved.
        output_dir: Directory where merged CSV/XLSX outputs are saved.
        selected_ids_path: JSON file listing the eight-street FRA IDs.
    """

    project_root: Path
    catalog_path: Path
    metadata_path: Path
    raw_output_dir: Path
    output_dir: Path
    selected_ids_path: Path

    @classmethod
    def from_project_root(cls, project_root: Path) -> "PipelineConfig":
        """Build the standard repository configuration from its root path."""
        return cls(
            project_root=project_root,
            catalog_path=project_root / "crossings.xlsx",
            metadata_path=project_root / "Trainfo Crossing Info - Sheet1.csv",
            raw_output_dir=project_root / "data" / "raw",
            output_dir=project_root / "data" / "processed",
            selected_ids_path=project_root / "config" / "eight_streets.json",
        )

    @property
    def output_columns(self) -> tuple[str, ...]:
        """Return the stable column order used by merged outputs."""
        return DEFAULT_OUTPUT_COLUMNS

    def ensure_directories(self) -> None:
        """Create local output directories when they do not already exist."""
        self.raw_output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

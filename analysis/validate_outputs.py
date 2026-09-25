"""Cross-check generated outputs independently of the plotting/report code."""
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/eda"


def main():
    tables = OUT / "tables"
    summary = pd.read_csv(tables / "crossing_summary.csv").set_index("name")
    daily = pd.read_csv(tables / "daily_exposure.csv")
    grouped = daily.groupby("name")[["blocked_min", "eligible_min"]].sum().loc[summary.index]
    np.testing.assert_allclose(grouped.blocked_min/60, summary.union_blocked_hours, atol=1e-6)
    np.testing.assert_allclose(grouped.eligible_min/1440, summary.eligible_days, atol=1e-6)
    assert (daily.blocked_min <= daily.eligible_min + 1e-6).all()
    assert daily.eligible_min.between(-1e-6, 1440+1e-6).all()
    monthly = pd.read_csv(tables / "monthly_patterns.csv")
    totals = monthly.groupby("name")[["blocked_min", "eligible_min"]].sum().loc[summary.index]
    np.testing.assert_allclose(totals, grouped, atol=1e-6)
    concurrency = pd.read_csv(tables / "concurrency.csv")
    assert concurrency.blocked_crossings.tolist() == list(range(9))
    assert concurrency.ticks.sum() == concurrency.eligible_ticks.iloc[0]
    np.testing.assert_allclose(concurrency.pct.sum(), 100)
    sensitivity = pd.read_csv(tables / "assumption_sensitivity.csv")
    assert sensitivity.blocked_pct.between(0, 100).all()
    for _, group in sensitivity.groupby(["name", "silence_threshold_h"]):
        group = group.sort_values("merge_gap_min")
        assert (group.episodes.diff().dropna() <= 0).all()
        assert (group.added_clear_minutes.diff().dropna() >= -1e-6).all()
    scores = pd.read_csv(tables / "forecast_baselines.csv")
    assert scores.brier.between(0, 1).all()
    assert not scores.name.eq("Telephone Road").any()
    for _, group in scores.groupby(["name", "horizon_min", "split"]):
        assert group.samples.nunique() == 1
        assert group.train_samples.nunique() == 1
    manifest = json.loads((OUT / "manifest.json").read_text())
    assert manifest["focused_matches_full"]
    assert summary.valid_records.sum() == manifest["clean_rows"]
    assert summary.union_episodes.sum() == manifest["union_episodes"]
    pictures = re.findall(r"<img src='([^']+)'", (OUT / "report.html").read_text())
    assert len(pictures) == 6
    assert all((OUT / p).is_file() for p in pictures)
    print("PASS: daily/monthly/summary totals, exposure limits, concurrency, sensitivity, model counts, source reconciliation, and all 6 report images")


if __name__ == "__main__":
    main()

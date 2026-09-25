"""Split the merged TRAINFO export into a station table and an event table.

Outputs (data/processed/):
  stations.csv   one row per crossing (FRA id, name, coordinates, source URL)
  events.csv     one row per raw blockage after exact-duplicate removal, with flags
  episodes.csv   raw events merged when the gap to the previous event at the same
                 crossing is <= MERGE_GAP_MIN (sensor fragments of one train)
  outages.csv    per-crossing unobserved intervals: kind="gap" when no events for
                 > OUTAGE_H hours (feed downtime, not "no trains"); kind="fault" for
                 whole days with a burst of spurious sub-minute episodes

Assumption: timestamps are local Houston time (America/Chicago), kept tz-naive.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "8mergedtrain_w_coords.csv"
OUT = ROOT / "data" / "processed"

MERGE_GAP_MIN = 2.0   # join events separated by <= 2 min of clear crossing
OUTAGE_H = 24.0       # no event for > 24 h at a crossing -> treat as downtime
FAULT_RATIO = 3.0     # fault day: episodes > 3x the rolling 29-day median ...
FAULT_SHORT = 0.5     # ... and > 50% of them shorter than 1 min

SHORT = {"Commerce Street": "Commerce", "Hirsch Road": "Hirsch", "Leeland Street": "Leeland",
         "Lockwood Street": "Lockwood", "Market Street": "Market", "Polk Street": "Polk",
         "Telephone Road": "Telephone", "York Street": "York"}


def load_raw():
    df = pd.read_csv(RAW, encoding="utf-8-sig")
    df.columns = ["fra", "name", "lat", "lon", "date", "time", "dur_min", "gmaps", "url"]
    # Telephone Road carries seconds (HH:MM:SS); the others are HH:MM
    df["start"] = pd.to_datetime(df["date"] + " " + df["time"], format="mixed")
    df["ts_resolution"] = np.where(df["time"].str.len() > 5, "second", "minute")
    return df


def build_stations(df):
    st = (df.groupby(["fra", "name"], as_index=False)
            .agg(lat=("lat", "first"), lon=("lon", "first"), trainfo_url=("url", "first")))
    st["short"] = st["name"].map(SHORT)
    return st


def build_events(df):
    ev = df[["fra", "name", "start", "dur_min", "ts_resolution"]].copy()
    n0 = len(ev)
    ev = ev.drop_duplicates(["fra", "start", "dur_min"]).sort_values(["fra", "start"])
    print(f"exact duplicates removed: {n0 - len(ev)}")
    ev["flag_nonpos"] = ev["dur_min"] <= 0
    ev["dur_min"] = ev["dur_min"].clip(lower=0)
    ev["end"] = ev["start"] + pd.to_timedelta(ev["dur_min"], unit="min")
    prev_end = ev.groupby("fra")["end"].shift()
    ev["gap_prev_min"] = (ev["start"] - prev_end).dt.total_seconds() / 60
    ev["flag_same_start"] = ev.duplicated(["fra", "start"], keep=False)
    ev["flag_overlap_prev"] = ev["gap_prev_min"] < -1  # beyond minute-rounding slack
    return ev.reset_index(drop=True)


def build_episodes(ev):
    ev = ev.sort_values(["fra", "start"]).copy()
    # running max of end handles nested/overlapping raw events
    ev["run_end"] = ev.groupby("fra")["end"].cummax()
    gap = (ev["start"] - ev.groupby("fra")["run_end"].shift()).dt.total_seconds() / 60
    new = gap.isna() | (gap > MERGE_GAP_MIN)
    ev["episode"] = new.groupby(ev["fra"]).cumsum()
    ep = (ev.groupby(["fra", "name", "episode"], as_index=False)
            .agg(start=("start", "min"), end=("run_end", "max"), n_fragments=("start", "size")))
    ep["dur_min"] = (ep["end"] - ep["start"]).dt.total_seconds() / 60
    return ep.drop(columns="episode")


def build_outages(ev, ep, stations):
    rows = []
    for fra, g in ev.groupby("fra"):
        s = g["start"].sort_values()
        e = g["end"].sort_values()
        gaps = (s.values[1:] - np.maximum.accumulate(e.values[:-1])) / np.timedelta64(1, "h")
        for i in np.where(gaps > OUTAGE_H)[0]:
            rows.append((fra, e.values[:-1][: i + 1].max(), s.values[i + 1]))
    out = pd.DataFrame(rows, columns=["fra", "gap_start", "gap_end"])
    out["kind"] = "gap"
    out = pd.concat([out, fault_days(ep)], ignore_index=True)
    out["hours"] = (out["gap_end"] - out["gap_start"]).dt.total_seconds() / 3600
    return out.merge(stations[["fra", "name"]], on="fra").sort_values(["fra", "gap_start"])


def fault_days(ep):
    d = (ep.assign(day=ep["start"].dt.floor("D"))
           .groupby(["fra", "day"])["dur_min"]
           .agg(n="size", short=lambda s: (s < 1).mean()).reset_index())
    base = d.groupby("fra")["n"].transform(
        lambda s: s.rolling(29, center=True, min_periods=7).median())
    f = d[(d["n"] > FAULT_RATIO * base) & (d["short"] > FAULT_SHORT)]
    return pd.DataFrame({"fra": f["fra"], "gap_start": f["day"],
                         "gap_end": f["day"] + pd.Timedelta(days=1), "kind": "fault"})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_raw()
    st = build_stations(df)
    ev = build_events(df)
    ep = build_episodes(ev)
    og = build_outages(ev, ep, st)
    st.to_csv(OUT / "stations.csv", index=False)
    ev.to_csv(OUT / "events.csv", index=False)
    ep.to_csv(OUT / "episodes.csv", index=False)
    og.to_csv(OUT / "outages.csv", index=False)
    print(f"stations {len(st)} | events {len(ev)} | episodes {len(ep)} | outages {len(og)}")
    print(ev.groupby("name")[["flag_nonpos", "flag_same_start", "flag_overlap_prev"]].sum())
    print(ep.groupby("name").agg(n=("dur_min", "size"), frag=("n_fragments", "mean"),
                                 med=("dur_min", "median")).round(2))
    print(og.groupby(["name", "kind"])["hours"].agg(["count", "sum", "max"]).div([1, 24, 24]).round(1)
            .rename(columns={"sum": "days_total", "max": "days_max"}))


if __name__ == "__main__":
    main()

"""Offline EDA. Run: python -m analysis.run_eda --help.

Intervals are half-open [start, end). Overlapping records are unioned before
measuring time. Positive merge gaps are sensitivity scenarios, not the baseline.
No event log can independently establish sensor uptime.
"""
import argparse
import hashlib
import html
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RENAME = {"FRA Number": "fra", "Crossing Name": "name", "Latitude": "lat",
          "Longitude": "lon", "duration (min)": "duration_min"}
COLORS = ["#2364aa", "#d06b32", "#188977", "#8357a6", "#b69319", "#478fa8", "#b24d6b", "#657447"]


def read_events(path):
    raw = pd.read_csv(path, dtype={"FRA Number": str}).rename(columns=RENAME)
    required = {"fra", "name", "duration_min", "blockageDate", "blockageStartTime"}
    if not required.issubset(raw):
        raise ValueError(f"Missing source columns: {sorted(required - set(raw))}")
    raw["start"] = pd.to_datetime(raw.blockageDate.astype(str) + " " +
                                   raw.blockageStartTime.astype(str), format="mixed", errors="coerce")
    raw["duration_min"] = pd.to_numeric(raw.duration_min, errors="coerce")
    raw["invalid"] = (raw.start.isna() | ~np.isfinite(raw.duration_min) |
                      raw.duration_min.le(0) | raw.fra.isna() | raw.name.isna())
    raw["duplicate"] = raw.duplicated(["fra", "start", "duration_min"])
    clean = raw.loc[~raw.invalid & ~raw.duplicate].copy()
    clean["end"] = clean.start + pd.to_timedelta(clean.duration_min, unit="min")
    return raw, clean.sort_values(["fra", "start", "end"])


def union_intervals(frame, gap_min=0):
    """Union nested intervals correctly, optionally bridging short clear gaps."""
    rows = []
    for fra, group in frame.groupby("fra", sort=True):
        group = group.sort_values(["start", "end"])
        running_end = group.end.cummax()
        gaps = (group.start - running_end.shift()).dt.total_seconds() / 60
        labels = (gaps.isna() | gaps.gt(gap_min)).cumsum()
        result = group.groupby(labels).agg(start=("start", "min"), end=("end", "max"),
                                           fragments=("start", "size"))
        result["fra"] = fra
        result["name"] = group.name.iloc[0]
        rows.append(result)
    if not rows:
        return pd.DataFrame(columns=["fra", "name", "start", "end", "fragments", "duration_min"])
    result = pd.concat(rows, ignore_index=True)
    result["duration_min"] = (result.end - result.start).dt.total_seconds() / 60
    return result


def gaps_between(intervals, hours):
    ordered = intervals.sort_values("start")
    previous = ordered.end.shift()
    keep = (ordered.start - previous).dt.total_seconds().gt(hours * 3600)
    return pd.DataFrame({"start": previous[keep], "end": ordered.start[keep]})


def allocate_days(intervals, days):
    """Exact wall-clock minutes by day, including midnight-crossing intervals."""
    result = np.zeros(len(days), dtype=float)
    origin = days[0]
    for row in intervals.itertuples():
        a, b = row.start, row.end
        while a < b:
            stop = min(b, a.normalize() + pd.Timedelta(days=1))
            index = (a.normalize() - origin).days
            if 0 <= index < len(result):
                result[index] += (stop - a).total_seconds() / 60
            a = stop
    return result


def interval_mask(intervals, origin, length):
    """State at exact minute ticks. Does not round partial minutes to full bins."""
    mask = np.zeros(length, dtype=bool)
    for row in intervals.itertuples():
        a = max(0, int(np.ceil((row.start - origin).total_seconds() / 60)))
        b = min(length, int(np.ceil((row.end - origin).total_seconds() / 60)))
        mask[a:b] = True
    return mask


def horizon_valid(observed, horizon):
    """Require every minute through the forecast horizon to be eligible."""
    missing = np.r_[0, np.cumsum(~observed)]
    t = np.arange(len(observed) - horizon)
    return missing[t + horizon + 1] == missing[t]


def markdown_table(frame):
    def val(x):
        if pd.isna(x):
            return "—"
        return f"{x:.2f}" if isinstance(x, (float, np.floating)) else str(x)
    lines = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    lines.extend("| " + " | ".join(val(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/processed/mergedtrain_with_coords8.csv")
    parser.add_argument("--full-input", type=Path, default=ROOT / "data/processed/mergedtrainfo_with_coords_ALL.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/eda")
    args = parser.parse_args()
    out = args.output
    tables, figures = out / "tables", out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "figure.facecolor": "white", "savefig.dpi": 160})
    raw, clean = read_events(args.input)
    if clean.empty:
        raise ValueError("No valid events remain")
    selected = set(json.loads((ROOT / "config/eight_streets.json").read_text())["fra_ids"])
    if set(clean.fra) != selected:
        raise ValueError("Input must contain exactly the configured eight crossings")
    intervals = union_intervals(clean)
    daily_rows, summaries, sensitivity, tails, residual, fault_sensitivity = [], [], [], [], [], []
    names = clean.groupby("fra").name.first().sort_values()
    origin = intervals.start.min().floor("D")
    end = intervals.end.max().ceil("D")
    time = pd.date_range(origin, end, freq="min", inclusive="left")
    states, eligible = [], []
    for fra, name in names.items():
        events = clean[clean.fra == fra]
        ep = intervals[intervals.fra == fra]
        first, last = ep.start.min(), ep.end.max()
        span = pd.DataFrame({"start": [first], "end": [last]})
        days = pd.date_range(first.floor("D"), last.floor("D"), freq="D")
        gaps = gaps_between(ep, 24)
        blocked = allocate_days(ep, days)
        calendar = allocate_days(span, days)
        exposure = calendar - allocate_days(gaps, days)
        if np.any(blocked > exposure + 1e-6):
            raise AssertionError("Blocked minutes exceed eligible exposure")
        counts = ep.groupby(ep.start.dt.floor("D")).size().reindex(days, fill_value=0)
        daily = pd.DataFrame({"fra": fra, "name": name, "day": days, "blocked_min": blocked,
                              "eligible_min": exposure, "span_min": calendar, "episodes": counts.to_numpy()})
        daily_rows.append(daily)
        # Reproduce the contribution's retrospective burst heuristic on valid
        # two-minute-merged episodes, but measure its effect on exact daily time.
        diagnostic = union_intervals(events, 2)
        burst = diagnostic.assign(day=diagnostic.start.dt.floor("D")).groupby("day").duration_min.agg(
            n="size", short=lambda x: x.lt(1).mean())
        rolling = burst.n.rolling(29, center=True, min_periods=7).median()
        flagged = burst.index[(burst.n > 3*rolling) & (burst.short > .5)]
        keep = ~daily.day.isin(flagged)
        fault_sensitivity.append({"name": name, "suspect_days": len(flagged),
            "retained_blocked_pct": 100*blocked.sum()/exposure.sum(),
            "excluded_blocked_pct": 100*daily.loc[keep, "blocked_min"].sum()/daily.loc[keep, "eligible_min"].sum(),
            "excluded_eligible_days": daily.loc[~keep, "eligible_min"].sum()/1440})
        d = ep.duration_min
        total = d.sum()
        summaries.append({"fra": fra, "name": name, "first": first, "last": last,
                          "valid_records": len(events), "union_episodes": len(ep),
                          "median_min": d.median(), "p90_min": d.quantile(.9), "p99_min": d.quantile(.99),
                          "over_30_pct": 100 * d.gt(30).mean(), "top_1pct_time_share_pct":
                          100 * d.nlargest(max(1, int(np.ceil(len(d) * .01)))).sum() / total,
                          "over_30_time_share_pct": 100 * d[d > 30].sum() / total,
                          "span_days": calendar.sum()/1440, "eligible_days": exposure.sum()/1440,
                          "union_blocked_hours": total/60,
                          "blocked_pct_span": 100 * total/calendar.sum(),
                          "blocked_pct_eligible": 100 * total/exposure.sum(),
                          "gaps_over24h": len(gaps), "gap_days": (calendar.sum()-exposure.sum())/1440})
        for gap in [0, 1, 2, 5]:
            merged = union_intervals(events, gap)
            for threshold in [6, 12, 24, 48, np.inf]:
                # Fix exposure to the zero-gap union to isolate the merge assumption.
                missing = gaps_between(ep, threshold)
                exp_min = calendar.sum() - ((missing.end-missing.start).dt.total_seconds()/60).sum()
                sensitivity.append({"name": name, "merge_gap_min": gap,
                                    "silence_threshold_h": str(threshold), "episodes": len(merged),
                                    "eligible_days": exp_min/1440,
                                    "blocked_pct": 100*merged.duration_min.sum()/exp_min,
                                    "added_clear_minutes": merged.duration_min.sum()-total})
        for threshold in [5, 10, 15, 30, 60, 120, 1440]:
            tails.append({"name": name, "threshold_min": threshold, "episodes_over": int(d.gt(threshold).sum()),
                          "episodes_pct": 100*d.gt(threshold).mean(),
                          "blocked_time_pct": 100*d[d > threshold].sum()/total})
        for elapsed in [0, 5, 10, 15, 30, 60]:
            remaining = d[d > elapsed] - elapsed
            residual.append({"name": name, "elapsed_min": elapsed, "episodes_at_risk": len(remaining),
                             "median_remaining_min": remaining.median(), "p90_remaining_min": remaining.quantile(.9),
                             "p_more_than_10min": remaining.gt(10).mean()})
        state = interval_mask(ep, origin, len(time))
        obs = interval_mask(span, origin, len(time)) & ~interval_mask(gaps, origin, len(time))
        states.append(state)
        eligible.append(obs)
    summary = pd.DataFrame(summaries)
    daily = pd.concat(daily_rows, ignore_index=True)
    sens = pd.DataFrame(sensitivity)
    states, eligible = np.array(states), np.array(eligible)
    print(f"Loaded {len(raw):,} rows; {len(clean):,} valid unique records; {len(intervals):,} union episodes", flush=True)

    # Calendar exposure is allocated exactly, rather than to episode start day.
    monthly = daily.assign(month=daily.day.dt.to_period("M").astype(str)).groupby(["name", "month"], as_index=False)[
        ["blocked_min", "eligible_min", "span_min", "episodes"]].sum()
    monthly["blocked_pct"] = 100*monthly.blocked_min/monthly.eligible_min.replace(0, np.nan)
    monthly["eligible_days"] = monthly.eligible_min/1440
    monthly["usable_for_trend"] = monthly.eligible_days >= 15
    hourly, joint, concurrency, baseline = [], [], [], []
    clock_hour = time.hour.to_numpy()
    how = time.dayofweek.to_numpy()*24 + clock_hour
    for k, name in enumerate(names):
        for hour in range(24):
            m = eligible[k] & (clock_hour == hour)
            hourly.append({"name": name, "hour": hour, "eligible_ticks": m.sum(),
                           "blocked_pct": 100*states[k, m].mean() if m.any() else np.nan})
        for j in range(k+1, len(names)):
            mask = eligible[k] & eligible[j]
            a, b = states[k, mask], states[j, mask]
            pa, pb = a.mean(), b.mean()
            joint.append({"a": name, "b": names.iloc[j], "joint_eligible_days": mask.sum()/1440,
                          "a_blocked_pct": pa*100, "b_blocked_pct": pb*100,
                          "both_blocked_pct": (a & b).mean()*100,
                          "p_b_given_a_pct": b[a].mean()*100 if a.any() else np.nan,
                          "lift": (a & b).mean()/(pa*pb) if pa*pb > 0 else np.nan})
        # Simple diagnostic forecast with target timestamps strictly inside split.
        # Hour-of-week and current-state probabilities fitted only before Jan 2025.
        for horizon in [5, 10, 15, 30, 60]:
            t = np.arange(0, len(time)-horizon, 5)
            t = t[horizon_valid(eligible[k], horizon)[t]]
            target = t + horizon
            train = time[target] < pd.Timestamp("2025-01-01")
            if not train.any():
                continue
            y = states[k, target].astype(float)
            current = states[k, t].astype(int)
            prior = y[train].mean()
            hw = how[target]
            n = np.bincount(hw[train], minlength=168)
            clim = (np.bincount(hw[train], weights=y[train], minlength=168)+20*prior)/(n+20)
            count = np.bincount(current[train], minlength=2)
            conditional = (np.bincount(current[train], weights=y[train], minlength=2)+20*prior)/(count+20)
            for split, lo, hi in [("validation", "2025-01-01", "2025-07-01"),
                                  ("test", "2025-07-01", "2100-01-01")]:
                mask = (time[t] >= pd.Timestamp(lo)) & (time[target] < pd.Timestamp(hi))
                if not mask.any():
                    continue
                ref = np.mean((clim[hw[mask]]-y[mask])**2)
                for model, pred in [("hour_of_week", clim[hw]), ("persistence", current),
                                    ("current_state_probability", conditional[current])]:
                    score = np.mean((pred[mask]-y[mask])**2)
                    baseline.append({"name": name, "horizon_min": horizon, "split": split,
                                     "model": model, "train_samples": train.sum(), "samples": mask.sum(),
                                     "target_blocked_pct": 100*y[mask].mean(), "brier": score,
                                     "brier_skill": 1-score/ref if ref > 0 else np.nan})
    allobs = eligible.all(axis=0)
    count = states[:, allobs].sum(axis=0)
    for n in range(9):
        concurrency.append({"blocked_crossings": n, "eligible_ticks": int(allobs.sum()),
                            "ticks": int((count == n).sum()), "pct": 100*(count == n).mean()})

    # Matched July–August windows avoid comparing different seasons or partial months.
    compare = daily[(daily.day.dt.month.isin([7, 8])) & daily.day.dt.year.isin([2025, 2026])].copy()
    compare["year"] = compare.day.dt.year
    drift = compare.groupby(["name", "year"], as_index=False)[["blocked_min", "eligible_min"]].sum()
    drift["eligible_days"] = drift.eligible_min/1440
    drift["blocked_pct"] = 100*drift.blocked_min/drift.eligible_min.replace(0, np.nan)
    drift = drift.set_index(["name", "year"]).reindex(
        pd.MultiIndex.from_product([names.values, [2025, 2026]], names=["name", "year"])).reset_index()
    # Day bootstrap is descriptive, with whole days as clusters. Temporal dependence
    # beyond a day and sensor assumptions are not represented in these intervals.
    rng = np.random.default_rng(20260925)
    ci = []
    for (name, year), group in compare.groupby(["name", "year"]):
        group = group[group.eligible_min >= 720]
        if len(group) < 15:
            continue
        ix = rng.integers(0, len(group), (1000, len(group)))
        ratios = 100*group.blocked_min.to_numpy()[ix].sum(1)/group.eligible_min.to_numpy()[ix].sum(1)
        ci.append({"name": name, "year": year, "days_ge12h": len(group),
                   "blocked_pct_days_ge12h": 100*group.blocked_min.sum()/group.eligible_min.sum(),
                   "day_bootstrap_p025": np.quantile(ratios, .025), "day_bootstrap_p975": np.quantile(ratios, .975)})
    quality = raw.groupby(["fra", "name"], as_index=False).agg(raw_rows=("fra", "size"),
                    invalid_rows=("invalid", "sum"), duplicate_keys=("duplicate", "sum"))
    full_raw, full_clean = read_events(args.full_input)
    inventory = full_raw.groupby(["fra", "name"], as_index=False).agg(rows=("fra", "size"),
        first=("start", "min"), last=("start", "max"), invalid_rows=("invalid", "sum"))
    signatures = {}
    for fra, group in full_raw.groupby("fra"):
        normalized = group[["start", "duration_min"]].sort_values(["start", "duration_min"]).to_csv(index=False)
        signatures.setdefault(hashlib.sha256(normalized.encode()).hexdigest(), []).append(fra)
    duplicate_feeds = [ids for ids in signatures.values() if len(ids) > 1]
    # Multiset comparison verifies that focused records match the full source.
    keys = ["fra", "start", "duration_min"]
    a = raw.groupby(keys, dropna=False).size().sort_index()
    b = full_raw[full_raw.fra.isin(selected)].groupby(keys, dropna=False).size().sort_index()
    focused_matches = a.equals(b)
    baseline_frame = pd.DataFrame(baseline)
    test_scores = baseline_frame[baseline_frame.split.eq("test")].pivot(
        index=["name", "horizon_min"], columns="model", values="brier_skill").reset_index()
    outputs = {"crossing_summary": summary, "data_quality": quality, "daily_exposure": daily,
               "monthly_patterns": monthly, "assumption_sensitivity": sens, "duration_tails": pd.DataFrame(tails),
               "remaining_duration": pd.DataFrame(residual), "hourly_patterns": pd.DataFrame(hourly),
               "joint_blockage": pd.DataFrame(joint), "concurrency": pd.DataFrame(concurrency),
               "forecast_baselines": baseline_frame, "matched_season_comparison": drift,
               "suspect_day_sensitivity": pd.DataFrame(fault_sensitivity),
               "matched_season_bootstrap": pd.DataFrame(ci), "full_network_inventory": inventory}
    for filename, frame in outputs.items():
        frame.to_csv(tables / f"{filename}.csv", index=False)

    # Figures and report share the exact same computed tables.
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    s = summary.sort_values("blocked_pct_eligible")
    axes[0].barh(s.name, s.blocked_pct_eligible, color=COLORS[0], label="Exclude >24h silence")
    axes[0].scatter(s.blocked_pct_span, s.name, color=COLORS[1], zorder=3, label="Entire recorded span")
    axes[0].set(xlabel="Recorded blocked time (%)", title="Coverage assumptions change exposure")
    axes[0].legend(fontsize=8)
    axes[1].barh(s.name, s.over_30_time_share_pct, color=COLORS[1])
    axes[1].set(xlabel="Share of recorded blocked minutes (%)", title="Contribution of episodes longer than 30 min", xlim=(0,100))
    fig.savefig(figures/"01_burden_and_tails.png"); plt.close(fig)
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), layout="constrained", sharey=True)
    for ax, (name, group), color in zip(axes.flat, monthly.groupby("name"), COLORS):
        ax.plot(pd.to_datetime(group.month), group.blocked_pct.where(group.usable_for_trend), color=color)
        ax.set(title=name, ylabel="Blocked time (%)")
        ax.tick_params(axis="x", rotation=45)
    fig.suptitle("Monthly burden: show months with at least 15 eligible days")
    fig.savefig(figures/"02_monthly_patterns.png"); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for name, group in sens[sens.merge_gap_min.eq(0)].groupby("name"):
        finite = group[group.silence_threshold_h.ne("inf")]
        axes[0].plot(finite.silence_threshold_h.astype(float), finite.blocked_pct, marker="o", label=name)
    axes[0].set(xlabel="Exclude silent intervals longer than (hours)", ylabel="Blocked time (%)", title="Silence threshold sensitivity")
    axes[0].legend(fontsize=7, ncol=2)
    merge = sens[sens.silence_threshold_h.eq("24")]
    for name, group in merge.groupby("name"):
        axes[1].plot(group.merge_gap_min, group.added_clear_minutes/60, marker="o", label=name)
    axes[1].set(xlabel="Clear gap bridged (minutes)", ylabel="Extra time labeled blocked (hours)", title="Bridging gaps adds clear time")
    fig.savefig(figures/"03_assumption_sensitivity.png"); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    axes[0].bar(range(9), [r["pct"] for r in concurrency], color=COLORS[0])
    axes[0].set(xlabel="Number of crossings blocked", ylabel="Share of eligible minute ticks (%)",
                title=f"All eight eligible: {allobs.sum()/1440:.1f} days", xticks=range(9))
    h = pd.DataFrame(hourly).pivot(index="name", columns="hour", values="blocked_pct")
    im = axes[1].imshow(h, aspect="auto", cmap="YlOrRd", vmin=0)
    axes[1].set(yticks=range(len(h)), yticklabels=h.index, xticks=[0,6,12,18,23], xlabel="Local clock hour", title="Hourly blocked state (%)")
    fig.colorbar(im, ax=axes[1], shrink=.8)
    fig.savefig(figures/"04_concurrency_and_hour.png"); plt.close(fig)
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), layout="constrained", sharey=True)
    for ax, name in zip(axes.flat, names):
        ep = intervals[intervals.name.eq(name)].duration_min.sort_values().to_numpy()
        ax.step(ep, 100*(len(ep)-np.arange(len(ep)))/len(ep), where="post", color=COLORS[0])
        ax.set(xscale="log", yscale="log", title=name, xlabel="Duration (minutes)", ylabel="Episodes at least this long (%)")
    fig.suptitle("Duration survival curves: overlapping records unioned, no clear gaps filled")
    fig.savefig(figures/"05_duration_survival.png"); plt.close(fig)
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), layout="constrained", sharey=True)
    for ax, name in zip(axes.flat, names):
        scores = test_scores[test_scores.name.eq(name)]
        ax.axhline(0, color="#777", ls="--", lw=1)
        if len(scores):
            ax.plot(scores.horizon_min, scores.current_state_probability, marker="o", color=COLORS[0], label="Current-state probability")
            ax.plot(scores.horizon_min, scores.persistence, marker="o", color=COLORS[1], label="Persistence")
        else:
            ax.text(.5, .5, "No pre-2025 training data", transform=ax.transAxes, ha="center", fontsize=9)
        ax.set(title=name, xlabel="Forecast horizon (minutes)", ylabel="Brier skill vs hour-of-week", xticks=[5,15,30,60])
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Held-out baseline diagnostics: train before 2025, test from July 2025")
    fig.savefig(figures/"06_forecast_baselines.png"); plt.close(fig)

    manifest = {"inputs": [{"path": str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p),
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in [args.input, args.full_input]],
                "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                "matplotlib": matplotlib.__version__, "raw_rows": len(raw), "clean_rows": len(clean),
                "union_episodes": len(intervals), "full_rows": len(full_raw), "full_fra_ids": full_raw.fra.nunique(),
                "duplicate_feed_groups": duplicate_feeds, "focused_matches_full": focused_matches,
                "all_eight_eligible_days": allobs.sum()/1440, "timezone": "unverified America/Chicago wall clock, naive",
                "primary_merge_gap_min": 0, "silence_threshold_h": 24, "bootstrap_seed": 20260925,
                "no_fault_day_exclusion": True}
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2, default=str)+"\n")
    top = summary.sort_values("blocked_pct_eligible", ascending=False).iloc[0]
    tail = summary.sort_values("over_30_time_share_pct", ascending=False).iloc[0]
    strongest = pd.DataFrame(joint).sort_values("lift", ascending=False).iloc[0]
    added = sens[(sens.merge_gap_min.eq(2)) & sens.silence_threshold_h.eq("24")].added_clear_minutes.sum()/60
    sections = []
    def section(title, text, table=None, image=None):
        sections.append((title, text, table, image))
    section("What the extended analysis shows",
        f"The focused export contains {len(raw):,} rows. Removing invalid/nonpositive durations and duplicate event keys leaves "
        f"{len(clean):,} records, representing {len(intervals):,} disjoint blockage episodes after overlap union. "
        f"{top['name']} has the largest recorded blocked-time share under the 24-hour silence scenario ({top.blocked_pct_eligible:.2f}%). "
        f"At {tail['name']}, episodes longer than 30 minutes account for {tail.over_30_time_share_pct:.1f}% of blocked time. "
        f"Bridging gaps up to two minutes adds {added:,.1f} hours of originally clear time across the eight crossings.")
    section("Crossing burden and long tails",
        "The denominator is each crossing's first valid start through last valid end, minus entire silent gaps longer than 24 hours. "
        "This is an assumed eligible window, not verified uptime. Long durations are retained and should be investigated with the provider. "
        "Unioning overlaps avoids counting the same blocked minute twice. No short clear gaps are filled in the primary analysis.",
        summary[["name", "union_episodes", "median_min", "p90_min", "blocked_pct_span", "blocked_pct_eligible", "over_30_time_share_pct"]],
        "01_burden_and_tails.png")
    section("Time trends and comparable seasons",
        "Monthly lines omit months with fewer than 15 eligible days. Missing lines do not mean zero blockages. "
        "The table compares July–August 2025 with the same months of 2026 to reduce seasonal and partial-month confounding. "
        "Market has no July–August 2026 records, so that comparison is unavailable. Differences still mix train activity, duration quality, and sensor availability. Bootstrap intervals in the supporting table resample "
        "whole days with at least 12 eligible hours, use 1,000 draws, and do not account for dependence across days or systematic coverage errors.",
        drift[["name", "year", "eligible_days", "blocked_pct"]], "02_monthly_patterns.png")
    section("Sensitivity to preparation choices",
        "The primary analysis retains suspect burst days rather than treating an unverified flag as proof of a fault. "
        "The archive's centered 29-active-day rolling rule is retrospective and must not be used as an online feature. "
        "Silence thresholds of 6, 12, 24, 48 hours and no silence exclusion are reported separately. "
        "Merge thresholds of 0, 1, 2 and 5 minutes use the same zero-gap exposure denominator so the additional blocked time is explicit. "
        "The table also quantifies exclusion of suspect days identified by the contributed centered burst heuristic, rebuilt from valid two-minute-merged episodes. "
        "It subtracts those days from both continuous blocked time and eligible exposure, without labeling the flags as confirmed faults.",
        pd.DataFrame(fault_sensitivity),
        image="03_assumption_sensitivity.png")
    section("Simultaneous blockage and daily timing",
        f"All eight crossings share {allobs.sum()/1440:.1f} eligible days under the silence assumption. "
        f"The strongest pairwise simultaneous-blockage lift is {strongest.a} / {strongest.b} ({strongest.lift:.2f} times the product of "
        "their marginal rates on jointly eligible minutes). Pairwise windows differ. Association does not establish a shared train, "
        "travel direction, or a route obstruction. Hourly estimates use exact minute ticks and can differ slightly from continuous-time burden. "
        "Concurrency includes every possible count from zero through eight.",
        pd.DataFrame(joint).sort_values("lift", ascending=False).head(8), "04_concurrency_and_hour.png")
    section("Duration tails and remaining waits",
        "Survival curves and remaining-duration tables describe completed, recorded union episodes. The remaining wait is conditional "
        "on an episode exceeding the stated elapsed time, with the number at risk reported. Boundary censoring and source truncation are "
        "unknown. These estimates describe recorded blockages and are not estimates of fire-engine response delay.",
        image="05_duration_survival.png")
    section("Forecast readiness",
        "A lightweight baseline check predicts blocked state at 5, 10, 15, 30 and 60 minutes. Models use training targets before "
        "January 2025, validation from January–June 2025, and test from July 2025 onward. Every tick between issue and target must be "
        "eligible, and issue/target timestamps must stay within the evaluation split. Baselines are hour-of-week frequency, persistence, "
        "and an empirical probability conditional on the current state, with 20 training observations of shrinkage. "
        "Telephone has no pre-2025 training history and is omitted from these fitted baselines. Brier scores and counts are supplied per "
        "crossing, horizon, model and split. These are retrospective diagnostics: silence masks use future information and sensor uptime "
        "must be available independently for an operational evaluation. Earlier archived model scores require correction before reuse. "
        "The table shows 10-minute test skill by crossing; positive values improve on the hour-of-week baseline, and negative values are worse.",
        test_scores[test_scores.horizon_min.eq(10)][["name", "current_state_probability", "persistence"]], "06_forecast_baselines.png")
    section("Source audit and reproducibility",
        f"The full source has {len(full_raw):,} rows and {full_raw.fra.nunique()} FRA identifiers. Identical complete timestamp/duration "
        f"multisets occur in these identifier groups: {duplicate_feeds}. Focused/full-source multiset match: {focused_matches}. "
        "Do not count identical feeds as independent evidence. Input SHA-256 hashes and package versions are stored in manifest.json. "
        "Timestamps remain naive local-clock values because the source does not supply offsets. DST ambiguity remains unresolved; "
        "absence of events in a clock hour does not prove a timezone. Run `.venv/bin/python -m analysis.run_eda` from the repository root.", quality)
    section("Next research priorities",
        "Obtain sensor heartbeat/uptime and timezone documentation; adjudicate long records and suspect burst days; validate actual "
        "rail connectivity before interpreting lead–lag results; add dispatch timestamps and routes before translating crossing burden "
        "into HFD response impact. A subsequent model evaluation should use causal missingness handling, a frozen validation design, "
        "calibration, and held-out crossing/time tests.")
    md = ["# HFD crossing EDA: consolidated findings\n", "Generated from the local September 20, 2026 export.\n"]
    web = ["<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
           "<title>HFD crossing EDA</title><style>body{font:16px/1.6 system-ui;color:#243447;max-width:1200px;margin:40px auto;padding:0 24px}h1,h2{color:#173b60}img{width:100%;height:auto}table{border-collapse:collapse;font-size:13px;width:100%}th,td{padding:8px;text-align:right;border-bottom:1px solid #ddd}th:first-child,td:first-child{text-align:left}.table{overflow:auto}section{margin:42px 0}p{max-width:1000px}</style>",
           "<h1>HFD crossing EDA</h1><p>Consolidated analysis of the local September 20, 2026 export.</p>"]
    for title, text, table, picture in sections:
        md += [f"## {title}\n", text+"\n"]
        web += [f"<section><h2>{html.escape(title)}</h2><p>{html.escape(text)}</p>"]
        if picture:
            md.append(f"![{title}](figures/{picture})\n")
            web.append(f"<img src='figures/{picture}' alt='{html.escape(title)}'>")
        if table is not None:
            display = table.rename(columns=lambda c: c.replace("_", " ").capitalize())
            md.append(markdown_table(display)+"\n")
            web.append("<div class='table'>"+display.to_html(index=False, na_rep="—", float_format=lambda v:f"{v:.2f}", border=0)+"</div>")
        web.append("</section>")
    web.append("</html>")
    (out/"README.md").write_text("\n".join(md))
    (out/"report.html").write_text("\n".join(web))
    print(f"Wrote {len(outputs)} tables, 6 figures, report and manifest to {out}", flush=True)


if __name__ == "__main__":
    main()

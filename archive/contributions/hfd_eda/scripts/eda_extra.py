"""Additional exploration that extends scripts/eda.py (Peikun's). Run prepare.py first.

Adds:
  figA  full 67-sensor network coverage (why the 8 study crossings)
  figB  worked wrangling example: raw records -> episodes -> minute-level state
  figC  sensitivity of cleaning choices (merge gap, outage threshold)
  figD  target variable: base rates and how fast the current state stops being informative
  figE  re-blocking: after a crossing clears, how soon is it blocked again?
  figF  day-of-week and long-term (monthly) patterns
  tables: wrangling funnel, full-network inventory, temporal split, DST check
Writes reports/eda_extra_stats.json and reports/tables/*.csv
"""
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import matplotlib.dates
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eda  # noqa: E402  (reuses Grid, palette, ORDER, rcParams)
import prepare  # noqa: E402
from eda import CAT, BLUE, INK, INK2, MUTED, GRID, SURF, ORDER, Grid  # noqa: E402

ROOT = eda.ROOT
FIG = eda.FIG
TAB = ROOT / "reports" / "tables"
TAB.mkdir(parents=True, exist_ok=True)
FULL = ROOT / "data" / "trainfo_all_updated_2026-09-20.csv"
STATS = {}
SPLITS = {"train": ("2022-09-01", "2025-01-01"), "validation": ("2025-01-01", "2025-07-01"),
          "test": ("2025-07-01", "2026-09-21")}


# ------------------------------------------------------------------ full network
def full_network():
    df = pd.read_csv(FULL, encoding="utf-8-sig")
    df.columns = ["fra", "loc", "date", "time", "dur"]
    df["start"] = pd.to_datetime(df["date"] + " " + df["time"], format="mixed")
    inv = (df.groupby(["fra", "loc"]).agg(records=("dur", "size"), first=("start", "min"),
                                          last=("start", "max"), median_min=("dur", "median"))
             .reset_index().sort_values("records", ascending=False))
    # identical feeds registered under two FRA ids
    sig = df.groupby("fra").apply(lambda g: hash(tuple(sorted(zip(g["date"], g["time"], g["dur"])))))
    dup = sig[sig.duplicated(keep=False)]
    pairs = dup.groupby(dup).apply(lambda s: list(s.index)).tolist()
    study = set(pd.read_csv(ROOT / "data" / "processed" / "stations.csv")["fra"])
    inv["study"] = inv["fra"].isin(study)
    inv.to_csv(TAB / "full_network_inventory.csv", index=False)
    STATS["full_network"] = {
        "records": int(len(df)), "fra_ids": int(df.fra.nunique()), "locations": int(df["loc"].nunique()),
        "duplicate_feed_pairs": pairs, "span": [str(df.start.min()), str(df.start.max())],
        "n_negative_duration": int((df.dur < 0).sum()), "n_over_24h": int((df.dur > 1440).sum()),
        "max_duration_min": float(df.dur.max()),
        "n_started_before_2024_06": int((inv["first"] < "2024-06-01").sum()),
        "second_resolution_records": int((df.time.str.len() > 5).sum()),
    }
    # figure A: monthly record counts for every sensor, study crossings on top
    df["month"] = df["start"].dt.to_period("M").dt.start_time
    dupe_ids = {p[1] if p[0] in study else p[0] for p in pairs}  # drop the second id of each pair
    keep = inv[~inv.fra.isin(dupe_ids)]
    order_fra = pd.read_csv(ROOT / "data" / "processed" / "stations.csv").set_index("short").loc[ORDER, "fra"]
    keep = pd.concat([keep.set_index("fra").loc[list(order_fra)].reset_index(), keep[~keep.study]])
    months = pd.date_range(df.month.min(), df.month.max(), freq="MS")
    piv = (df[df.fra.isin(keep.fra)].pivot_table(index="fra", columns="month", values="dur", aggfunc="size")
             .reindex(index=keep.fra, columns=months))
    fig, ax = plt.subplots(figsize=(13, 13))
    from matplotlib.colors import LogNorm, LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("b", BLUE); cmap.set_bad("#eeede8")
    im = ax.imshow(piv.values, aspect="auto", cmap=cmap, norm=LogNorm(1, piv.max().max()),
                   interpolation="nearest")
    fix = {"75Th": "75th", "Wb ": "WB ", "I 610": "I-610", "Mccarty St": "McCarty Street",
           " Dr": " Drive", " Rd": " Road"}
    labels = []
    for _, r in keep.iterrows():
        lab = r["loc"].title()
        for a, b in fix.items():
            lab = re.sub(re.escape(a) + r"\b", b, lab) if a.startswith(" ") else lab.replace(a, b)
        labels.append(lab)
    ax.set_yticks(range(len(keep))); ax.set_yticklabels(labels, fontsize=10.5)
    for t, s in zip(ax.get_yticklabels(), keep.study):
        if s:
            t.set_fontweight("bold"); t.set_color(CAT[1])
    nst = int(keep.study.sum())
    ax.axhline(nst - 0.5, color=CAT[1], lw=2)
    yr = [i for i, m in enumerate(months) if m.month == 1]
    ax.set_xticks(yr); ax.set_xticklabels([months[i].strftime("%Y") for i in yr])
    ax.axvline(list(months).index(pd.Timestamp("2024-06-01")) + 0.5, color=INK, lw=1, ls="--")
    ax.text(list(months).index(pd.Timestamp("2024-06-01")) - 0.5, 22,
            "most of the network\nstarts reporting\nin late June 2024 \u2192", fontsize=12, color=INK,
            ha="right", va="center")
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, pad=0.01, fraction=0.025); cb.set_label("records per month (log scale)")
    cb.outline.set_visible(False)
    ax.set_title("Every TRAINFO sensor in Houston, month by month (orange = the eight study crossings)",
                 loc="left")
    fig.savefig(FIG / "figA_network_coverage.png"); plt.close(fig)
    return df


# ------------------------------------------------------------------ DST check
def dst_check(ev):
    spring = ["2023-03-12", "2024-03-10", "2025-03-09", "2026-03-08"]
    fall = ["2022-11-06", "2023-11-05", "2024-11-03", "2025-11-02"]
    ndays = ev.start.dt.normalize().nunique()
    base2 = (ev.start.dt.hour == 2).sum() / ndays
    base1 = (ev.start.dt.hour == 1).sum() / ndays
    sp = {d: int(((ev.start >= f"{d} 02:00") & (ev.start < f"{d} 03:00")).sum()) for d in spring}
    fa = {d: int(((ev.start >= f"{d} 01:00") & (ev.start < f"{d} 02:00")).sum()) for d in fall}
    from math import exp
    STATS["dst"] = {"spring_forward_2am_counts": sp, "typical_2am_count_per_day": round(base2, 2),
                    "p_all_zero_if_no_dst": exp(-base2) ** len(spring),
                    "fall_back_1am_counts": fa, "typical_1am_count_per_day": round(base1, 2)}


# ------------------------------------------------------------------ wrangling funnel
def funnel(ev, ep, og, g):
    raw = pd.read_csv(prepare.RAW, encoding="utf-8-sig")
    rows = [("Raw rows in the eight-crossing export", len(raw)),
            ("After removing exact duplicate rows", len(ev)),
            ("Durations below zero set to zero", int(ev.flag_nonpos.sum())),
            ("Blockage episodes after joining records <= 2 min apart", len(ep))]
    fault = og[og.kind == "fault"]
    in_fault = np.zeros(len(ep), bool)
    for r in fault.itertuples():
        in_fault |= ((ep.fra == r.fra) & (ep.start >= r.gap_start) & (ep.start < r.gap_end)).to_numpy()
    rows += [("Episodes on flagged sensor-fault days (excluded)", int(in_fault.sum())),
             ("Episodes kept for analysis", int((~in_fault).sum())),
             ("Sensor-outage intervals (> 24 h with no record)", int((og.kind == "gap").sum())),
             ("Minute-level grid: crossings x minutes", f"8 x {g.T:,}"),
             ("Crossing-minutes with the sensor reporting", f"{int(g.obs.sum()):,}"),
             ("  ...of which blocked", f"{int((g.occ & g.obs).sum()):,}")]
    t = pd.DataFrame(rows, columns=["Step", "Count"])
    t.to_csv(TAB / "wrangling_funnel.csv", index=False)
    STATS["funnel"] = {r[0]: (r[1] if isinstance(r[1], str) else int(r[1])) for r in rows}
    return in_fault


# ------------------------------------------------------------------ worked example
def fig_wrangle_example(ev, ep, g):
    s = "York"; k = ORDER.index(s)
    e = ev[ev.s == s]
    # pick the hour with the most fragments (merged episodes with >= 3 records), within normal operation
    # a typical hour: 3-5 episodes, one of them built from 3-5 records, nothing pathological
    ep_s = ep[(ep.s == s) & (ep.start > "2024-01-01")].sort_values("start").reset_index(drop=True)
    t0 = None
    for i in ep_s.index[ep_s.n_fragments.between(3, 5)]:
        a = ep_s.loc[i, "start"] - pd.Timedelta(minutes=25)
        w = ep_s[(ep_s.end > a) & (ep_s.start < a + pd.Timedelta(minutes=70))]
        if 3 <= len(w) <= 5 and w.n_fragments.max() <= 5 and (w.start > a).all() and \
                (w.end < a + pd.Timedelta(minutes=70)).all() and w.dur_min.min() > 1:
            t0 = a.floor("5min"); break
    t1 = t0 + pd.Timedelta(minutes=70)
    fig, axs = plt.subplots(3, 1, figsize=(13, 6.8), sharex=True, gridspec_kw={"hspace": 0.45})
    mins = lambda ts: (pd.to_datetime(ts) - t0).dt.total_seconds() / 60 if hasattr(ts, "dt") else \
        (ts - t0).total_seconds() / 60
    ee = e[(e.end > t0) & (e.start < t1)]
    for i, r in enumerate(ee.itertuples()):
        axs[0].barh(0, mins(r.end) - mins(r.start), left=mins(r.start), height=0.5,
                    color=CAT[3], edgecolor=INK, lw=0.6)
    axs[0].set_title(f"(a) Raw records at {s} St: {len(ee)} rows",
                     loc="left")
    pp = ep[(ep.s == s) & (ep.end > t0) & (ep.start < t1)]
    for r in pp.itertuples():
        axs[1].barh(0, mins(r.end) - mins(r.start), left=mins(r.start), height=0.5, color=CAT[0],
                    edgecolor=INK, lw=0.6)
        axs[1].text((mins(r.start) + mins(r.end)) / 2, 0.36,
                    f"{r.n_fragments} record" + ("s" if r.n_fragments > 1 else ""), ha="center",
                    fontsize=11, color=INK2)
    axs[1].set_title(f"(b) After joining records separated by 2 minutes or less: {len(pp)} blockage episodes",
                     loc="left")
    m0 = g.m(t0); x = np.arange(70)
    axs[2].step(x, g.occ[k, m0:m0 + 70].astype(int), where="post", color=INK, lw=1.8)
    axs[2].fill_between(x, 0, g.occ[k, m0:m0 + 70].astype(int), step="post", color=CAT[0], alpha=0.25)
    axs[2].set_yticks([0, 1]); axs[2].set_yticklabels(["clear", "blocked"]); axs[2].set_ylim(-0.2, 1.3)
    axs[2].set_title("(c) Minute-by-minute state used as the prediction target", loc="left")
    for ax in axs[:2]:
        ax.set_yticks([]); ax.set_ylim(-0.4, 0.6)
    axs[2].set_xlim(0, 70)
    axs[2].set_xlabel(f"minutes after {t0:%H:%M} on {t0:%d %B %Y}")
    fig.savefig(FIG / "figB_wrangling_example.png"); plt.close(fig)
    STATS["wrangle_example_window"] = [str(t0), str(t1)]


# ------------------------------------------------------------------ sensitivity
def sensitivity(ev):
    rows = []
    for gap in (0.0, 1.0, 2.0, 5.0):
        prepare.MERGE_GAP_MIN = gap
        ep = prepare.build_episodes(ev)
        for s_name, d in ep.groupby("name"):
            rows.append({"param": "merge_gap_min", "value": gap, "crossing": s_name, "episodes": len(d),
                         "median_min": d.dur_min.median(), "short_frac": (d.dur_min < 1).mean()})
    prepare.MERGE_GAP_MIN = 2.0
    ep = prepare.build_episodes(ev)
    st = pd.read_csv(ROOT / "data" / "processed" / "stations.csv")
    out_rows = []
    for h in (6.0, 12.0, 24.0, 48.0):
        prepare.OUTAGE_H = h
        og = prepare.build_outages(ev, ep, st)
        gg = og[og.kind == "gap"].groupby("name")["hours"].agg(["size", "sum"])
        for s_name in st.name:
            n, tot = (gg.loc[s_name] if s_name in gg.index else (0, 0.0))
            out_rows.append({"param": "outage_h", "value": h, "crossing": s_name, "n_gaps": int(n),
                             "days_unobserved": tot / 24})
    prepare.OUTAGE_H = 24.0
    a, b = pd.DataFrame(rows), pd.DataFrame(out_rows)
    a.to_csv(TAB / "sensitivity_merge_gap.csv", index=False); b.to_csv(TAB / "sensitivity_outage.csv", index=False)
    short = {v: k for k, v in prepare.SHORT.items()}
    fig, axs = plt.subplots(1, 3, figsize=(16, 5.2))
    for i, s in enumerate(ORDER):
        d = a[a.crossing == short[s]]
        axs[0].plot(d.value, d.episodes / d.episodes.iloc[0] * 100, marker="o", color=CAT[i], label=s)
        axs[1].plot(d.value, d.median_min, marker="o", color=CAT[i])
        o = b[b.crossing == short[s]]
        axs[2].plot(o.value, o.days_unobserved, marker="o", color=CAT[i])
    axs[0].set_xlabel("joining gap (minutes)"); axs[0].set_ylabel("episodes, % of count with no joining")
    axs[0].set_title("(a) Number of blockages", loc="left")
    axs[1].set_xlabel("joining gap (minutes)"); axs[1].set_ylabel("median blockage length (minutes)")
    axs[1].set_title("(b) Typical blockage length", loc="left")
    for ax in axs[:2]:
        ax.axvline(2, color=INK, ls=":", lw=1); ax.set_xticks([0, 1, 2, 5])
    axs[2].set_xscale("log"); axs[2].set_xticks([6, 12, 24, 48]); axs[2].set_xticklabels([6, 12, 24, 48])
    axs[2].axvline(24, color=INK, ls=":", lw=1)
    axs[2].set_xlabel("hours without a record before calling it an outage"); axs[2].set_ylabel("days marked as outage")
    axs[2].set_title("(c) Time marked as sensor outage", loc="left")
    axs[2].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=8, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("How much do the cleaning choices matter? (dotted line = value used)", x=0.01, ha="left",
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0.07, 1, 0.94)); fig.savefig(FIG / "figC_sensitivity.png"); plt.close(fig)
    STATS["sensitivity_merge"] = a.groupby("value")[["episodes"]].sum()["episodes"].to_dict()
    STATS["sensitivity_outage_days"] = b.groupby("value")["days_unobserved"].sum().round(1).to_dict()


# ------------------------------------------------------------------ target variable
def target(g):
    H = [1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120]
    base, cond = {}, {}
    fig, axs = plt.subplots(1, 2, figsize=(16, 5.6), gridspec_kw={"width_ratios": [1, 1.5]})
    for k, s in enumerate(ORDER):
        o, y = g.obs[k], g.occ[k]
        base[s] = float(y[o].mean())
        pb, pc = [], []
        for h in H:
            ok = o[:-h] & o[h:]
            now, fut = y[:-h][ok], y[h:][ok]
            pb.append(fut[now].mean()); pc.append(fut[~now].mean())
        cond[s] = {"H": H, "p_blocked_given_blocked": np.round(pb, 3).tolist(),
                   "p_blocked_given_clear": np.round(pc, 3).tolist()}
        axs[1].plot(H, 100 * np.array(pb), color=CAT[k], marker="o", ms=4, label=s)
        axs[1].plot(H, 100 * np.array(pc), color=CAT[k], ls="--", lw=1.3)
    axs[0].barh(range(8), [100 * base[s] for s in ORDER], color=CAT[0])
    for i, s in enumerate(ORDER):
        axs[0].text(100 * base[s] + 0.3, i, f"{100 * base[s]:.1f}%", va="center", fontsize=11.5, color=INK2)
    axs[0].set_yticks(range(8)); axs[0].set_yticklabels(ORDER); axs[0].invert_yaxis()
    axs[0].set_xlabel("% of reporting minutes that are blocked"); axs[0].set_xlim(0, 20)
    axs[0].set_title("(a) Blocked minutes are the rare class", loc="left")
    axs[1].set_xscale("log"); axs[1].set_xticks(H); axs[1].set_xticklabels(H)
    axs[1].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    axs[1].set_xlabel("minutes ahead"); axs[1].set_ylabel("chance the crossing is blocked then (%)")
    axs[1].set_title("(b) Solid: blocked now.  Dashed: clear now.", loc="left")
    axs[1].legend(loc="upper right", ncol=2, fontsize=10.5)
    fig.suptitle("The prediction target: how rare is 'blocked', and how long does 'now' stay informative?",
                 x=0.01, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(FIG / "figD_target.png"); plt.close(fig)
    STATS["base_rate"] = {s: round(v, 4) for s, v in base.items()}
    STATS["conditional"] = cond


def splits(g):
    rows = []
    for name, (a, b) in SPLITS.items():
        m = (g.time >= a) & (g.time < b)
        for k, s in enumerate(ORDER):
            o = g.obs[k] & m
            rows.append({"split": name, "from": a, "to": b, "crossing": s, "days_observed": round(o.sum() / 1440, 1),
                         "blocked_pct": round(100 * g.occ[k][o].mean(), 2) if o.any() else np.nan})
    t = pd.DataFrame(rows)
    t.pivot(index="crossing", columns="split", values="days_observed").reindex(ORDER)[list(SPLITS)] \
        .to_csv(TAB / "split_days_observed.csv")
    t.pivot(index="crossing", columns="split", values="blocked_pct").reindex(ORDER)[list(SPLITS)] \
        .to_csv(TAB / "split_blocked_pct.csv")
    STATS["splits"] = SPLITS
    STATS["split_days"] = t.pivot(index="crossing", columns="split", values="days_observed").to_dict()


# ------------------------------------------------------------------ re-blocking
def reblock(ep, g):
    """P(new blockage starts within 10 min | crossing has been clear for x minutes)."""
    xs = np.array([2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180])
    W = 10
    fig, ax = plt.subplots(figsize=(11, 6))
    out = {}
    for k, s in enumerate(ORDER):
        e = ep[ep.s == s].sort_values("start")
        st, en = g.mf(e.start), g.mf(e.end)
        gaps = st[1:] - np.maximum.accumulate(en)[:-1]  # clear spell lengths
        ok = g.obs[k][np.clip(st[1:].astype(int), 0, g.T - 1)]
        gaps = gaps[ok & (gaps > 0) & (gaps < 24 * 60)]
        p = []
        for x in xs:
            alive = gaps > x
            p.append(((gaps <= x + W) & alive).sum() / max(alive.sum(), 1) if alive.sum() >= 30 else np.nan)
        out[s] = {"median_clear_min": round(float(np.median(gaps)), 1),
                  "p_reblock_10": [None if np.isnan(v) else round(float(v), 3) for v in p]}
        ax.plot(xs, 100 * np.array(p), color=CAT[k], marker="o", ms=4, label=s)
    ax.set_xscale("log"); ax.set_xticks(xs); ax.set_xticklabels(xs)
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("minutes since the crossing last cleared")
    ax.set_ylabel("chance a new blockage starts\nin the next 10 minutes (%)")
    ax.set_ylim(0, None)
    ax.set_title("If a crossing just cleared, how soon will it be blocked again?", loc="left")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), title="crossing")
    fig.tight_layout(); fig.savefig(FIG / "figE_reblock.png"); plt.close(fig)
    STATS["reblock"] = {"x": xs.tolist(), **out}


# ------------------------------------------------------------------ calendar
def calendar(g):
    dow = g.time.dayofweek.to_numpy()
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    codes, uniq = pd.factorize(g.time.to_period("M").start_time)
    M = np.full((8, 7), np.nan); monthly = {}
    for k, s in enumerate(ORDER):
        o = g.obs[k]
        M[k] = np.bincount(dow[o], g.occ[k][o], 7) / np.maximum(np.bincount(dow[o], minlength=7), 1)
        num = np.bincount(codes[o], g.occ[k][o], len(uniq)); den = np.bincount(codes[o], minlength=len(uniq))
        v = np.where(den >= 10 * 1440, 1440 * num / np.maximum(den, 1), np.nan)
        monthly[s] = pd.Series(v, index=uniq).sort_index()
    # (F) day of week, shown relative to each crossing's own average so the within-row pattern is visible
    rel = 100 * (M / M.mean(1, keepdims=True) - 1)
    fig, ax = plt.subplots(figsize=(10, 5.8))
    from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
    cm = LinearSegmentedColormap.from_list("d", [BLUE[5], SURF, CAT[1]])
    im = ax.imshow(rel, cmap=cm, norm=TwoSlopeNorm(0, -25, 25), aspect="auto")
    for i in range(8):
        for j in range(7):
            ax.text(j, i, f"{100 * M[i, j]:.1f}", ha="center", va="center", fontsize=11.5, color=INK)
    ax.set_xticks(range(7)); ax.set_xticklabels(names); ax.set_yticks(range(8)); ax.set_yticklabels(ORDER)
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.04)
    cb.set_label("% above or below the crossing's own average"); cb.outline.set_visible(False)
    ax.set_title("Percent of time each crossing is blocked, by day of week", loc="left")
    fig.tight_layout(); fig.savefig(FIG / "figF_dayofweek.png"); plt.close(fig)
    # (G) month by month, small multiples, with the proposed train / validation / test periods shaded
    fig, axs = plt.subplots(2, 4, figsize=(16, 7.2), sharex=True, sharey=True)
    shade = {"validation": BLUE[0], "test": "#fbe3d6"}
    means = {}
    for k, (ax, s) in enumerate(zip(axs.flat, ORDER)):
        for nm, (a, b) in SPLITS.items():
            if nm in shade:
                ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=shade[nm], lw=0, zorder=0)
        m = monthly[s]
        ax.plot(m.index, m.values, color=CAT[0], lw=1.8, marker="o", ms=2.5)
        means[s] = {}
        for nm, (a, b) in SPLITS.items():
            seg = m[(m.index >= a) & (m.index < b)]
            if seg.notna().sum() >= 2:
                means[s][nm] = round(float(seg.mean()), 0)
                if nm != "validation":
                    ax.hlines(seg.mean(), pd.Timestamp(a), pd.Timestamp(b), color=INK, lw=1.2, ls="--")
        ax.set_title(s, loc="left")
        ax.xaxis.set_major_locator(matplotlib.dates.YearLocator())
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    for ax in axs[:, 0]:
        ax.set_ylabel("minutes blocked per day")
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    fig.legend(handles=[Patch(color=BLUE[0], label="validation period (Jan-Jun 2025)"),
                        Patch(color="#fbe3d6", label="test period (Jul 2025 onward)"),
                        Line2D([], [], color=INK, ls="--", label="average over training / test period")],
               loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Blocked minutes per day, month by month: the level drifts over time",
                 x=0.01, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95)); fig.savefig(FIG / "figG_monthly.png"); plt.close(fig)
    STATS["dow_blocked_pct"] = {s: np.round(100 * M[k], 1).tolist() for k, s in enumerate(ORDER)}
    STATS["dow_max_rel_dev_pct"] = {s: round(float(np.abs(rel[k]).max()), 1) for k, s in enumerate(ORDER)}
    STATS["monthly_min_per_day_by_split"] = means
    STATS["monthly_min_per_day_range"] = {s: [round(float(np.nanmin(v)), 0), round(float(np.nanmax(v)), 0)]
                                          for s, v in monthly.items()}


def main():
    st, ep, ev, og = eda.load()
    g = Grid(ep, og)
    full_network()
    dst_check(ev)
    funnel(ev, ep, og, g)
    fig_wrangle_example(ev, ep, g)
    sensitivity(ev.drop(columns="s"))
    target(g)
    splits(g)
    reblock(ep, g)
    calendar(g)
    json.dump(STATS, open(ROOT / "reports" / "eda_extra_stats.json", "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in STATS.items() if k not in ("conditional",)}, indent=1, default=str))


if __name__ == "__main__":
    main()

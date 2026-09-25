"""Exploratory analysis of the 8 Houston crossings. Writes figures to reports/figures/
and headline numbers to reports/eda_stats.json. Run scripts/prepare.py first."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# ---- style (reference palette, light mode) ----
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "font.size": 13, "axes.titlesize": 14, "axes.titleweight": "bold", "lines.linewidth": 1.8,
    "legend.fontsize": 12, "xtick.labelsize": 12, "ytick.labelsize": 12, "axes.labelsize": 13,
    "legend.frameon": False, "figure.dpi": 110, "savefig.dpi": 160, "savefig.bbox": "tight",
})

LINE = {"Commerce": "West Belt", "Leeland": "West Belt", "Polk": "East Belt",
        "Telephone": "East Belt", "York": "Galveston Sub", "Lockwood": "Galveston Sub",
        "Market": "Strang Sub", "Hirsch": "industrial spur"}
# north-to-south-ish reading order used in every small-multiple grid
ORDER = ["Market", "Hirsch", "Commerce", "York", "Lockwood", "Leeland", "Polk", "Telephone"]
TEST_START = pd.Timestamp("2025-07-01")
STATS = {}


def load():
    st = pd.read_csv(PROC / "stations.csv").set_index("short")
    ep = pd.read_csv(PROC / "episodes.csv", parse_dates=["start", "end"])
    ev = pd.read_csv(PROC / "events.csv", parse_dates=["start", "end"])
    og = pd.read_csv(PROC / "outages.csv", parse_dates=["gap_start", "gap_end"])
    name2short = dict(zip(st["name"], st.index))
    for d in (ep, ev, og):
        d["s"] = d["name"].map(name2short)
    return st.loc[ORDER], ep, ev, og


# ---------------------------------------------------------------- minute grid
class Grid:
    """occ[k, m]: crossing k blocked during minute m; obs[k, m]: crossing k reporting."""

    def __init__(self, ep, og):
        self.t0 = ep["start"].min().floor("D")
        t1 = ep["end"].max().ceil("D")
        self.T = int((t1 - self.t0) / pd.Timedelta(minutes=1))
        self.occ = np.zeros((len(ORDER), self.T), bool)
        self.obs = np.zeros((len(ORDER), self.T), bool)
        self.starts, self.ends = {}, {}
        for k, s in enumerate(ORDER):
            e = ep[ep["s"] == s]
            a = self.m(e["start"]); b = np.maximum(np.ceil(self.mf(e["end"])).astype(int), a + 1)
            diff = np.zeros(self.T + 1, int)
            np.add.at(diff, a, 1); np.add.at(diff, b, -1)
            self.occ[k] = np.cumsum(diff)[:-1] > 0
            self.obs[k, a.min():b.max()] = True
            for _, r in og[og["s"] == s].iterrows():
                self.obs[k, max(self.m(r.gap_start), 0):self.m(r.gap_end)] = False
            self.starts[s], self.ends[s] = self.mf(e["start"]), self.mf(e["end"])
        self.time = self.t0 + pd.to_timedelta(np.arange(self.T), unit="min")

    def mf(self, ts):
        return ((pd.to_datetime(ts) - self.t0) / pd.Timedelta(minutes=1)).to_numpy(float)

    def m(self, ts):
        if isinstance(ts, pd.Timestamp):
            return int(np.floor((ts - self.t0) / pd.Timedelta(minutes=1)))
        return np.floor(self.mf(ts)).astype(int)


# ---------------------------------------------------------------- figures
def fig_map(st, g, min_ratio=5.0):
    osm = json.load(open(ROOT / "data" / "external" / "osm_rail_roads.json"))
    fig, ax = plt.subplots(figsize=(10, 10))
    for e in osm["elements"]:
        t = e.get("tags", {})
        if e["type"] != "way" or "geometry" not in e:
            continue
        xy = np.array([[p["lon"], p["lat"]] for p in e["geometry"]])
        if t.get("railway") == "rail":
            main = t.get("usage") in ("main", "branch")
            ax.plot(xy[:, 0], xy[:, 1], color=INK2 if main else MUTED,
                    lw=1.6 if main else 0.6, zorder=2, solid_capstyle="round")
        elif "highway" in t:
            big = t["highway"] in ("motorway", "trunk")
            ax.plot(xy[:, 0], xy[:, 1], color="#d9d7cf" if big else "#ecebe6",
                    lw=3 if big else 1.4, zorder=1)
    blocked = {s: 1440 * g.occ[k][g.obs[k]].mean() for k, s in enumerate(ORDER)}
    STATS["blocked_min_per_day"] = {s: round(v, 1) for s, v in blocked.items()}
    offs = {"Market": (12, 4), "Hirsch": (12, 4), "Commerce": (-14, 6), "York": (-14, -22),
            "Lockwood": (12, 4), "Leeland": (-14, -14), "Polk": (12, 2), "Telephone": (12, -10)}
    for s, r in st.iterrows():
        ax.scatter(r.lon, r.lat, s=24 * np.sqrt(blocked[s]) + 30, color=BLUE[4],
                   edgecolor=SURF, linewidth=2, zorder=5, alpha=0.9)
        ha = "right" if offs[s][0] < 0 else "left"
        ax.annotate(f"{s}\n{blocked[s]:.0f} min/day blocked", (r.lon, r.lat), xytext=offs[s],
                    textcoords="offset points", ha=ha, fontsize=12, color=INK, zorder=6)
    arrows = {}  # leader -> follower: (lag, ratio)
    for p in STATS["leadlag"]:
        if p["peak_ratio"] >= min_ratio:
            arrows[(p["a"], p["b"])] = (p["peak_lag_min"], p["peak_ratio"])
    # drop a->b when some a->c->b chain explains its lag (within 2 min)
    transitive = {(a, b) for (a, b), (l, _) in arrows.items()
                  for (a2, c) in arrows if a2 == a and (c, b) in arrows
                  and abs(arrows[(a, c)][0] + arrows[(c, b)][0] - l) <= 2}
    key = []
    for (a, b), (lag, ratio) in arrows.items():
        if (a, b) in transitive:
            continue
        ax.annotate("", xy=(st.loc[b, "lon"], st.loc[b, "lat"]), xytext=(st.loc[a, "lon"], st.loc[a, "lat"]),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.4,head_length=0.8", color=CAT[1],
                                    lw=1.5 + np.log(ratio), shrinkA=11, shrinkB=11,
                                    connectionstyle="arc3,rad=0.25", alpha=0.9), zorder=4)
        key.append(f"{a} → {b}: about {lag} min later")
    ax.text(0.02, 0.02, "Orange arrow: a blockage at the first crossing is\nusually followed by one at the second\n\n"
            + "\n".join(key), transform=ax.transAxes, fontsize=11.5, color=INK, va="bottom",
            bbox=dict(boxstyle="round,pad=0.6", fc=SURF, ec=GRID), zorder=7)
    ax.set_xlim(st.lon.min() - 0.02, st.lon.max() + 0.024)
    ax.set_ylim(st.lat.min() - 0.018, st.lat.max() + 0.008)
    ax.set_aspect(1 / np.cos(np.deg2rad(29.75)))
    ax.grid(False); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("The eight crossings (circle size = minutes blocked per day)", loc="left")
    ax.text(0, -0.015, "Dark grey lines: railroad tracks. Light lines: major roads. Map data: OpenStreetMap contributors.",
            transform=ax.transAxes, fontsize=10.5, color=MUTED, va="top")
    fig.savefig(FIG / "fig1_map.png"); plt.close(fig)


def fig_coverage(ep, og):
    ep = ep.assign(week=ep["start"].dt.to_period("W").dt.start_time)
    w = ep.pivot_table(index="s", columns="week", values="dur_min", aggfunc="size").reindex(ORDER)
    weeks = pd.date_range(w.columns.min(), w.columns.max(), freq="7D")
    w = w.reindex(columns=weeks) / 7
    # fraction of each week unobserved
    unobs = pd.DataFrame(0.0, index=ORDER, columns=weeks)
    first = ep.groupby("s")["start"].min(); last = ep.groupby("s")["end"].max()
    for s in ORDER:
        for i, wk in enumerate(weeks):
            lo, hi = wk, wk + pd.Timedelta(days=7)
            span = max(0, (min(hi, last[s]) - max(lo, first[s])).total_seconds())
            o = og[(og.s == s) & (og.gap_end > lo) & (og.gap_start < hi)]
            lost = sum((min(hi, r.gap_end) - max(lo, r.gap_start)).total_seconds() for r in o.itertuples())
            unobs.iloc[ORDER.index(s), i] = 1 - max(span - lost, 0) / (7 * 86400)
    v = w.where(unobs.values < 0.5)
    fig, ax = plt.subplots(figsize=(13, 4.8))
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Patch
    cmap = LinearSegmentedColormap.from_list("b", BLUE); cmap.set_bad("#e4e2dc")
    im = ax.imshow(v.values, aspect="auto", cmap=cmap, vmin=0, vmax=30, interpolation="nearest",
                   extent=[0, len(weeks), len(ORDER), 0])
    ax.set_yticks(np.arange(len(ORDER)) + 0.5); ax.set_yticklabels(ORDER)
    yr = [i for i, d in enumerate(weeks) if d.month == 1 and d.day <= 7]
    ax.set_xticks(yr); ax.set_xticklabels([weeks[i].strftime("%b %Y") for i in yr])
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, pad=0.01, fraction=0.03); cb.set_label("blockages per day")
    cb.outline.set_visible(False)
    ax.legend(handles=[Patch(color="#e4e2dc", label="no data (sensor not reporting)")],
              loc="upper left", bbox_to_anchor=(0, -0.1), fontsize=11.5)
    ax.set_title("Blockages per day at each crossing, averaged week by week", loc="left")
    fig.savefig(FIG / "fig2_coverage.png"); plt.close(fig)


def fig_duration(ev, ep, g):
    # drop events inside outage / fault windows
    ok = lambda d: g.obs[d["s"].map(ORDER.index).to_numpy(), np.clip(g.m(d["start"]), 0, g.T - 1)]
    ev, ep = ev[ok(ev)], ep[ok(ep)]
    bins = np.logspace(np.log10(0.05), np.log10(1500), 60)
    fig, axs = plt.subplots(2, 4, figsize=(15, 7.5), sharex=True)
    rows = []
    for ax, s in zip(axs.flat, ORDER):
        a = ev.loc[ev.s == s, "dur_min"].clip(lower=0.05); b = ep.loc[ep.s == s, "dur_min"].clip(lower=0.05)
        wa, wb = np.full(len(a), 100 / len(a)), np.full(len(b), 100 / len(b))  # % of events per log bin
        ax.hist(a, bins, weights=wa, histtype="step", color=MUTED, lw=1.4, label="raw records")
        ax.hist(b, bins, weights=wb, histtype="stepfilled", color=CAT[0], alpha=0.35)
        ax.hist(b, bins, weights=wb, histtype="step", color=CAT[0], lw=1.6, label="after merging fragments")
        ax.set_xscale("log"); ax.set_title(s, loc="left")
        ax.axvline(b.median(), color=INK, lw=1, ls=":")
        ax.text(0.98, 0.97, f"median {b.median():.1f} min\n(dotted line)", transform=ax.transAxes, fontsize=11,
                color=INK2, va="top", ha="right")
        rows.append({"s": s, "raw_n": len(a), "ep_n": len(b), "raw_short_frac": round((a < 1).mean(), 3),
                     "ep_short_frac": round((b < 1).mean(), 3), "ep_median": round(b.median(), 2),
                     "ep_p90": round(b.quantile(.9), 1), "ep_p99": round(b.quantile(.99), 1),
                     "ep_gt30_frac": round((b > 30).mean(), 3)})
    for ax in axs[1]:
        ax.set_xlabel("minutes blocked (log scale)")
        ax.set_xticks([0.1, 1, 10, 100, 1000]); ax.set_xticklabels(["0.1", "1", "10", "100", "1000"])
    for ax in axs[:, 0]:
        ax.set_ylabel("% of blockages")
    fig.suptitle("How long does a blockage last?", x=0.01, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=2, bbox_to_anchor=(0.99, 0.995))
    fig.savefig(FIG / "fig3_duration.png"); plt.close(fig)
    STATS["duration"] = rows


def fig_diurnal(g):
    hod = g.time.hour.to_numpy(); wkend = g.time.dayofweek.to_numpy() >= 5
    fig, axs = plt.subplots(2, 4, figsize=(15, 7.5), sharex=True, sharey=True)
    prof = {}
    for k, (ax, s) in enumerate(zip(axs.flat, ORDER)):
        o = g.obs[k]
        for flag, col, lab in ((False, CAT[0], "weekdays"), (True, CAT[1], "weekends")):
            msk = o & (wkend == flag)
            p = np.bincount(hod[msk], g.occ[k][msk], 24) / np.bincount(hod[msk], minlength=24)
            ax.plot(np.arange(24) + 0.5, 100 * p, color=col, lw=2, label=lab)
            if not flag:
                prof[s] = p
        ax.set_title(s, loc="left"); ax.set_xticks([0, 6, 12, 18, 24]); ax.set_xlim(0, 24)
        ax.set_ylim(0, None)
    for ax in axs[:, 0]:
        ax.set_ylabel("% of time blocked")
    for ax in axs[1]:
        ax.set_xlabel("hour of day")
    axs[0, 0].legend(loc="lower left")
    fig.suptitle("At what time of day are crossings blocked?", x=0.01, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(); fig.savefig(FIG / "fig4_diurnal.png"); plt.close(fig)
    STATS["weekday_blocked_pct_peak_trough"] = {
        s: (round(100 * p.max(), 1), int(p.argmax()), round(100 * p.min(), 1), int(p.argmin())) for s, p in prof.items()}


def fig_residual(ep):
    """Median remaining blockage time given the time already blocked."""
    fig, ax = plt.subplots(figsize=(11, 6))
    el = np.array([0, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120])
    ax.axvspan(0, 10, color=CAT[0], alpha=0.07, lw=0)
    ax.text(0.6, 78, "first 10 min:\nusually a\ntrain passing", ha="left", va="top", fontsize=11.5, color=INK2)
    ax.text(22, 78, "after 10 min: often a stopped or\nswitching train, expect a long wait", ha="left", va="top",
            fontsize=11.5, color=INK2)
    resid = {}
    for i, s in enumerate(ORDER):
        d = ep.loc[ep.s == s, "dur_min"].to_numpy()
        r = [np.median(d[d > e] - e) if (d > e).sum() >= 30 else np.nan for e in el]
        resid[s] = [None if np.isnan(v) else round(float(v), 1) for v in r]
        ax.plot(el, r, color=CAT[i], marker="o", ms=5, lw=1.8, label=s)
    ax.set_xlim(0, 122); ax.set_ylim(0, 80)
    ax.set_xlabel("minutes the crossing has already been blocked")
    ax.set_ylabel("typical (median) minutes still to go")
    ax.set_title("If a crossing is already blocked, how much longer will it stay blocked?", loc="left")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), title="crossing")
    fig.tight_layout(); fig.savefig(FIG / "fig5_residual.png"); plt.close(fig)
    STATS["median_residual_by_elapsed"] = {"elapsed": el.tolist(), **resid}


def xcorr(g, a, b, W=90):
    """Episode-start co-occurrence of b relative to a, lag in [-W, W] min, / baseline at |lag|>60."""
    sa, sb = np.sort(g.starts[a]), np.sort(g.starts[b])
    ka, kb = ORDER.index(a), ORDER.index(b)
    ia = np.clip(sa.astype(int), 0, g.T - 1)
    sa = sa[g.obs[ka][ia] & g.obs[kb][ia]]
    lo, hi = np.searchsorted(sb, sa - W), np.searchsorted(sb, sa + W)
    lags = np.concatenate([sb[l:h] - x for x, l, h in zip(sa, lo, hi)]) if len(sa) else np.array([])
    h = np.histogram(lags, np.arange(-W, W + 2) - 0.5)[0].astype(float)
    lag = np.arange(-W, W + 1)
    base = h[np.abs(lag) > 60].mean()
    return lag, h / base if base > 0 else h * np.nan, len(sa)


def fig_leadlag(g, n_show=6):
    peaks, curves = [], {}
    for i, a in enumerate(ORDER):
        for b in ORDER[i + 1:]:
            lag, r, na = xcorr(g, a, b)
            core = np.abs(lag) <= 30
            pk = int(lag[core][np.nanargmax(r[core])]); pv = float(np.nanmax(r[core]))
            rev = float(np.nanmax(r[core & (np.sign(lag) == -np.sign(pk))]))
            if pk < 0:  # orient every pair leader -> follower
                a2, b2, lag2, r2, pk = b, a, -lag[::-1], r[::-1], -pk
            else:
                a2, b2, lag2, r2 = a, b, lag, r
            curves[(a2, b2)] = (lag2, r2)
            peaks.append({"a": a2, "b": b2, "same_line": LINE[a] == LINE[b], "peak_ratio": round(pv, 2),
                          "peak_lag_min": pk, "reverse_peak_ratio": round(rev, 2), "n_a": na})
    peaks.sort(key=lambda d: -d["peak_ratio"])
    STATS["leadlag"] = peaks
    # strongest pairs, plus the two best-observed unlinked pairs for contrast
    show = peaks[:n_show] + sorted(peaks[n_show:], key=lambda d: -d["n_a"])[:2]
    fig, axs = plt.subplots(2, 4, figsize=(15, 7.5), sharex=True)
    for ax, p in zip(axs.flat, show):
        lag, r = curves[(p["a"], p["b"])]
        linked = p["peak_ratio"] >= 5
        col = CAT[1] if linked else CAT[0]
        ax.fill_between(lag, 1, r, color=col, alpha=0.3, lw=0)
        ax.plot(lag, r, color=col, lw=1.4)
        ax.axhline(1, color=INK, lw=0.9, ls="--")
        ax.axvline(0, color=MUTED, lw=0.8)
        ax.set_xlim(-45, 45); ax.set_xticks([-40, -20, 0, 20, 40]); ax.set_ylim(0, max(3, np.nanmax(r) * 1.12))
        ax.set_title(f"{p['a']} → {p['b']}" if linked else f"{p['a']} and {p['b']} (unlinked)", loc="left")
        if linked:
            ax.text(p["peak_lag_min"] + 3, p["peak_ratio"] * 0.97, f"{p['peak_ratio']:.0f}x at\n+{p['peak_lag_min']} min",
                    fontsize=11, va="top", color=INK)
    for ax in axs[1]:
        ax.set_xlabel(f"minutes after a blockage starts\nat the first crossing")
    for ax in axs[:, 0]:
        ax.set_ylabel("times more likely than chance")
    axs[0, 0].text(-43, 1.4, "chance level", fontsize=10.5, color=INK2)
    fig.suptitle("After a blockage starts at one crossing, does one soon start at another?",
                 x=0.01, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(); fig.savefig(FIG / "fig6_leadlag.png"); plt.close(fig)


def fig_concurrency(g):
    allobs = g.obs.all(0)
    k = g.occ[:, allobs].sum(0)
    hod = g.time.hour.to_numpy()[allobs]
    STATS["all8_observed_days"] = round(allobs.sum() / 1440, 1)
    STATS["concurrency_pct"] = {int(c): round(100 * (k == c).mean(), 2) for c in range(0, 6)}
    fig, axs = plt.subplots(1, 2, figsize=(15, 5.5), gridspec_kw={"width_ratios": [1, 1.4]})
    pct = [100 * (k == c).mean() for c in range(6)]
    axs[0].bar(range(6), pct, color=CAT[0], width=0.7)
    for c, p in enumerate(pct):
        axs[0].text(c, p + 1, f"{p:.1f}%", ha="center", fontsize=11.5, color=INK2)
    axs[0].set_xlabel("number of crossings blocked at the same time"); axs[0].set_ylabel("% of all minutes")
    axs[0].set_title("(a) How many crossings are blocked at once?", loc="left")
    for c, col in zip((1, 2, 3), (BLUE[2], BLUE[4], BLUE[6])):
        p = np.bincount(hod, k >= c, 24) / np.bincount(hod, minlength=24)
        axs[1].plot(np.arange(24) + 0.5, 100 * p, color=col, lw=2.2, label=f"at least {c} blocked")
    axs[1].set_xlabel("hour of day"); axs[1].set_ylabel("% of minutes"); axs[1].set_xlim(0, 24)
    axs[1].set_xticks([0, 6, 12, 18, 24]); axs[1].legend(loc="center right")
    axs[1].set_title("(b) The same, by hour of day", loc="left")
    fig.tight_layout(); fig.savefig(FIG / "fig7_concurrency.png"); plt.close(fig)
    # pairwise co-blockage lift P(both)/P(a)P(b) on jointly observed minutes
    lift = np.full((len(ORDER),) * 2, np.nan)
    for i in range(len(ORDER)):
        for j in range(len(ORDER)):
            if i != j:
                m = g.obs[i] & g.obs[j]
                pa, pb = g.occ[i][m].mean(), g.occ[j][m].mean()
                lift[i, j] = (g.occ[i][m] & g.occ[j][m]).mean() / (pa * pb)
    STATS["coblock_lift"] = pd.DataFrame(lift, ORDER, ORDER).round(2).to_dict()


# ---------------------------------------------------------------- predictability
def features(g, step=5):
    """One row per (crossing, minute t) sampled every `step` min where the crossing reports."""
    t = np.arange(0, g.T, step)
    how = (g.time.dayofweek.to_numpy() * 24 + g.time.hour.to_numpy())
    state = {}
    for k, s in enumerate(ORDER):
        st, en = g.starts[s], g.ends[s]
        o = np.argsort(st); st, en = st[o], en[o]
        idx = np.searchsorted(st, t, side="right") - 1
        valid = idx >= 0
        last_st = np.where(valid, st[np.clip(idx, 0, None)], np.nan)
        last_en = np.where(valid, en[np.clip(idx, 0, None)], np.nan)
        blocked = g.occ[k][t]
        state[s] = dict(blocked=blocked.astype(float),
                        elapsed=np.where(blocked, t - last_st, 0.0),
                        since_end=np.where(~blocked, np.minimum(t - last_en, 1440), 0.0),
                        since_start=np.minimum(t - last_st, 1440))
        for key in state[s]:
            state[s][key] = np.where(g.obs[k][t], state[s][key], np.nan)
    return t, how, state


def fig_predict(g):
    import xgboost as xgb
    t, how, state = features(g)
    tt = g.time[t]
    train = tt < TEST_START
    H = [2, 5, 10, 15, 30, 60, 120]
    res = []
    for h in H:
        th = t + h
        keep_t = th < g.T
        Xs, ys, clim, sid, split = [], [], [], [], []
        for k, s in enumerate(ORDER):
            ok = keep_t & g.obs[k][np.clip(t, 0, g.T - 1)] & g.obs[k][np.clip(th, 0, g.T - 1)]
            y = g.occ[k][th[ok]].astype(float)
            # hour-of-week climatology of the target, fitted on the training period only
            hw = how[th[ok]]; tr = train[ok]
            c = np.bincount(hw[tr], y[tr], 168) / np.maximum(np.bincount(hw[tr], minlength=168), 1)
            own = np.column_stack([state[s][f][ok] for f in ("blocked", "elapsed", "since_end", "since_start")])
            nb = np.column_stack([state[o][f][ok] for o in ORDER if o != s for f in ("blocked", "since_start")])
            Xs.append((own, nb, c[hw], hw)); ys.append(y); sid.append(np.full(ok.sum(), k)); split.append(tr)
        y = np.concatenate(ys); tr = np.concatenate(split); sid = np.concatenate(sid)
        cl = np.concatenate([x[2] for x in Xs])
        oh = np.eye(len(ORDER))[sid]
        base = np.column_stack([np.concatenate([x[0] for x in Xs]), cl, oh,
                                np.concatenate([x[3] for x in Xs]) % 24])
        # neighbour columns are ordered by ORDER-minus-self, so realign to absolute crossing slots
        nbabs = np.full((len(y), 2 * len(ORDER)), np.nan); r0 = 0
        for k, x in enumerate(Xs):
            others = [j for j in range(len(ORDER)) if j != k]
            for c_i, j in enumerate(others):
                nbabs[r0:r0 + len(x[1]), 2 * j:2 * j + 2] = x[1][:, 2 * c_i:2 * c_i + 2]
            r0 += len(x[1])
        full = np.column_stack([base, nbabs])
        te = ~tr

        def bss(p, mask=te):
            ref = np.mean((cl[mask] - y[mask]) ** 2)
            return 1 - np.mean((p[mask] - y[mask]) ** 2) / ref

        persist = np.concatenate([x[0][:, 0] for x in Xs])
        out = {"h": h, "persistence": bss(persist)}
        for name, X in (("own", base), ("own+neighbours", full)):
            m = xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
                                  tree_method="hist", n_jobs=32, verbosity=0)
            m.fit(X[tr], y[tr])
            p = m.predict_proba(X)[:, 1]
            out[name] = bss(p)
            out[name + "_by_station"] = {s: round(bss(p, te & (sid == k)), 3) for k, s in enumerate(ORDER)
                                         if (te & (sid == k)).sum() > 1000}
        out["n_test"] = int(te.sum()); out["base_rate_test"] = round(float(y[te].mean()), 4)
        res.append(out)
        print(f"h={h:4d}  persist {out['persistence']:.3f}  own {out['own']:.3f}  +nb {out['own+neighbours']:.3f}")
    STATS["predict"] = res
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for key, col, lab in (("own+neighbours", CAT[1], "model: this crossing + the other seven"),
                          ("own", CAT[0], "model: this crossing only"),
                          ("persistence", MUTED, "guess: \"same as now\"")):
        ax.plot(H, [r[key] for r in res], marker="o", ms=6, lw=2.2, color=col, label=lab)
    ax.axhline(0, color=INK, lw=0.8)
    ax.text(H[0], -0.1, "0 = no better than the average for that hour of the week", ha="left", fontsize=11.5,
            color=INK2)
    ax.set_xscale("log"); ax.set_xticks(H); ax.set_xticklabels(H)
    ax.set_ylim(-0.6, 1)
    ax.set_xlabel("how far ahead we predict (minutes)")
    ax.set_ylabel("forecast skill (Brier skill score)\n1 = perfect,  0 = no better than average")
    ax.set_title("How far ahead can we predict whether a crossing will be blocked?", loc="left")
    ax.legend(loc="upper right")
    fig.tight_layout(); fig.savefig(FIG / "fig8_predict.png"); plt.close(fig)


def main():
    st, ep, ev, og = load()
    g = Grid(ep, og)
    STATS["n_raw_events"] = int(len(ev)); STATS["n_episodes"] = int(len(ep))
    STATS["observed_days"] = {s: round(g.obs[k].sum() / 1440, 1) for k, s in enumerate(ORDER)}
    STATS["span"] = [str(ep.start.min()), str(ep.end.max())]
    for f in (lambda: fig_leadlag(g), lambda: fig_map(st, g), lambda: fig_coverage(ep, og),
              lambda: fig_duration(ev, ep, g), lambda: fig_diurnal(g), lambda: fig_residual(ep),
              lambda: fig_concurrency(g), lambda: fig_predict(g)):
        f()
    json.dump(STATS, open(ROOT / "reports" / "eda_stats.json", "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in STATS.items() if k not in ("leadlag", "predict", "coblock_lift")},
                     indent=1, default=str))
    print(pd.DataFrame(STATS["leadlag"]).head(15).to_string())
    print(pd.DataFrame(STATS["coblock_lift"]).to_string())


if __name__ == "__main__":
    main()

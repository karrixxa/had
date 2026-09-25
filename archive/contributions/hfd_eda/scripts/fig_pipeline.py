"""Pipeline overview diagram for the report."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import sys; sys.path.insert(0, "scripts")
from eda import CAT, BLUE, INK, INK2, SURF, FIG

stages = [
    ("Data sources", ["TRAINFO export: 67 sensor\nIDs, 285,263 records", "Eight study crossings:\n153,141 records",
                      "OpenStreetMap\nrail lines", "Fire Department delay\nreports (context)"], BLUE[0]),
    ("Data wrangling", ["Remove duplicates,\nfix negative durations", "Join records up to 2 min\napart into episodes",
                        "Flag outages (> 24 h\nsilent) and fault days", "Minute-by-minute\nblocked / clear grid"], BLUE[1]),
    ("Exploration", ["Duration and\nremaining-wait curves", "Daily, weekly and\nlong-term patterns",
                     "Lead-lag links\nbetween crossings", "Class balance and\ndrift over time"], "#fbe3d6"),
    ("Modeling", ["Baselines: persistence,\ntime-of-week rate", "Gradient-boosted trees\n(own + upstream)",
                  "Sequence / graph\nmodels (stretch goal)", "Time-ordered train /\nvalidation / test split"], "#d7f0e5"),
    ("Evaluation", ["Brier skill, PR-AUC,\nprecision / recall", "Calibration", "Per-crossing\npredictability",
                    "Feature importance"], "#fdf0c8"),
]
fig, ax = plt.subplots(figsize=(16, 7.2)); ax.set_xlim(0, 5); ax.set_ylim(0, 5.3); ax.axis("off")
for i, (title, items, col) in enumerate(stages):
    x = i + 0.06
    ax.add_patch(FancyBboxPatch((x, 0.1), 0.88, 4.7, boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc=col, ec="none", alpha=0.7))
    ax.text(x + 0.44, 4.95, title, ha="center", va="center", fontsize=15, fontweight="bold", color=INK)
    for j, it in enumerate(items):
        y = 4.1 - j * 1.1
        ax.add_patch(FancyBboxPatch((x + 0.05, y - 0.4), 0.78, 0.8, boxstyle="round,pad=0.01,rounding_size=0.04",
                                    fc=SURF, ec=INK2, lw=0.8))
        ax.text(x + 0.44, y, it, ha="center", va="center", fontsize=11.5, color=INK)
    if i < len(stages) - 1:
        ax.annotate("", xy=(i + 1.07, 2.45), xytext=(i + 0.93, 2.45),
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=2))
fig.savefig(FIG / "fig0_pipeline.png"); plt.close(fig)

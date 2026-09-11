"""
Generates the three data-driven figures for the report from the exact
numbers reported in the manuscript (docs/paper_draft.md, sections 4.1-4.3).
Palette: validated categorical slots 1 (blue, #2a78d6) and 2 (orange,
#eb6834) from the project's data-viz reference palette -- an adjacent,
colorblind-safe pair (worst adjacent CVD Delta E 9.1, normal-vision 19.6).

Run: python3 make_figures.py
Outputs: fig_reliability.pdf, fig_confound_b2.pdf, fig_confound_scheduler.pdf
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 9,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "axes.axisbelow": True,
        "svg.fonttype": "none",
    }
)


def style_axis(ax, ylabel, zero_line=False):
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(axis="both", length=0)
    ax.set_ylabel(ylabel, color=INK)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=6))
    if zero_line:
        ax.axhline(0, color=BASELINE, linewidth=1.0, zorder=1)


# ---------------------------------------------------------------------------
# Figure 2 (Sec. 4.1): reliability profile, common-denominator configuration.
# Platform-tuned values are omitted from the figure because Sec. 4.1 reports
# they are nearly identical within each system/workload pair; the full
# eight-row breakdown remains in Table 1 (text).
# ---------------------------------------------------------------------------
groups = ["A, disaster-\nresponse", "A, supply-\nchain", "B, disaster-\nresponse", "B, supply-\nchain"]
invalid_rate = [64.8, 59.8, 48.9, 56.6]
semantic_valid_rate = [35.2, 40.2, 51.1, 43.4]

fig, ax = plt.subplots(figsize=(5.5, 3.2), dpi=300)
x = range(len(groups))
width = 0.32
b1 = ax.bar([i - width / 2 for i in x], invalid_rate, width, color=BLUE, label="Invalid after repair", zorder=3)
b2 = ax.bar([i + width / 2 for i in x], semantic_valid_rate, width, color=ORANGE, label="Semantic-valid", zorder=3)

for bars in (b1, b2):
    for rect in bars:
        h = rect.get_height()
        ax.annotate(
            f"{h:.1f}",
            xy=(rect.get_x() + rect.get_width() / 2, h),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.5,
            color=INK,
        )

ax.set_xticks(list(x))
ax.set_xticklabels(groups)
ax.set_ylim(0, 78)
style_axis(ax, "Share of steps (%)")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2, fontsize=8)
fig.tight_layout()
fig.savefig("fig_reliability.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------------------
# Figure 3 (Sec. 4.2): three-stage confound reversal for the platform-tuned
# vs. common-denominator serving-configuration comparison, faceted by system.
# ---------------------------------------------------------------------------
stages_b2 = ["Original\n(low load)", "Real load,\nuncorrected\nconfig.", "Real load,\ncorrected\nconfig."]
data_b2 = {
    "A": {"disaster-response": [4.6, -18.2, 1.6], "supply-chain": [59.7, -21.4, 0.6]},
    "B": {"disaster-response": [-6.6, -22.0, 15.1], "supply-chain": [10.9, -15.1, 19.1]},
}

fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), dpi=300, sharey=True)
for ax, system in zip(axes, ("A", "B")):
    xs = range(len(stages_b2))
    end_ys = {w: data_b2[system][w][-1] for w in ("disaster-response", "supply-chain")}
    # When the two end points sit close together (as on System A), stagger the
    # labels vertically so they do not overlap; otherwise keep them centered.
    close = abs(end_ys["disaster-response"] - end_ys["supply-chain"]) < 4.0
    label_dy = {"disaster-response": 7, "supply-chain": -7} if close else {"disaster-response": 0, "supply-chain": 0}
    for workload, color, marker in (("disaster-response", BLUE, "o"), ("supply-chain", ORANGE, "s")):
        ys = data_b2[system][workload]
        ax.plot(xs, ys, color=color, marker=marker, markersize=5, linewidth=2, zorder=3, label=workload)
        ax.annotate(
            f"{ys[-1]:+.1f}%",
            xy=(xs[-1], ys[-1]),
            xytext=(6, label_dy[workload]),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=8,
            color=color,
        )
    ax.set_xticks(list(xs))
    ax.set_xticklabels(stages_b2, fontsize=7.8)
    ax.set_xlim(-0.3, len(stages_b2) - 0.3 + 0.7)
    ax.set_title(f"System {system} ({'AMD' if system == 'A' else 'NVIDIA'})", fontsize=9.5)
    style_axis(ax, "Relative improvement (%)" if system == "A" else "", zero_line=True)

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.06), ncol=2, frameon=False, fontsize=8.5)
fig.tight_layout()
fig.savefig("fig_confound_b2.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------------------
# Figure 4 (Sec. 4.3): four-stage confound reversal for the scheduling
# decision gate (Full vs. Causal-Order-Only relative improvement).
# ---------------------------------------------------------------------------
stages_sched = [
    "Original\n(low load)",
    "Real load,\nuncorrected",
    "Real load,\nbatch-cap\nfixed",
    "Real load,\nboth fixed",
]
# The first stage is reported only qualitatively in the manuscript ("tied" /
# overlapping bands) with no exact point estimate, unlike the other three
# stages, which are real measured percentages. It is plotted at the zero
# baseline as an explicit placeholder for "no distinguishing effect", drawn
# as a hollow marker with a dotted connecting segment to keep it visually
# distinct from the three measured points -- never claimed as a measured value.
data_sched = {"A": [0.0, -71.6, -66.1, 1.1], "B": [0.0, -73.2, -63.8, -0.3]}

fig, ax = plt.subplots(figsize=(5.8, 3.4), dpi=300)
xs = range(len(stages_sched))
for system, color, marker in (("A", BLUE, "o"), ("B", ORANGE, "s")):
    ys = data_sched[system]
    label = f"System {system} ({'AMD' if system == 'A' else 'NVIDIA'})"
    # Dotted, lighter segment into the qualitative first stage; solid for the
    # three measured stages.
    ax.plot(xs[:2], ys[:2], color=color, linewidth=1.4, linestyle=(0, (2, 2)), zorder=2)
    ax.plot(xs[1:], ys[1:], color=color, linewidth=2, zorder=3, label=label)
    ax.plot(xs[1:], ys[1:], color=color, marker=marker, markersize=5, linestyle="none", zorder=3)
    ax.plot(
        xs[0],
        ys[0],
        marker=marker,
        markersize=5,
        markerfacecolor="white",
        markeredgecolor=color,
        markeredgewidth=1.3,
        linestyle="none",
        zorder=3,
    )
    ax.annotate(
        f"{ys[-1]:+.1f}%",
        xy=(xs[-1], ys[-1]),
        xytext=(6, 4 if system == "A" else -10),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=8,
        color=color,
    )

ax.annotate(
    "tied\n(no point estimate reported)",
    xy=(0, 0),
    xytext=(0, 14),
    textcoords="offset points",
    ha="center",
    va="bottom",
    fontsize=6.8,
    color=MUTED,
    style="italic",
)
ax.set_xticks(list(xs))
ax.set_xticklabels(stages_sched, fontsize=8)
ax.set_xlim(-0.3, len(stages_sched) - 0.3 + 0.7)
style_axis(ax, "Relative improvement of Full vs.\nCausal-Order-Only (%)", zero_line=True)
ax.legend(frameon=False, loc="lower right", fontsize=8.5)
fig.tight_layout()
fig.savefig("fig_confound_scheduler.pdf", bbox_inches="tight")
plt.close(fig)

print("wrote fig_reliability.pdf, fig_confound_b2.pdf, fig_confound_scheduler.pdf")

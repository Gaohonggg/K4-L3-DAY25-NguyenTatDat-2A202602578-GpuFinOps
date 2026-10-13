"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly") -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    pct_label = f"{pct:.2f}".rstrip("0").rstrip(".")
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}",
        "",
        f"**Baseline spend:** ${baseline_usd:,.2f}",
        "",
        f"**Optimized spend:** ${optimized_usd:,.2f}",
        "",
        f"**Projected savings:** ${savings:,.2f}  (**{pct_label}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.2f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cleanest region: {sustainability.get('best_region', 'n/a')}",
        ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, baseline_usd: float | None = None) -> str:
    """Write a cumulative waterfall; without baseline start from total savings."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    baseline = baseline_usd if baseline_usd is not None else sum(levers.values())
    names = ["Baseline"] + list(levers) + ["Optimized"]
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.bar(0, baseline, color="#2e548a")
    ax.annotate(f"${baseline:,.2f}", (0, baseline), xytext=(0, 8),
                textcoords="offset points", ha="center", fontsize=9)
    remaining = baseline
    for i, amount in enumerate(levers.values(), 1):
        after = remaining - amount
        ax.plot([i - 0.6, i + 0.4], [remaining, remaining], color="#999999", linewidth=0.8)
        ax.bar(i, amount, bottom=after, color="#27866b")
        if not amount:
            ax.plot(i, after, marker="_", color="#27866b", markersize=24)
        label = f"-${amount:,.2f}" if amount else "$0\nnot added"
        ax.annotate(label, (i, remaining), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=9)
        remaining = after
    ax.bar(len(names) - 1, remaining, color="#2e548a")
    ax.annotate(f"${remaining:,.2f}", (len(names) - 1, remaining), xytext=(0, 8),
                textcoords="offset points", ha="center", fontsize=9)
    ax.set_xticks(range(len(names)), names)
    ax.set_ylabel("USD / 30-day recurring scenario")
    ax.set_title("Baseline to optimized spend — savings counted once")
    ax.set_ylim(0, baseline * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path

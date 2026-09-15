# -*- coding: utf-8 -*-
"""
生成 Fig 2：三种治疗方式的逐年构成比。

输出 outputs/figures/fig2_trend.{pdf,png}

**为什么画构成比而不是异物类型趋势**：后者与作者已投稿的磁性异物论文重复，
期刊不允许同一图表在两文发表。本图落点在治疗决策本身，与本文主题一致，
且与该文无重叠。

**为什么手术放在最下面**：100% 堆积图中只有最底层的基线是固定的，其厚度可直接读出。
手术占比是本文最关心的量（也是变化最剧烈的：6.4%–32.0%），故置于底层；
观察置于顶层。这是为可读性作的刻意选择，图注中已说明。

数字从 outputs/cohort.csv 实时读取，不硬编码。
"""
import os

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# 与 Fig 1、ROC/校准/DCA 同一套配色；已通过色盲分辨度与对比度校验
COLORS = {"手术": "#BE3241", "内镜": "#0A7EA4", "观察": "#5C8A1E"}
EN = {"手术": "Surgery", "内镜": "Endoscopy", "观察": "Observation"}
ORDER = ["手术", "内镜", "观察"]          # 自下而上
INK = "#15232A"
MUTED = "#5A6B72"
GRID = "#D8E1E2"
SURFACE = "white"
PARTIAL_YEAR = 2026                       # 仅含 1–6 月


def build():
    os.makedirs("outputs/figures", exist_ok=True)
    d = pd.read_csv("outputs/cohort.csv")
    counts = pd.crosstab(d["admit_year"], d["label_name"])[ORDER]
    pct = counts.div(counts.sum(axis=1), axis=0) * 100
    years = list(counts.index)
    n_per_year = counts.sum(axis=1)

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(7.4, 4.3))

    # 网格置于柱后且淡化，不与数据争视线
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, lw=0.7)
    ax.xaxis.grid(False)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    bottom = pd.Series(0.0, index=counts.index)
    for key in ORDER:
        vals = pct[key]
        ax.bar(years, vals, bottom=bottom, width=0.72,
               color=COLORS[key], edgecolor=SURFACE, linewidth=1.4, zorder=2)
        # 段内直标：仅在高度足够时标，避免拥挤
        for x, v, b in zip(years, vals, bottom):
            if v >= 7.5:
                ax.text(x, b + v / 2, f"{v:.0f}", ha="center", va="center",
                        fontsize=7.6, color=SURFACE, fontweight="bold", zorder=3)
        bottom = bottom + vals

    for x, n in zip(years, n_per_year):
        ax.text(x, 101.5, f"n={n}", ha="center", va="bottom",
                fontsize=7.2, color=MUTED)

    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0", "25", "50", "75", "100"])
    ax.set_ylabel("Proportion of admissions (%)", color=INK)
    ax.set_xticks(years)
    ax.set_xticklabels([f"{y}*" if y == PARTIAL_YEAR else str(y) for y in years],
                       color=INK)
    ax.tick_params(colors=MUTED, length=0)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(INK)

    handles = [Patch(facecolor=COLORS[k], edgecolor=SURFACE, label=EN[k])
               for k in reversed(ORDER)]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.28),
              ncol=3, frameon=False, fontsize=8.5)

    ax.text(0, -0.40, f"*{PARTIAL_YEAR} includes January to June only.",
            transform=ax.transAxes, fontsize=7.4, color=MUTED)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"outputs/figures/fig2_trend.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    print("已生成 outputs/figures/fig2_trend.{pdf,png}")
    print("\n构成比(%)：")
    print(pct.round(1).to_string())
    print(f"\n观察 {pct['观察'].iloc[0]:.1f}% -> {pct['观察'].iloc[-1]:.1f}%"
          f"　内镜 {pct['内镜'].iloc[0]:.1f}% -> {pct['内镜'].iloc[-1]:.1f}%"
          f"　手术峰值 {pct['手术'].max():.1f}%（{pct['手术'].idxmax()}）")


if __name__ == "__main__":
    build()

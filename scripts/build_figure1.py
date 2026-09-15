# -*- coding: utf-8 -*-
"""
生成 Fig 1 研究流程图（TRIPOD / STROBE 格式）。

输出 outputs/figures/fig1_flow.{pdf,png}
PDF 为矢量格式，多数期刊要求；PNG 供预览。

所有数字从 outputs/cohort.csv 实时读取，不硬编码——
队列定义一旦改动，重跑即同步，不会出现图与正文对不上的情况。
"""
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

INK = "#15232A"
RULE = "#6B7F84"
COLORS = {"观察": "#5C8A1E", "内镜": "#0A7EA4", "手术": "#BE3241"}
EN = {"观察": "Observation", "内镜": "Endoscopy", "手术": "Surgery"}


def numbers():
    d = pd.read_csv("outputs/cohort.csv")
    raw = pd.read_excel("10年消化道异物原始数据.xlsx", sheet_name="病案首页基本信息")
    dev = d["admit_year"] <= 2023
    counts = d["label_name"].value_counts()
    return {
        "raw_adm": len(raw),
        "excluded": len(raw) - len(d),
        "n": len(d),
        "children": int(d["科研患者编号"].nunique()),
        "classes": {k: int(counts[k]) for k in ("观察", "内镜", "手术")},
        "dev_n": int(dev.sum()),
        "dev_split": np.bincount(d.loc[dev, "label"], minlength=3).tolist(),
        "val_n": int((~dev).sum()),
        "val_split": np.bincount(d.loc[~dev, "label"], minlength=3).tolist(),
        "xray": int(d["has_xray"].sum()),
        "labs": int(d["lab_predecision"].sum()),
        "declined": int(d["family_declined"].sum()),
    }


def box(ax, x, y, w, h, lines, edge=RULE, face="white", bold_first=True, size=8.2):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0.008,rounding_size=0.012",
                                linewidth=1.0, edgecolor=edge, facecolor=face))
    n = len(lines)
    for i, text in enumerate(lines):
        ax.text(x, y + h / 2 - h * (i + 0.62) / n, text, ha="center", va="center",
                fontsize=size, color=INK,
                fontweight="bold" if (i == 0 and bold_first) else "normal")


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=9, linewidth=1.0, color=RULE,
                                 shrinkA=0, shrinkB=0))


def build():
    os.makedirs("outputs/figures", exist_ok=True)
    v = numbers()
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, ax = plt.subplots(figsize=(7.4, 9.0))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # 主列居左，侧注居右，两者之间留出空档，避免线穿过框
    CX, CW = 0.355, 0.50          # 主列中心与宽度 -> 0.105 ~ 0.605
    SX, SW = 0.815, 0.325         # 侧注中心与宽度 -> 0.6525 ~ 0.9775

    def tee(y, y_to=None):
        """自主列竖线向右分出一条横线到侧注；横线走在两框之间的空档。"""
        ax.plot([CX, SX - SW / 2], [y, y], color=RULE, lw=1.0)
        arrow(ax, SX - SW / 2 - 0.001, y, SX - SW / 2 + 0.004, y)

    y1, h1 = 0.945, 0.080
    box(ax, CX, y1, CW, h1, [
        "Admissions for gastrointestinal foreign body ingestion",
        "Tertiary paediatric centre, July 2016 – June 2026",
        f"n = {v['raw_adm']}"], size=8.0)

    y2, h2 = 0.818, 0.062
    ax.plot([CX, CX], [y1 - h1 / 2, y2 + h2 / 2 + 0.004], color=RULE, lw=1.0)
    arrow(ax, CX, y2 + h2 / 2 + 0.010, CX, y2 + h2 / 2 + 0.002)
    tee(0.877)
    box(ax, SX, 0.877, SW, 0.070, [
        f"Excluded (n = {v['excluded']})",
        "Only a procedure unrelated to foreign",
        "body ingestion was recorded"], size=7.4)

    box(ax, CX, y2, CW, h2, [
        "Analysis cohort",
        f"{v['n']} admissions in {v['children']} children"], size=8.0)

    y3, h3 = 0.688, 0.048
    ax.plot([CX, CX], [y2 - h2 / 2, y3 + h3 / 2 + 0.004], color=RULE, lw=1.0)
    arrow(ax, CX, y3 + h3 / 2 + 0.010, CX, y3 + h3 / 2 + 0.002)
    tee(0.755)
    box(ax, SX, 0.752, SW, 0.100, [
        "Predictors available before the decision",
        f"Radiograph  {v['xray']}",
        f"Laboratory  {v['labs']}",
        "Investigations obtained after the",
        "procedure began were excluded"], size=7.4)

    box(ax, CX, y3, CW, h3, ["Management delivered"], size=8.0)

    # 三个类别框：等距且留缝
    # 留缝须大于 2×pad（pad 是往框外扩的），否则相邻框会贴在一起
    bw, step = 0.145, 0.200
    xs = [CX - step, CX, CX + step]
    ytop, yc, hc = 0.640, 0.590, 0.070
    ax.plot([CX, CX], [y3 - h3 / 2, ytop], color=RULE, lw=1.0)
    ax.plot([xs[0], xs[2]], [ytop, ytop], color=RULE, lw=1.0)
    for x, key in zip(xs, ("观察", "内镜", "手术")):
        arrow(ax, x, ytop, x, yc + hc / 2 + 0.002)
        n = v["classes"][key]
        box(ax, x, yc, bw, hc, [EN[key], f"n = {n} ({n / v['n'] * 100:.1f}%)"],
            edge=COLORS[key], size=8.0)

    ybot = yc - hc / 2
    ymerge = 0.505
    for x in xs:
        ax.plot([x, x], [ybot, ymerge], color=RULE, lw=1.0)
    ax.plot([xs[0], xs[2]], [ymerge, ymerge], color=RULE, lw=1.0)

    y4, h4 = 0.448, 0.046
    arrow(ax, CX, ymerge, CX, y4 + h4 / 2 + 0.002)
    box(ax, CX, y4, 0.34, h4, ["Split by year of admission"], size=8.0)

    ysplit = 0.398
    ax.plot([CX, CX], [y4 - h4 / 2, ysplit], color=RULE, lw=1.0)
    dx = [CX - 0.165, CX + 0.165]
    ax.plot([dx[0], dx[1]], [ysplit, ysplit], color=RULE, lw=1.0)
    for x, title, period, n, split in [
            (dx[0], "Model development", "2016 – 2023", v["dev_n"], v["dev_split"]),
            (dx[1], "Temporal validation", "2024 – 2026", v["val_n"], v["val_split"])]:
        arrow(ax, x, ysplit, x, 0.352)
        box(ax, x, 0.290, 0.270, 0.120, [
            title, period, f"n = {n}",
            "Observation / Endoscopy / Surgery",
            f"{split[0]} / {split[1]} / {split[2]}"], size=7.6)

    ax.text(0.5, 0.145,
            f"Ten admissions in the observation class carry the coded diagnosis "
            f"\u201cprocedure not performed for reasons\nattributable to the family\u201d; "
            "these were excluded in a prespecified sensitivity analysis.",
            ha="center", va="center", fontsize=7.4, color=INK, style="italic")
    ax.text(0.5, 0.088,
            "Predictors were restricted to information available before the treatment decision, "
            "verified by comparing\neach investigation's timestamp against the recorded start of "
            "the procedure in the anaesthetic record.",
            ha="center", va="center", fontsize=7.4, color="#4A5D64")

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"outputs/figures/fig1_flow.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("已生成 outputs/figures/fig1_flow.{pdf,png}")


if __name__ == "__main__":
    build()

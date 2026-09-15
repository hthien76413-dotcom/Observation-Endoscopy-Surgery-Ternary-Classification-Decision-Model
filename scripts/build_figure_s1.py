# -*- coding: utf-8 -*-
"""
补充图 S1：多重插补前后的分布比较。

用法:
    python3 scripts/build_figure_s1.py [--imputations 20]

输出:
    outputs/figures/figS1_imputation.{pdf,png}

**读这张图的方式与一般插补诊断相反。** 通常「插补值分布与观测值一致」被当作
好现象。本队列不是：缺失本身携带治疗信息（内镜组 85% 没有 CRP——快速送手术室，
来不及做化验），属非随机缺失。若插补值分布与观测值严丝合缝，反而说明插补模型
没有利用结局与其他协变量的信息，只是把观测分布复制了一遍。

所以本图要看的是：① 插补值落在临床可能的范围内（没有外推出负白蛋白、40℃ 体温）；
② 偏移方向讲得通（缺化验的多是快速送内镜者，病情较轻，插补出的白细胞应偏低）。
图注须把这一条写明，否则审稿人会按常规读法质疑「分布不一致」。

连续变量画密度叠加，二分类变量画阳性比例的点图（实心为观测、空心为插补，
横线为 m 份插补之间的范围）。
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTDIR = "outputs/figures"
COHORT = "outputs/cohort.csv"

OBS_COLOR = "#2F4858"      # 观测值：深靛，与三色治疗调色板不冲突
IMP_COLOR = "#C1663B"      # 插补值：赭橙
BINARY_MAX_LEVELS = 3

# 变量名转英文——图件进入英文稿件，且 matplotlib 无 CJK 字体
PRETTY = {
    "lab_wbc": "White cell count", "lab_neut_pct": "Neutrophil %",
    "lab_alb": "Albumin", "log_ingest_hours": "log(h since ingestion)",
    "temp_c": "Temperature", "weight_kg": "Weight",
    "xray_radiopaque": "Radio-opaque on X-ray", "loc_esophagus": "Oesophagus",
    "loc_stomach": "Stomach", "loc_duodenum": "Duodenum",
    "loc_smallbowel": "Small bowel", "loc_colorectal": "Colorectal",
}


def nice(name):
    return PRETTY.get(name, name.replace("_", " "))


def split_columns(X, cols):
    """按取值个数分连续 / 二分类——插补后二分类会变成小数，须按原始列判断。"""
    cont, binary = [], []
    for c in cols:
        (binary if X[c].dropna().nunique() <= BINARY_MAX_LEVELS else cont).append(c)
    return cont, binary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imputations", type=int, default=20)
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    from definitive_analysis import SEED, feature_columns, impute

    if not os.path.exists(COHORT):
        sys.exit(f"缺少 {COHORT}——先跑 python3 scripts/build_cohort.py")

    df = pd.read_csv(COHORT)
    feats = feature_columns(df)
    X, y = df[feats], df["label"].to_numpy()

    incomplete = [c for c in feats if X[c].isna().any()]
    if not incomplete:
        sys.exit("没有缺失变量，无须画插补诊断图")
    cont, binary = split_columns(X, incomplete)

    print(f"缺失变量 {len(incomplete)} 个（连续 {len(cont)}、二分类 {len(binary)}）"
          f"　插补 m={args.imputations}，约需一两分钟")
    # 与主分析同规：插补模型纳入结局
    sets = impute(X, y, args.imputations, SEED, include_outcome=True)

    os.makedirs(OUTDIR, exist_ok=True)
    plt.rcParams.update({
        "font.size": 9, "figure.dpi": 200,
        "axes.edgecolor": "0.35", "axes.labelcolor": "0.15",
        "text.color": "0.15", "xtick.color": "0.35", "ytick.color": "0.35",
    })

    ncol = 3
    nrow_cont = int(np.ceil(len(cont) / ncol))
    LEFT, RIGHT = 0.075, 0.975
    LEFT_B = 0.30          # B 排的变量名比 A 排坐标轴左缘长得多，单独让出位置
    fig = plt.figure(figsize=(7.5, 2.15 * nrow_cont + 3.6))

    top_h = 0.905
    b_h = 0.20             # B 排占的竖向比例
    gap = 0.085
    gs = fig.add_gridspec(nrow_cont, ncol, left=LEFT, right=RIGHT,
                          top=top_h, bottom=0.235 + b_h + gap,
                          hspace=0.75, wspace=0.30)

    for i, col in enumerate(cont):
        ax = fig.add_subplot(gs[i // ncol, i % ncol])
        miss = X[col].isna().to_numpy()
        obs = X.loc[~miss, col].to_numpy()
        imp = np.concatenate([s.loc[miss, col].to_numpy() for s in sets])

        lo = min(obs.min(), imp.min())
        hi = max(obs.max(), imp.max())
        bins = np.linspace(lo, hi, 34)
        for data, color, label in ((obs, OBS_COLOR, "Observed"),
                                   (imp, IMP_COLOR, "Imputed")):
            ax.hist(data, bins=bins, density=True, histtype="stepfilled",
                    color=color, alpha=0.32, lw=0)
            ax.hist(data, bins=bins, density=True, histtype="step",
                    color=color, lw=1.3, label=label)

        ax.set_title(nice(col), fontsize=8.2, pad=14, loc="left")
        ax.text(0, 1.015, f"{miss.mean()*100:.1f}% missing", fontsize=7,
                color="0.45", transform=ax.transAxes, va="bottom")
        ax.set_yticks([])
        ax.tick_params(length=3, labelsize=7.5)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)

    # 二分类：阳性比例点图，横线为 m 份插补之间的范围
    axb = fig.add_axes((LEFT_B, 0.235, RIGHT - LEFT_B, b_h))
    ypos = np.arange(len(binary))[::-1]
    for i, col in enumerate(binary):
        miss = X[col].isna().to_numpy()
        obs_p = X.loc[~miss, col].mean()
        # 插补后是小数，按 0.5 归类回二分类再求比例
        per_set = [(s.loc[miss, col] >= 0.5).mean() for s in sets]
        axb.plot([min(per_set), max(per_set)], [ypos[i]] * 2,
                 color=IMP_COLOR, lw=1.4, alpha=0.55, solid_capstyle="round",
                 zorder=2)
        axb.plot(np.mean(per_set), ypos[i], "o", ms=5.5, mfc="white",
                 mec=IMP_COLOR, mew=1.5, zorder=3)
        axb.plot(obs_p, ypos[i], "o", ms=5.5, color=OBS_COLOR, zorder=3)

    axb.set_yticks(ypos)
    axb.set_yticklabels([f"{nice(c)}  ({X[c].isna().mean()*100:.1f}%)"
                         for c in binary], fontsize=7.8)
    axb.set_xlabel("Proportion positive", fontsize=8)
    axb.set_xlim(-0.02, 1.02)
    axb.set_ylim(-0.7, len(binary) - 0.3)
    axb.grid(axis="x", color="0.9", lw=0.7, zorder=0)
    axb.set_axisbelow(True)
    axb.tick_params(length=3, labelsize=7.5)
    for side in ("top", "right", "left"):
        axb.spines[side].set_visible(False)

    fig.text(LEFT, 0.945, "A   Continuous variables", fontsize=10,
             fontweight="bold", va="bottom")
    fig.text(LEFT, 0.235 + b_h + 0.022, "B   Binary variables", fontsize=10,
             fontweight="bold", va="bottom")

    fig.legend(handles=[
        Line2D([], [], color=OBS_COLOR, lw=1.5, marker="o", ms=5, label="Observed"),
        Line2D([], [], color=IMP_COLOR, lw=1.5, marker="o", ms=5, mfc="white",
               mew=1.5, label=f"Imputed (m = {args.imputations})"),
    ], loc="lower right", bbox_to_anchor=(RIGHT, 0.945), ncol=2, frameon=False,
        fontsize=7.6, handlelength=1.8, borderpad=0.0, borderaxespad=0.0)

    fig.text(LEFT, 0.175,
             "Distributions of observed values against values drawn by chained-equation "
             "multiple imputation, pooled over m imputations;\n"
             "in B the horizontal bar spans the m imputation-specific proportions. "
             "Missingness here is informative rather than random — "
             "children\n"
             "taken quickly to theatre for endoscopic removal often had no bloods drawn "
             "— so imputed and observed distributions are not\n"
             "expected to coincide. What the figure is meant to show is that imputed "
             "values stay within a clinically possible range and that\n"
             "any shift runs in the direction the missingness mechanism predicts.",
             fontsize=7.1, color="0.4", va="top", linespacing=1.6)

    for ext in ("pdf", "png"):
        fig.savefig(f"{OUTDIR}/figS1_imputation.{ext}")
    plt.close(fig)

    print(f"已输出 {OUTDIR}/figS1_imputation.{{pdf,png}}")
    for col in cont:
        miss = X[col].isna().to_numpy()
        obs = X.loc[~miss, col].mean()
        imp = np.mean([s.loc[miss, col].mean() for s in sets])
        print(f"  {nice(col):<28} 观测均值 {obs:8.2f}　插补均值 {imp:8.2f}"
              f"　差 {imp - obs:+.2f}")


if __name__ == "__main__":
    main()

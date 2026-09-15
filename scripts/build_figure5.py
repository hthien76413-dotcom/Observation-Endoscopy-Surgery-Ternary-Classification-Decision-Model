# -*- coding: utf-8 -*-
"""
Fig 5：逐类校准曲线（上排）与多分类决策曲线分析（下排）。

用法:
    python3 scripts/definitive_analysis.py     # 先跑，产出 outputs/predictions.csv
    python3 scripts/build_figure5.py

输出:
    outputs/figures/fig5_calibration_dca.{pdf,png}

**校准绝不能画表观概率。** 惩罚 logistic 回归在自己的训练数据上几乎必然接近
完美校准（斜率 ≈ 1、截距 ≈ 0），画出来是一条贴着对角线的直线，什么也没说明。
本图与 Fig 4 同规，只读 outputs/predictions.csv 的 cv 与 temporal 两套。

上排每格画两条：折内交叉验证（实线）与时间验证（虚线）。**两条分开画是本图的
要点**——判别力在时间验证里基本保住（宏平均 0.799 → 0.779），校准却明显漂移，
原因是构成比变了（观察 47.1% → 55.9%、内镜 42.0% → 36.3%、手术 10.9% → 7.7%），
而截距正是承接患病率的那一项。结论是模型若要用于后续年份，须先重估截距。
这一点不写出来，读者会默认「时间验证通过」＝可以直接用。

下排为逐类净获益。三格共用同一条阈值轴，便于整排一起读；纵轴各自缩放，因为
读者比较的是格内的三条线（模型 / 全部按该类处理 / 都不处理），而非跨格比较。

分箱数按样本量定：n_bins = clip(n // 120, 4, 10)。交叉验证 n=1238 得 10 箱，
时间验证 n=413 得 4 箱——后者手术仅 32 例，硬切 10 箱会有半数箱子实际比例为 0，
画出来是锯齿而不是校准。
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import calibration_slope_intercept, net_benefit  # noqa: E402

PRED = "outputs/predictions.csv"
OUTDIR = "outputs/figures"

COLORS = ["#5C8A1E", "#0A7EA4", "#BE3241"]
LABELS = ["Observation", "Endoscopy", "Surgery"]
PCOLS = ["p_obs", "p_endo", "p_surg"]

THRESHOLDS = np.arange(0.01, 0.82, 0.01)
SERIES = [("cv", "Cross-validated", "-", 1.0),
          ("temporal", "Temporal validation", (0, (4, 2.4)), 0.8)]


def n_bins_for(n):
    """箱数随样本量伸缩，避免小样本被硬切成锯齿。"""
    return int(np.clip(n // 120, 4, 10))


def calibration_points(y, p, n_bins):
    """等频分箱：(预测均值, 实际比例, 例数)。

    metrics.calibration_curve_points 固定 10 箱，这里要按样本量调箱数，
    故就地实现；分箱规则与之相同（argsort 后 array_split）。
    """
    order = np.argsort(p)
    out = []
    for b in np.array_split(order, n_bins):
        if len(b):
            out.append((p[b].mean(), y[b].mean(), len(b)))
    return np.array(out)


def calib_panel(ax, sets, k, show_legend):
    lim = 0.0
    for key, name, ls, alpha in SERIES:
        y, P = sets[key]
        yk, pk = (y == k).astype(float), P[:, k]
        pts = calibration_points(yk, pk, n_bins_for(len(y)))
        lim = max(lim, pts[:, 0].max(), pts[:, 1].max())
        ax.plot(pts[:, 0], pts[:, 1], ls=ls, color=COLORS[k], lw=1.5, alpha=alpha,
                marker="o" if key == "cv" else "s", ms=3.4,
                mfc=COLORS[k] if key == "cv" else "white",
                mew=1.0, mec=COLORS[k], label=name, zorder=3)

    lim = min(1.0, np.ceil(lim * 10) / 10 + 0.05)
    ax.plot([0, lim], [0, lim], color="0.6", ls=(0, (4, 3)), lw=0.9, zorder=1,
            label="Ideal" if show_legend else None)

    # 底部铺一条预测概率的分布带。校准曲线最容易被误读的地方是「曲线右端
    # 偏离对角线很远」——但那一段往往只有几例。把分布画出来，读者一眼
    # 看得出哪一段有数据支撑。
    y, P = sets["cv"]
    hist, edges = np.histogram(P[:, k], bins=28, range=(0, lim))
    if hist.max():
        h = hist / hist.max() * lim * 0.11
        ax.bar(edges[:-1], h, width=np.diff(edges), align="edge",
               color=COLORS[k], alpha=0.16, lw=0, zorder=0)

    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_aspect("equal")
    return lim


def advantage_range(nb, all_nb, thresholds):
    """模型同时优于 treat-all 与 treat-none 的最长连续阈值区间。

    阈值低于患病率时 treat-all 本来就该占优（把所有人都按该类处理，净获益
    约等于患病率），所以区间下界高于 0 不是模型的毛病，是 DCA 的常态。
    把区间算出来而非笼统说「在合理范围内更优」，免得图上看得见的那段
    劣势区被文字盖过去。
    """
    ok = (nb > all_nb) & (nb > 0)
    best, run, start = (0, None, None), 0, None
    for t, good in zip(thresholds, ok):
        if good:
            start = t if run == 0 else start
            run += 1
            if run > best[0]:
                best = (run, start, t)
        else:
            run = 0
    return best[1], best[2]


def dca_panel(ax, y, P, k):
    nb, all_nb = net_benefit(y, P, k, THRESHOLDS)
    lo, hi = advantage_range(nb, all_nb, THRESHOLDS)
    if lo is not None:
        ax.axvspan(lo, hi, color=COLORS[k], alpha=0.07, lw=0, zorder=0)

    ax.plot(THRESHOLDS, nb, color=COLORS[k], lw=1.6, label="Model", zorder=3)
    ax.plot(THRESHOLDS, all_nb, color="0.45", lw=1.0,
            ls=(0, (4, 2.4)), label="Treat all", zorder=2)
    ax.axhline(0, color="0.45", lw=0.9, label="Treat none", zorder=2)

    top = max(float(nb.max()), 0.02)
    ax.set_xlim(0, THRESHOLDS[-1])
    ax.set_ylim(-top * 0.28, top * 1.18)
    return lo, hi


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not os.path.exists(PRED):
        sys.exit(f"缺少 {PRED}——先跑 python3 scripts/definitive_analysis.py")

    pred = pd.read_csv(PRED)
    sets = {}
    for key, *_ in SERIES:
        d = pred[pred["set"] == key]
        if d.empty:
            sys.exit(f"{PRED} 缺少 set={key}——请重跑 definitive_analysis.py")
        sets[key] = (d["label"].to_numpy(), d[PCOLS].to_numpy())

    os.makedirs(OUTDIR, exist_ok=True)
    plt.rcParams.update({
        "font.size": 9, "figure.dpi": 200,
        "axes.edgecolor": "0.35", "axes.labelcolor": "0.15",
        "text.color": "0.15", "xtick.color": "0.35", "ytick.color": "0.35",
    })

    fig, axes = plt.subplots(2, 3, figsize=(7.5, 6.9))
    LEFT = 0.085
    fig.subplots_adjust(left=LEFT, right=0.985, top=0.855, bottom=0.260,
                        wspace=0.34, hspace=0.72)

    si = {key: calibration_slope_intercept(*sets[key]) for key, *_ in SERIES}

    for k, label in enumerate(LABELS):
        ax = axes[0][k]
        calib_panel(ax, sets, k, show_legend=(k == 0))
        ax.set_title(label, fontsize=9.5, fontweight="bold", pad=20, color=COLORS[k])
        # 注记须塞进面板宽度内（约 1.8 英寸），故去掉斜杠两侧空格。
        note = "  ".join(
            f"{'CV' if key == 'cv' else 'Temp'} {si[key][k][0]:.2f}/"
            f"{si[key][k][1]:+.2f}" for key, *_ in SERIES)
        ax.text(0, 1.035, note, transform=ax.transAxes, fontsize=6.9,
                color="0.4", va="bottom")
        ax.set_xlabel("Predicted probability", fontsize=8)
        if k == 0:
            ax.set_ylabel("Observed proportion", fontsize=8)
        ax.tick_params(length=3, labelsize=7.5)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    y_cv, P_cv = sets["cv"]
    spans = {}
    for k, label in enumerate(LABELS):
        ax = axes[1][k]
        spans[label] = dca_panel(ax, y_cv, P_cv, k)
        ax.set_xlabel("Threshold probability", fontsize=8)
        if k == 0:
            ax.set_ylabel("Net benefit", fontsize=8)
        ax.tick_params(length=3, labelsize=7.5)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    # 行标题按子图实际位置放置，不写死 y——之前写死的 0.452 落进了
    # B 排坐标区，压在图例上。A 排上方还有类别标题与注记，故让得更高。
    from matplotlib.lines import Line2D

    ya = axes[0][0].get_position().y1 + 0.075
    yb = axes[1][0].get_position().y1 + 0.020
    fig.text(LEFT, ya, "A   Calibration", fontsize=10.5, fontweight="bold",
             va="bottom")
    fig.text(LEFT, yb, "B   Decision curve analysis", fontsize=10.5,
             fontweight="bold", va="bottom")

    def shared_legend(handles, y):
        fig.legend(handles=handles, loc="lower right", bbox_to_anchor=(0.985, y),
                   ncol=len(handles), frameon=False, fontsize=7.4,
                   handlelength=1.8, handletextpad=0.5, columnspacing=1.6,
                   borderpad=0.0, borderaxespad=0.0)

    grey = "0.35"
    shared_legend([
        Line2D([], [], color=grey, lw=1.5, marker="o", ms=3.4,
               label="Cross-validated"),
        Line2D([], [], color=grey, lw=1.5, ls=(0, (4, 2.4)), marker="s", ms=3.4,
               mfc="white", label="Temporal validation"),
        Line2D([], [], color="0.6", lw=0.9, ls=(0, (4, 3)), label="Ideal"),
    ], ya)
    shared_legend([
        Line2D([], [], color=grey, lw=1.6, label="Model"),
        Line2D([], [], color="0.45", lw=1.0, ls=(0, (4, 2.4)), label="Treat all"),
        Line2D([], [], color="0.45", lw=0.9, label="Treat none"),
    ], yb)

    span_txt = ";  ".join(f"{l.lower()} {lo:.2f}\u2013{hi:.2f}"
                          for l, (lo, hi) in spans.items())
    fig.text(LEFT, 0.175,
             "A  Above each panel: calibration slope / intercept for the "
             "cross-validated (CV) and temporal (Temp) predictions. The\n"
             "shaded strip shows where the predicted probabilities actually lie. "
             "Discrimination survives temporal validation but\n"
             "calibration does not \u2014 the intercepts move with the case mix "
             "(observation 47.1 \u2192 55.9%, endoscopy 42.0 \u2192 36.3%,\n"
             "surgery 10.9 \u2192 7.7%), so the intercepts would need re-estimating "
             "before use in a later period.\n"
             "B  Net benefit from the cross-validated predictions. Shading marks "
             "where the model beats both default strategies\n"
             "(" + span_txt + "). Below those ranges treating everyone as that "
             "class is preferable,\n"
             "as expected once the threshold falls under prevalence.",
             fontsize=7.1, color="0.4", va="top", linespacing=1.6)

    for ext in ("pdf", "png"):
        fig.savefig(f"{OUTDIR}/fig5_calibration_dca.{ext}")
    plt.close(fig)

    print(f"已输出 {OUTDIR}/fig5_calibration_dca.{{pdf,png}}")
    for key, name, *_ in SERIES:
        n = len(sets[key][0])
        print(f"  {name:<22} n={n:<5} 箱数 {n_bins_for(n)}  " + "　".join(
            f"{l} {s:.2f}/{i:+.2f}" for l, (s, i) in zip(LABELS, si[key])))


if __name__ == "__main__":
    main()

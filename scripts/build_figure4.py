# -*- coding: utf-8 -*-
"""
Fig 4：one-vs-rest ROC 曲线，内部验证与时间外部验证并列。

用法:
    python3 scripts/definitive_analysis.py     # 先跑，产出 outputs/predictions.csv
    python3 scripts/build_figure4.py

输出:
    outputs/figures/fig4_roc.{pdf,png}

**画的是哪一套概率，是这张图唯一要紧的事。**

`outputs/predictions.csv` 里有三套概率：表观、折内交叉验证、时间验证。表观
（模型在自己的训练数据上预测）宏平均 AUC 约 0.832，交叉验证约 0.799——差 0.033。
若 Fig 4 画表观而 Table 3 报交叉验证，图与表在同一篇稿子里就对不上，审稿人一核
即出问题，且解释不掉：曲线下面积是能从图上量出来的。

故本脚本**只取 cv 与 temporal 两套**，且在图注中写明。表观曲线由
definitive_analysis.py 另存为 roc_apparent_DIAGNOSTIC.png，文件名与标题都标了
「不可入稿」。

置信区间用成对自助法（重抽病例而非重抽预测），2000 次，取百分位。时间验证集
手术仅 32 例，其 CI 必然很宽——这正是要如实画出来的，不是缺陷。
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PRED = "outputs/predictions.csv"
OUTDIR = "outputs/figures"
SEED = 20260915
N_BOOT = 2000

# 与 Fig 1–3、校准图、DCA 共用同一套三色（已过色觉障碍校验）
COLORS = ["#5C8A1E", "#0A7EA4", "#BE3241"]
LABELS = ["Observation", "Endoscopy", "Surgery"]
PCOLS = ["p_obs", "p_endo", "p_surg"]

# 副标题只放一句能一眼读完的，方法细节留给图注——两栏并排时标题行
# 宽度有限，写长了会越过面板右缘。
PANELS = [
    ("cv", "A", "Internal validation", "5-fold cross-validation"),
    ("temporal", "B", "Temporal validation", "fitted on 2016–2023"),
]


def auc_ci(y, p, rng, n_boot=N_BOOT):
    """成对自助的 AUC 与 95% 百分位区间。

    重抽的是病例（真值与预测概率成对抽出），不是重新拟合模型——本图评的是
    既定模型在该数据集上的判别力，抽样不确定性来自病例而非训练过程。
    自助样本若只剩单一类别则跳过，否则 roc_auc_score 会抛异常。
    """
    from sklearn.metrics import roc_auc_score

    point = roc_auc_score(y, p)
    n = len(y)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        if yb.min() == yb.max():
            continue
        vals.append(roc_auc_score(yb, p[idx]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return point, lo, hi


def panel(ax, df, title_letter, title, subtitle, rng):
    from sklearn.metrics import roc_curve

    y = df["label"].to_numpy()
    proba = df[PCOLS].to_numpy()

    aucs = []
    for k, label in enumerate(LABELS):
        yk = (y == k).astype(int)
        fpr, tpr, _ = roc_curve(yk, proba[:, k])
        point, lo, hi = auc_ci(yk, proba[:, k], rng)
        aucs.append(point)
        # 每类例数写进标签：手术在时间验证集只有 32 例，读者看到 n
        # 才知道那条 0.96 的区间为什么宽。
        ax.plot(fpr, tpr, color=COLORS[k], lw=1.7, solid_capstyle="round",
                label=f"{label} ({int(yk.sum())})  {point:.2f} "
                      f"({lo:.2f}–{hi:.2f})")

    ax.plot([0, 1], [0, 1], color="0.6", ls=(0, (4, 3)), lw=0.9, zorder=0)
    ax.set_xlim(-0.015, 1.015)
    ax.set_ylim(-0.015, 1.015)
    ax.set_aspect("equal")
    ax.set_xlabel("1 − Specificity")
    ax.set_ylabel("Sensitivity")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=3, labelsize=8)

    ax.set_title(f"{title_letter}   {title}", loc="left", fontsize=10.5,
                 fontweight="bold", pad=17)
    ax.text(0, 1.028, f"{subtitle}   ·   N = {len(y)}", transform=ax.transAxes,
            fontsize=7.8, color="0.4", va="bottom")

    # 图例落在右下的空白三角区。字号、handlelength、borderaxespad 都收过，
    # 免得最长的一条顶到左边的 y 轴刻度上。
    leg = ax.legend(frameon=False, loc="lower right", fontsize=7.4,
                    handlelength=1.3, handletextpad=0.5, borderpad=0.0,
                    borderaxespad=0.35, labelspacing=0.42,
                    title=f"AUC (95% CI)   macro {np.mean(aucs):.3f}",
                    title_fontsize=7.8, alignment="left")
    leg.get_title().set_color("0.35")
    return aucs


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not os.path.exists(PRED):
        sys.exit(f"缺少 {PRED}——先跑 python3 scripts/definitive_analysis.py")

    pred = pd.read_csv(PRED)
    missing = [s for s, *_ in PANELS if s not in set(pred["set"])]
    if missing:
        sys.exit(f"{PRED} 缺少 set={missing}——请重跑 definitive_analysis.py")

    os.makedirs(OUTDIR, exist_ok=True)
    plt.rcParams.update({
        "font.size": 9, "figure.dpi": 200,
        "axes.edgecolor": "0.35", "axes.labelcolor": "0.15",
        "text.color": "0.15", "xtick.color": "0.35", "ytick.color": "0.35",
    })

    rng = np.random.default_rng(SEED)

    # 坐标轴设了 set_aspect("equal")：若外框不是正方形，matplotlib 会把
    # 坐标轴缩到框内居中，下方凭空多出一条空白。故先按边距反解图高，
    # 让每个子图框本身就是正方形。
    FW, L, R, WSPACE, TOP, BOTTOM = 7.2, 0.075, 0.985, 0.22, 0.88, 0.285
    ax_w = (R - L) / (2 + WSPACE) * FW
    fh = ax_w / (TOP - BOTTOM)

    fig, axes = plt.subplots(1, 2, figsize=(FW, fh))
    fig.subplots_adjust(left=L, right=R, top=TOP, bottom=BOTTOM, wspace=WSPACE)

    summary = {}
    for ax, (key, letter, title, subtitle) in zip(axes, PANELS):
        summary[key] = panel(ax, pred[pred["set"] == key], letter, title, subtitle, rng)

    fig.text(L, 0.168,
             "One-versus-rest ROC curves with 95% bootstrap confidence intervals "
             "(2000 resamples of cases); class sizes in parentheses. Panel A\n"
             "imputes separately within each fold; panel B applies the 2016\u20132023 "
             "model unchanged. Apparent (in-sample) curves are deliberately\n"
             "not shown \u2014 they overstate discrimination by about 0.03 macro AUC. "
             "Surgery separates sharply in both panels;\n"
             "the observation\u2013endoscopy boundary does not, which we argue is a "
             "property of the decision rather than of the model.",
             fontsize=7.3, color="0.4", va="top", linespacing=1.65)

    for ext in ("pdf", "png"):
        fig.savefig(f"{OUTDIR}/fig4_roc.{ext}")
    plt.close(fig)

    print(f"已输出 {OUTDIR}/fig4_roc.{{pdf,png}}")
    for key, letter, title, _ in PANELS:
        aucs = summary[key]
        print(f"  {letter} {title:<22} " +
              "　".join(f"{l} {a:.3f}" for l, a in zip(LABELS, aucs)) +
              f"　宏平均 {np.mean(aucs):.3f}")


if __name__ == "__main__":
    main()

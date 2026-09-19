# -*- coding: utf-8 -*-
"""
学习曲线：观察/内镜的判别力是否随样本量爬升，还是已经平台。

用法:
    python3 scripts/learning_curve.py [--repeats 10] [--quick]

输出:
    outputs/learning_curve.csv         逐次重抽的结果（供复核）
    outputs/learning_curve.txt         文字报告：分段斜率、结论
    outputs/figures/figS2_learning_curve.{pdf,png}

**这张图要回答的问题，不是「模型好不好」，是「观察／内镜分不开这件事，
有没有另一种解释」。** 正文的核心论点是：手术 AUC 0.91–0.96、观察/内镜仅
0.68–0.74，是因为前者由客观病理状态决定、后者含临床实践差异——不是模型的
缺陷。但这个论点现在至少有两个未排除的替代解释：

  1. 样本不够。`scripts/sample_size.py` 按 Riley 标准算出观察 vs 内镜这对
     比较需要 2095 例（折合全队列），实际只有 1238——低判别力可能只是因为
     还没测够。
  2. 变量不够。X 线定位 557 例无法定位到节段、异物尺寸仅 1.8% 病历写明；
     重标注回流前，模型缺了这些理论上有用的变量。

替代解释 2 只能等重标注回流后才能直接检验（届时重跑 Fig 4/5 看 AUC 有无
提升）。但替代解释 1——「再给更多同类数据，AUC 还会不会涨」——现有队列
本身就能回答：把训练集从小到大切，看观察/内镜的判别力是**持续爬升**
（支持「样本不够」）还是**早早走平**（支持「这是临床决策本身的性质」，
即正文论点）。手术类作为对照：它应该在很小的样本量下就已经很高，
因为区分它的信号（穿孔、多枚磁体）本身就强。

## 方法

- 先按类别分层切出固定 20% 作时间与拆分都独立的测试集（不参与任何训练），
  作为整条曲线唯一的评价基准，保证每个点比较的是同一把尺子。
- 训练池（余下 80%，约 990 例）按比例（10%–100%）分层子抽样，每个比例
  重复 R 次——重复带来的方差既来自「抽到哪些例子」，也来自插补本身的
  随机抽样（`sample_posterior=True`），在 100% 这一点两种方差仍然都在，
  不会因为「只有一种可能的样本」而塌缩成一条直线。
- 插补边界、结局纳入插补模型、惩罚回归的拟合方式，均与
  `definitive_analysis.py` 的折内交叉验证同规——训练集单独插补、
  测试集用该次训练出的插补器变换（不纳入结局），避免跨集信息流动。
- 惩罚强度用 `select_penalty()` 在训练池全量上选一次并固定，与主分析
  的处理方式一致（避免 96 次网格搜索的计算量）。

## 一处方法学简化，必须交代

每个「比例 × 重复」只做**一次插补抽样**，不像主分析那样做 m 份多重插补
再按 Rubin 规则合并。省下 m 倍的计算量；代价是单次结果比 MI 合并后的估计
更燥，但重复本身（R 次独立重抽 + 独立插补抽样）已经在聚合层面部分补偿了
这一点——阅读误差带时按「不如主分析精确」来看，不要当成与 Fig 4/5 同等
严格的效能估计。这条曲线的目的是看趋势方向，不是给出另一个可报告的 AUC。

## 结论怎么下

比较「曲线尾段」与「曲线头段」的斜率（每增加 100 例，AUC 涨多少）。
尾段斜率远小于头段——支持「已经平台」；尾段斜率仍接近头段——支持
「数据不够，很可能还会再涨」。这个判断只依据观测范围内的 8 个点，
**不做任何超出观测范围的外推**（把学习曲线外推到 n=2095 这类做法在
只有 8 个点时并不可靠，容易把噪声读成信号）。
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from definitive_analysis import (LABELS, SEED, feature_columns, fit_model,  # noqa: E402
                                 observed_bounds, select_penalty)
from metrics import one_vs_rest_auc  # noqa: E402

OUT_CSV = "outputs/learning_curve.csv"
OUT_META = "outputs/learning_curve_meta.json"
OUT_TXT = "outputs/learning_curve.txt"
OUT_FIG = "outputs/figures/figS2_learning_curve"

TEST_FRAC = 0.20
FRACTIONS = np.array([0.10, 0.20, 0.32, 0.45, 0.58, 0.71, 0.85, 1.00])
FIG_LABELS = ["Observation", "Endoscopy", "Surgery"]
COLORS = ["#5C8A1E", "#0A7EA4", "#BE3241"]
MACRO_COLOR = "0.35"


def stratified_subsample(y, n, rng):
    """按类别比例（非重抽）抽 n 个索引；舍入误差归入占比最大的类。"""
    idx_by_class = [np.where(y == k)[0] for k in range(len(LABELS))]
    props = np.array([len(ix) for ix in idx_by_class], dtype=float)
    props /= props.sum()
    counts = np.floor(props * n).astype(int)
    counts[int(np.argmax(props))] += n - counts.sum()
    chosen = []
    for k, c in enumerate(counts):
        c = int(min(c, len(idx_by_class[k])))
        chosen.append(rng.choice(idx_by_class[k], size=c, replace=False))
    return np.concatenate(chosen)


def fit_eval(Xtr, ytr, Xte, penalty, C, seed):
    """单次插补抽样 + 拟合 + 在固定测试集上评估。

    与 definitive_analysis.cross_validated_proba() 同规：插补器只在
    训练子集上拟合，测试集经同一插补器变换（结局列置 NaN，不纳入）。
    """
    block = Xtr.copy()
    for k in range(len(LABELS)):
        block[f"__y{k}"] = (ytr == k).astype(float)
    lo, hi = observed_bounds(block)
    imp = IterativeImputer(max_iter=10, sample_posterior=True,
                           min_value=lo, max_value=hi, random_state=seed)
    imp.fit(block)
    tr_filled = pd.DataFrame(imp.transform(block), columns=block.columns,
                             index=Xtr.index)[Xtr.columns]

    te_block = Xte.copy()
    for k in range(len(LABELS)):
        te_block[f"__y{k}"] = np.nan
    te_filled = pd.DataFrame(imp.transform(te_block), columns=block.columns,
                             index=Xte.index)[Xte.columns]

    sc, clf = fit_model(tr_filled, ytr, penalty, C)
    return clf.predict_proba(sc.transform(te_filled))


def tail_vs_head_slope(sub, k):
    """尾段（后两点）与头段（前两点）的斜率，单位：AUC / 百例。"""
    def slope(rows):
        n0, n1 = rows["n"].iloc[0], rows["n"].iloc[-1]
        a0, a1 = rows["auc"].iloc[0], rows["auc"].iloc[-1]
        return (a1 - a0) / (n1 - n0) * 100 if n1 != n0 else np.nan

    g = sub[sub["class"] == k].groupby("n", as_index=False)["auc"].mean().sort_values("n")
    return slope(g.iloc[:2]), slope(g.iloc[-2:])


def write_report_and_figure(result, meta):
    """文字报告 + 图，供完整计算流程与 --replot 共用。

    meta 须含：n_pool, n_test, penalty, C, fractions, repeats。
    """
    n_pool, n_test = meta["n_pool"], meta["n_test"]
    penalty, C, fractions, R = meta["penalty"], meta["C"], meta["fractions"], meta["repeats"]

    L = []
    a = L.append
    a("=" * 78)
    a("学习曲线：观察/内镜的判别力是否随样本量爬升，还是已经平台")
    a("=" * 78)
    a(f"训练池 n={n_pool}（固定测试集 n={n_test} 不参与任何训练）")
    a(f"惩罚强度 {penalty}, C={C}（训练池全量上选定一次）")
    a(f"比例 {list(fractions)}　每比例重复 {R} 次"
      f"（单次插补抽样，非 m 份 MI 合并——见脚本文档字符串）")
    a("")

    a("-" * 78)
    a("各比例 · 各类别的平均 AUC（跨重复）")
    a("-" * 78)
    for n_val in sorted(result["n"].unique()):
        line = f"  n={n_val:>4}　"
        for cls in LABELS + ["宏平均"]:
            sub = result[(result["n"] == n_val) & (result["class"] == cls)]["auc"]
            line += f"{cls} {sub.mean():.3f}±{sub.std():.3f}　"
        a(line)
    a("")

    a("-" * 78)
    a("头段 vs 尾段斜率（AUC 每增 100 例的变化）")
    a("-" * 78)
    verdicts = {}
    for cls in LABELS + ["宏平均"]:
        head, tail = tail_vs_head_slope(result, cls)
        ratio = abs(tail) / abs(head) if head else np.nan
        a(f"  {cls:<4} 头段 {head:+.4f}/百例　尾段 {tail:+.4f}/百例"
          f"　尾/头 比值 {ratio:.2f}")
        verdicts[cls] = (head, tail, ratio)
    a("")
    a("  比值远小于 1：尾段已显著放缓，支持「判别力已趋平台，不只是样本不够」。")
    a("  比值接近或大于 1：尾段仍在爬升，支持「更多同类数据可能继续提升判别力」，")
    a("  正文「这是临床决策本身的性质」这一论点须谨慎措辞，待重标注数据佐证。")
    a("")

    obs_ratio = verdicts["观察"][2]
    endo_ratio = verdicts["内镜"][2]
    surg_ratio = verdicts["手术"][2]
    worst = max(obs_ratio, endo_ratio)   # 只看观察/内镜——这是要回答的问题
    a("-" * 78)
    a("结论（仅供内部判断措辞，不做超出观测范围的外推）")
    a("-" * 78)
    a(f"  手术类尾/头比值 {surg_ratio:.2f}，供对照：它是最容易分开的类别，")
    a("  走平得早不意外，不作为观察/内镜判断的依据。")
    a("")
    if worst < 0.4:
        a("  观察／内镜的尾段斜率明显小于头段——在当前训练池规模下大体走平。")
        a("  这与「观察/内镜分不开是临床决策性质而非样本不足」的论点方向一致，")
        a("  但 sample_size.py 按 Riley 标准算出该对比较仍未达标（需 2095 例，")
        a("  实际 1238），两条证据须并置写出，不能只引这条学习曲线掩盖那条")
        a("  样本量核算——走平也可能只是当前样本规模内「爬得慢」，不等于")
        a("  「给再多数据也不会涨」，正文措辞仍需保留「有限样本内」的限定。")
    else:
        a("  观察／内镜的尾段斜率仍接近头段（或更陡），当前训练池规模内")
        a("  判别力还没有明显走平。这与 sample_size.py 的 Riley 核算结果（该对")
        a("  比较仍需上千例）方向一致：现有证据更支持「样本不足」而非「临床")
        a("  决策本身不可预测」。正文「这不是模型缺陷而是临床真相」这一表述")
        a("  须软化，加上「有限样本内」的限定，并明确列为重标注/扩样后待验证。")
    a("=" * 78)

    report = "\n".join(L)
    with open(OUT_TXT, "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print("\n" + report)
    print(f"\n已写入 {OUT_TXT}")

    # -----------------------------------------------------------------
    # 图
    # -----------------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.size": 9, "figure.dpi": 200,
        "axes.edgecolor": "0.35", "axes.labelcolor": "0.15",
        "text.color": "0.15", "xtick.color": "0.35", "ytick.color": "0.35",
    })
    fig, ax = plt.subplots(figsize=(6.4, 4.6))

    # 图内文字一律用英文——matplotlib 在本环境无 CJK 字体，中文会渲染成方框
    # （与 Fig 1–5 同一约定）；result["class"] 仍是中文，按 LABELS 取子集。
    for k, (label, fig_label) in enumerate(zip(LABELS, FIG_LABELS)):
        g = (result[result["class"] == label].groupby("n")["auc"]
             .agg(["mean", "std"]).reset_index().sort_values("n"))
        ax.plot(g["n"], g["mean"], color=COLORS[k], lw=1.7, marker="o", ms=4,
                label=fig_label)
        ax.fill_between(g["n"], g["mean"] - g["std"], g["mean"] + g["std"],
                        color=COLORS[k], alpha=0.15, lw=0)

    g = (result[result["class"] == "宏平均"].groupby("n")["auc"]
         .agg(["mean", "std"]).reset_index().sort_values("n"))
    ax.plot(g["n"], g["mean"], color=MACRO_COLOR, lw=1.3, ls=(0, (4, 2.4)),
            marker="s", ms=3.4, mfc="white", label="Macro-average")

    ax.set_xlabel(f"Training-set size (n, held-out test set fixed at n={n_test})")
    ax.set_ylabel("AUC on fixed held-out test set")
    ax.set_ylim(0.5, 1.0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=3, labelsize=8)
    ax.legend(frameon=False, fontsize=8, loc="lower right")

    fig.text(0.06, -0.02,
             "One imputation draw per point (not pooled multiple imputation); "
             "shaded bands are ±1 SD across "
             f"{R} repeats per training size. Surgery separates with little "
             "training data; observation and endoscopy are\n"
             "the comparison this curve is meant to inform — see "
             "outputs/learning_curve.txt for the head-vs-tail slope test "
             "and its bearing on the manuscript's central claim.",
             fontsize=6.8, color="0.4", va="top", linespacing=1.5)

    fig.tight_layout(rect=(0, 0.06, 1, 1))
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT_FIG}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(f"已输出 {OUT_FIG}.{{pdf,png}}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=10)
    ap.add_argument("--quick", action="store_true", help="3 个比例 × 3 次重复，供冒烟测试")
    ap.add_argument("--replot", action="store_true",
                    help="跳过重新计算，只从已有 outputs/learning_curve.csv 重画图/报告"
                         "（改图内样式时用，不必重跑几分钟的插补模拟）")
    args = ap.parse_args()

    if args.replot:
        if not (os.path.exists(OUT_CSV) and os.path.exists(OUT_META)):
            sys.exit(f"缺少 {OUT_CSV} 或 {OUT_META}——先跑一次不带 --replot 的完整计算")
        result = pd.read_csv(OUT_CSV)
        with open(OUT_META, encoding="utf-8") as fh:
            meta = json.load(fh)
        print(f"--replot：从 {OUT_CSV} 重画，跳过插补模拟")
        write_report_and_figure(result, meta)
        return

    fractions = np.array([0.20, 0.60, 1.00]) if args.quick else FRACTIONS
    R = 3 if args.quick else args.repeats

    df = pd.read_csv("outputs/cohort.csv")
    feats = feature_columns(df)
    X_all, y_all = df[feats], df["label"].to_numpy()

    idx = np.arange(len(y_all))
    idx_pool, idx_test = train_test_split(
        idx, test_size=TEST_FRAC, random_state=SEED, stratify=y_all)
    X_pool, y_pool = X_all.iloc[idx_pool].reset_index(drop=True), y_all[idx_pool]
    X_test, y_test = X_all.iloc[idx_test].reset_index(drop=True), y_all[idx_test]

    print(f"训练池 n={len(y_pool)}　固定测试集 n={len(y_test)}"
          f"（各类：{dict(zip(LABELS, np.bincount(y_test)))}）")

    X_median = X_pool.fillna(X_pool.median())
    penalty, C, loss = select_penalty(X_median, y_pool, SEED)
    print(f"惩罚强度：{penalty}, C={C}（在训练池全量上选定一次，log-loss {loss:.4f}）")

    rows = []
    total = len(fractions) * R
    done = 0
    for fi, frac in enumerate(fractions):
        n = int(round(frac * len(y_pool)))
        for r in range(R):
            seed = SEED + fi * 1000 + r
            rng = np.random.default_rng(seed)
            sub_idx = stratified_subsample(y_pool, n, rng)
            Xtr, ytr = X_pool.iloc[sub_idx], y_pool[sub_idx]

            proba = fit_eval(Xtr, ytr, X_test, penalty, C, seed)
            aucs = one_vs_rest_auc(y_test, proba)
            for k, label in enumerate(LABELS):
                rows.append({"fraction": frac, "n": n, "repeat": r,
                            "class": label, "auc": aucs[k]})
            rows.append({"fraction": frac, "n": n, "repeat": r,
                        "class": "宏平均", "auc": float(np.mean(aucs))})

            done += 1
            print(f"  [{done}/{total}] fraction={frac:.2f} n={n} repeat={r}"
                  f"　宏平均 AUC {np.mean(aucs):.3f}")

    result = pd.DataFrame(rows)
    os.makedirs("outputs", exist_ok=True)
    result.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    meta = {
        "n_pool": len(y_pool), "n_test": len(y_test),
        "penalty": penalty, "C": C, "fractions": [float(f) for f in fractions],
        "repeats": R,
    }
    with open(OUT_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    write_report_and_figure(result, meta)
    print(f"已写入 {OUT_CSV} 与 {OUT_META}")



if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
最小样本量核算（Riley 等的标准，多分类按 Pate/Riley 的成对做法）。

用法:
    python3 scripts/definitive_analysis.py    # 先跑，产出 outputs/predictions.csv
    python3 scripts/sample_size.py

输出:
    outputs/sample_size.txt

**这是事后核算，不是事前估算。** 队列已经固定（十年全部住院，n=1238），样本量
不是设计出来的。所以本脚本回答的是审稿人真正会问的那个问题：**以现有事件数，
这个预测因子数目是否站得住**——而不是假装我们事先算过。正文须照此措辞。

多分类没有单一公式。按 Pate 与 Riley 的做法拆成三组成对比较（观察vs内镜、
观察vs手术、内镜vs手术），对每一组套用二分类的三条准则，取最严的一组倒推
全队列所需例数。最严的必然是含手术的那两组——手术仅 135 例。

三条准则（δ 均取 0.05）：
  1  期望收缩系数 S ≥ 0.9，即过拟合造成的系数收缩不超过 10%
  2  表观与校正后 Nagelkerke R² 之差 ≤ 0.05
  3  结局比例的 95% CI 半宽 ≤ 0.05

**R² 取交叉验证值而非表观值。** 表观 Cox-Snell R² 必然乐观，拿它去算样本量
会算出偏小的需求——等于用被高估的效能为偏小的样本背书。这里用
outputs/predictions.csv 的 cv 概率算，成对比较的模型概率取 p_j/(p_j+p_k)。
两个值都打印，差距本身也是要交代的信息。
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PRED = "outputs/predictions.csv"
COHORT = "outputs/cohort.csv"
OUT = "outputs/sample_size.txt"

LABELS = ["观察", "内镜", "手术"]
PCOLS = ["p_obs", "p_endo", "p_surg"]
SHRINKAGE = 0.90          # 准则 1
DELTA_R2 = 0.05           # 准则 2
DELTA_PHI = 0.05          # 准则 3，95% CI 半宽
EPS = 1e-12


def cox_snell(y, p):
    """Cox-Snell R²：1 − (L_null / L_model)^(2/n)。

    y 为 0/1，p 为模型给出的 P(y=1)。零模型取观测比例。
    """
    n = len(y)
    p = np.clip(p, EPS, 1 - EPS)
    phi = np.clip(y.mean(), EPS, 1 - EPS)
    ll_model = np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))
    ll_null = n * (phi * np.log(phi) + (1 - phi) * np.log(1 - phi))
    return 1 - np.exp(2 * (ll_null - ll_model) / n), ll_model, ll_null


def max_cox_snell(phi):
    """Cox-Snell R² 的上界——它达不到 1，故 Nagelkerke 要除以它。"""
    phi = np.clip(phi, EPS, 1 - EPS)
    return 1 - np.exp(2 * (phi * np.log(phi) + (1 - phi) * np.log(1 - phi)))


def n_for_shrinkage(p_params, r2_cs, S):
    """Riley 准则 1/2 共用的式子：n = p / ((S−1) ln(1 − R²/S))。"""
    if r2_cs <= 0 or r2_cs >= S:
        return np.inf
    return p_params / ((S - 1) * np.log(1 - r2_cs / S))


def criteria(p_params, r2_cs, phi):
    """三条准则各自所需的例数。"""
    r2_max = max_cox_snell(phi)
    n1 = n_for_shrinkage(p_params, r2_cs, SHRINKAGE)
    # 准则 2 先由容许的 R² 差额反解出对应的收缩系数
    s2 = r2_cs / (r2_cs + DELTA_R2 * r2_max) if r2_cs > 0 else np.nan
    n2 = n_for_shrinkage(p_params, r2_cs, s2) if np.isfinite(s2) else np.inf
    n3 = (1.96 / DELTA_PHI) ** 2 * phi * (1 - phi)
    return {"准则1 收缩": n1, "准则2 R²差": n2, "准则3 比例精度": n3,
            "S2": s2, "R2_max": r2_max}


def main():
    for f in (PRED, COHORT):
        if not os.path.exists(f):
            sys.exit(f"缺少 {f}——先跑 python3 scripts/definitive_analysis.py")

    from definitive_analysis import feature_columns

    cohort = pd.read_csv(COHORT)
    p_params = len(feature_columns(cohort))
    pred = pd.read_csv(PRED)

    L = []
    a = L.append
    a("=" * 78)
    a("最小样本量核算（Riley 等的标准；多分类按 Pate/Riley 的成对做法）")
    a("=" * 78)
    a(f"实际队列 n={len(cohort)}　预测因子参数 p={p_params}")
    a(f"各类例数：" + "　".join(
        f"{l} {int((cohort['label'] == k).sum())}" for k, l in enumerate(LABELS)))
    a("")
    a("这是事后核算，不是事前估算——队列为十年全部住院，样本量不是设计出来的。")
    a("回答的是「以现有事件数，这个预测因子数目是否站得住」。")
    a("")

    rows = []
    for which, tag in (("cv", "交叉验证（主报告）"), ("apparent", "表观（对照，偏乐观）")):
        d = pred[pred["set"] == which]
        if d.empty:
            continue
        y_all = d["label"].to_numpy()
        P = d[PCOLS].to_numpy()

        a("-" * 78)
        a(f"R² 来源：{tag}")
        a("-" * 78)
        worst = (0.0, None)
        for j in range(3):
            for k in range(j + 1, 3):
                m = (y_all == j) | (y_all == k)
                n_pair = int(m.sum())
                # 成对比较的模型概率：在两类之内重新归一
                denom = P[m, j] + P[m, k]
                p_j = np.where(denom > EPS, P[m, j] / np.maximum(denom, EPS), 0.5)
                y = (y_all[m] == j).astype(float)

                r2, _, _ = cox_snell(y, p_j)
                phi = y.mean()
                c = criteria(p_params, r2, phi)
                need_pair = max(c["准则1 收缩"], c["准则2 R²差"], c["准则3 比例精度"])
                frac = n_pair / len(cohort)
                need_total = need_pair / frac

                a(f"  {LABELS[j]} vs {LABELS[k]}：n={n_pair}（占全队列 {frac*100:.1f}%）"
                  f"　φ={phi:.3f}　Cox-Snell R²={r2:.4f}（上界 {c['R2_max']:.3f}）")
                a(f"    准则1 收缩 S≥{SHRINKAGE}          需 {c['准则1 收缩']:7.0f}")
                a(f"    准则2 R² 差 ≤{DELTA_R2}（S={c['S2']:.3f}） 需 {c['准则2 R²差']:7.0f}")
                a(f"    准则3 比例 95%CI 半宽 ≤{DELTA_PHI}  需 {c['准则3 比例精度']:7.0f}")
                a(f"    -> 该组需 {need_pair:.0f} 例，折合全队列需 {need_total:.0f} 例"
                  f"　实际 {n_pair} 例　{'✓ 满足' if n_pair >= need_pair else '✗ 不足'}")
                a("")
                if need_total > worst[0]:
                    worst = (need_total, f"{LABELS[j]} vs {LABELS[k]}")
                if which == "cv":
                    rows.append({"比较": f"{LABELS[j]} vs {LABELS[k]}", "n": n_pair,
                                 "phi": phi, "R2_CS": r2, "需该组": need_pair,
                                 "折合全队列": need_total, "满足": n_pair >= need_pair})

        a(f"  最严的一组是 {worst[1]}，折合全队列需 {worst[0]:.0f} 例，"
          f"实际 {len(cohort)} 例　{'✓ 满足' if len(cohort) >= worst[0] else '✗ 不足'}")
        a("")

    # 事件数与参数数之比，作为描述性对照
    a("-" * 78)
    a("每参数事件数（EPP，描述性对照，非判定标准）")
    a("-" * 78)
    for k, l in enumerate(LABELS):
        n_k = int((cohort["label"] == k).sum())
        a(f"  {l:<4} {n_k:>4} 例 / {p_params} 参数 = {n_k / p_params:.1f}")
    a("  注：EPP 的经验阈值（10 或 20）已被 Riley 等证明过于粗糙，此处仅作对照。")
    a("      手术组 EPP 最低，正是上面成对核算中最严的那一组。")
    a("")
    a("=" * 78)

    report = "\n".join(L)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print(report)
    print(f"\n已写入 {OUT}")


if __name__ == "__main__":
    main()

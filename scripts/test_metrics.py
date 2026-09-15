# -*- coding: utf-8 -*-
"""指标实现的构造数据验证。多分类指标无现成实现，必须逐个钉住。"""
import sys

import numpy as np

sys.path.insert(0, "scripts")
from metrics import (calibration_slope_intercept, macro_auc, multiclass_brier,  # noqa: E402
                     net_benefit, pdi)

rng = np.random.default_rng(0)


def approx(a, b, tol=0.02):
    return abs(a - b) <= tol


def run():
    n = 3000
    y = rng.integers(0, 3, n)

    # 1a. 概率全部并列：K 路并列随机定序，应得 1/K
    flat = np.full((n, 3), 1 / 3)
    v, _ = pdi(y, flat)
    assert approx(v, 1 / 3), f"全并列时 PDI 应为 1/3，实得 {v}"
    print(f"  OK  PDI 全部并列 = {v:.3f}（理论 0.333，逐对连乘会误得 0.25）")

    # 1b. 概率随机、与真值无关：同样应得 1/K
    noise = rng.uniform(size=(n, 3))
    noise /= noise.sum(1, keepdims=True)
    v, _ = pdi(y, noise)
    assert approx(v, 1 / 3, 0.03), f"随机概率时 PDI 应约 1/3，实得 {v}"
    print(f"  OK  PDI 随机概率 = {v:.3f}（理论 0.333）")

    # 2. 完美判别：真类概率恒为 1
    perfect = np.zeros((n, 3))
    perfect[np.arange(n), y] = 1.0
    v, _ = pdi(y, perfect)
    assert approx(v, 1.0), f"完美判别时 PDI 应为 1，实得 {v}"
    assert approx(macro_auc(y, perfect), 1.0)
    assert approx(multiclass_brier(y, perfect), 0.0)
    print(f"  OK  PDI 完美判别 = {v:.3f}；macro AUC = 1.000；Brier = 0.000")

    # 3. PDI 应随判别力单调上升
    prev = 0
    for strength in (0.0, 0.5, 1.5, 4.0):
        logits = rng.normal(size=(n, 3))
        logits[np.arange(n), y] += strength
        p = np.exp(logits) / np.exp(logits).sum(1, keepdims=True)
        v, _ = pdi(y, p)
        assert v >= prev - 0.01, "PDI 未随判别力单调上升"
        prev = v
        print(f"  OK  信号强度 {strength:>3} -> PDI {v:.3f}, macro AUC {macro_auc(y, p):.3f}")

    # 4. 校准：类别 0 的概率恰为真实发生概率 -> 斜率 1、截距 0
    p0 = rng.uniform(0.05, 0.95, n)
    occurred = (rng.uniform(size=n) < p0).astype(int)      # 1 表示类别 0 发生
    y_cal = np.where(occurred == 1, 0, 1)                  # 类别 0 或 1
    proba = np.column_stack([p0, 1 - p0, np.zeros(n)])
    slope, intercept = calibration_slope_intercept(y_cal, proba)[0]
    assert approx(slope, 1.0, 0.12), f"完美校准的斜率应约为 1，实得 {slope}"
    assert approx(intercept, 0.0, 0.12), f"完美校准的截距应约为 0，实得 {intercept}"
    print(f"  OK  完美校准 -> 斜率 {slope:.3f}（理想 1）、截距 {intercept:.3f}（理想 0）")

    # 5. 把类别 0 的概率整体抬高 0.15（系统性高估）-> 截距应为负
    over = np.clip(p0 + 0.15, 0.01, 0.99)
    proba_o = np.column_stack([over, 1 - over, np.zeros(n)])
    _, inter_o = calibration_slope_intercept(y_cal, proba_o)[0]
    assert inter_o < -0.1, f"系统性高估时截距应明显为负，实得 {inter_o}"
    print(f"  OK  概率整体高估 0.15 -> 截距 {inter_o:.3f}（应为负）")

    # 5b. 反向：整体压低 0.15 -> 截距应为正
    under = np.clip(p0 - 0.15, 0.01, 0.99)
    proba_u = np.column_stack([under, 1 - under, np.zeros(n)])
    _, inter_u = calibration_slope_intercept(y_cal, proba_u)[0]
    assert inter_u > 0.1, f"系统性低估时截距应明显为正，实得 {inter_u}"
    print(f"  OK  概率整体低估 0.15 -> 截距 {inter_u:.3f}（应为正）")

    # 6. 净获益：阈值等于患病率时 treat-all 的净获益应为 0
    y3 = rng.integers(0, 3, n)
    p3 = np.full((n, 3), 1 / 3)
    prev = (y3 == 0).mean()
    _, all_nb = net_benefit(y3, p3, 0, [prev])
    assert approx(all_nb[0], 0.0, 0.01), f"阈值=患病率时 treat-all 净获益应为 0，实得 {all_nb[0]}"
    print(f"  OK  阈值=患病率({prev:.3f}) -> treat-all 净获益 {all_nb[0]:.4f}（理论 0）")

    # 7. 完美模型的净获益应等于患病率（阈值趋近 0 时）
    perfect3 = np.zeros((n, 3))
    perfect3[np.arange(n), y3] = 1.0
    m_nb, _ = net_benefit(y3, perfect3, 0, [0.5])
    assert approx(m_nb[0], (y3 == 0).mean(), 0.01)
    print(f"  OK  完美模型净获益 {m_nb[0]:.3f} = 患病率 {(y3 == 0).mean():.3f}")

    print("\n全部通过")


if __name__ == "__main__":
    run()

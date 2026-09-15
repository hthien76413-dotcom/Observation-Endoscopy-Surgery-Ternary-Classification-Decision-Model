# -*- coding: utf-8 -*-
"""三分类预测模型的评价指标。

与二分类不同，多分类的判别、校准与净获益都没有现成实现，
故在此自行实现并以构造数据验证（见 scripts/test_metrics.py）。
"""
import numpy as np
from sklearn.metrics import roc_auc_score

N_CLASSES = 3


def one_vs_rest_auc(y, proba):
    """逐类 one-vs-rest AUC。"""
    return [roc_auc_score((y == k).astype(int), proba[:, k]) for k in range(proba.shape[1])]


def macro_auc(y, proba):
    return float(np.mean(one_vs_rest_auc(y, proba)))


def micro_auc(y, proba):
    """把所有类别的 (真值, 预测) 对拉平后算单一 AUC。"""
    k = proba.shape[1]
    flat_y = np.concatenate([(y == c).astype(int) for c in range(k)])
    flat_p = np.concatenate([proba[:, c] for c in range(k)])
    return float(roc_auc_score(flat_y, flat_p))


def multiclass_brier(y, proba):
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y)), y] = 1
    return float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))


def pdi(y, proba):
    """多分类判别指数 (Polytomous Discrimination Index, Van Calster 等)。

    定义：各类随机取一例，真正属于类 k 的那一例其 p_k 最高的概率，
    再对各类求平均。无判别力时等于 1/K。

    并列的处理是关键。若按「逐对比较各记 0.5 再连乘」，全部并列时
    K=3 会得到 0.5²=0.25，而不是应有的 1/3——因为各次比较在并列时并不独立。
    这里按 K 路并列随机定序计算精确概率：设与第 i 例并列的其他类集合为 S，
    该情形下 i 胜出的概率为 1/(|S|+1)，对所有 S 求和。
    """
    from itertools import combinations

    k = proba.shape[1]
    per_class = []
    for c in range(k):
        idx_c = np.where(y == c)[0]
        others = [o for o in range(k) if o != c]
        if len(idx_c) == 0 or any(np.sum(y == o) == 0 for o in others):
            per_class.append(np.nan)
            continue

        p_self = proba[idx_c, c]
        lower, tied = {}, {}
        for o in others:
            p_o = np.sort(proba[y == o, c])
            lo = np.searchsorted(p_o, p_self, side="left")
            hi = np.searchsorted(p_o, p_self, side="right")
            lower[o] = lo / len(p_o)
            tied[o] = (hi - lo) / len(p_o)

        total = np.zeros(len(idx_c))
        for size in range(len(others) + 1):
            for subset in combinations(others, size):
                term = np.ones(len(idx_c))
                for o in others:
                    term *= tied[o] if o in subset else lower[o]
                total += term / (size + 1)
        per_class.append(float(np.mean(total)))
    return float(np.nanmean(per_class)), per_class


def _logit(p, eps=1e-6):
    p = np.clip(p, eps, 1 - eps)
    return np.log(p / (1 - p))


def calibration_slope_intercept(y, proba):
    """逐类校准斜率与截距。

    斜率：以 logit(p_k) 为唯一自变量做 logistic 回归，系数即斜率（理想为 1）。
    截距：固定斜率为 1（把 logit(p_k) 作为 offset）后拟合的截距（理想为 0）。
    """
    from sklearn.linear_model import LogisticRegression

    out = []
    for c in range(proba.shape[1]):
        target = (y == c).astype(int)
        lp = _logit(proba[:, c]).reshape(-1, 1)
        if target.sum() in (0, len(target)):
            out.append((np.nan, np.nan))
            continue
        slope = LogisticRegression(C=np.inf, max_iter=1000).fit(lp, target).coef_[0][0]
        intercept = _fit_offset_intercept(target, lp.ravel())
        out.append((float(slope), float(intercept)))
    return out


def _fit_offset_intercept(target, offset, iters=100, tol=1e-10):
    """以 offset 固定斜率为 1，用 Newton 法求截距。"""
    a = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(a + offset)))
        grad = np.sum(target - p)
        hess = -np.sum(p * (1 - p))
        if abs(hess) < 1e-12:
            break
        step = grad / hess
        a -= step
        if abs(step) < tol:
            break
    return a


def calibration_curve_points(y, proba, cls, n_bins=10):
    """等频分箱的校准曲线点：(预测均值, 实际比例, 例数)。"""
    p = proba[:, cls]
    target = (y == cls).astype(int)
    order = np.argsort(p)
    bins = np.array_split(order, n_bins)
    pts = []
    for b in bins:
        if len(b) == 0:
            continue
        pts.append((float(p[b].mean()), float(target[b].mean()), int(len(b))))
    return pts


def net_benefit(y, proba, cls, thresholds):
    """某一类别的净获益（one-vs-rest）。

    NB(t) = TP/n − FP/n × t/(1−t)，p_k ≥ t 判为阳性。
    同时给出 treat-all（全部按该类处理）与 treat-none（恒为 0）作参照。
    """
    n = len(y)
    target = (y == cls).astype(int)
    p = proba[:, cls]
    prevalence = target.mean()

    model, treat_all = [], []
    for t in thresholds:
        w = t / (1 - t) if t < 1 else np.inf
        pred = p >= t
        tp = float(np.sum(pred & (target == 1)))
        fp = float(np.sum(pred & (target == 0)))
        model.append(tp / n - fp / n * w)
        treat_all.append(prevalence - (1 - prevalence) * w)
    return np.array(model), np.array(treat_all)


def linear_shap(coefs, intercepts, X, feature_names, class_index):
    """线性模型的精确 SHAP 值：φ_j = β_j × (x_j − mean(x_j))。

    多分类 logistic 的对数几率是线性的，故不必用近似算法，
    也就不必引入 shap 依赖。返回 (每例每特征的贡献, 平均绝对贡献)。
    """
    beta = np.asarray(coefs)[class_index]
    centred = X - X.mean(axis=0)
    contrib = centred * beta
    importance = dict(zip(feature_names, np.abs(contrib).mean(axis=0)))
    return contrib, importance

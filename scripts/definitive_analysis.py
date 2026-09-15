# -*- coding: utf-8 -*-
"""
正式分析流水线：多重插补 + 惩罚多分类回归 + Bootstrap 乐观度校正 + 时间验证。

用法:
    python3 scripts/definitive_analysis.py [--imputations 20] [--bootstrap 500] [--quick]

输出:
    outputs/definitive_results.txt     完整文字报告
    outputs/model_coefficients.csv     Rubin 规则合并后的系数
    outputs/predictions.csv            逐例预测概率（表观 / 交叉验证 / 时间验证）
    outputs/figures/*.png              诊断用图（正式图件见 build_figure4.py 等）

与预试验（scripts/pilot_model.py）的区别——预试验用 5 折交叉验证 + 中位数填补，
只为估计可行性；本脚本才是论文的正式分析：

  插补    链式方程多重插补，m 份；插补模型纳入结局（Moons 等的建议），
          但时间验证集不纳入结局，以匹配真实部署场景
  建模    惩罚多分类 logistic 回归，惩罚强度由交叉验证选定
  内部验证 Harrell Bootstrap 乐观度校正
  合并    系数按 Rubin 规则合并；效能指标在各插补集上计算后取平均
"""
import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, "scripts")
from metrics import (calibration_curve_points, calibration_slope_intercept,  # noqa: E402
                     linear_shap, macro_auc, micro_auc, multiclass_brier,
                     net_benefit, one_vs_rest_auc, pdi)

warnings.filterwarnings("ignore")

LABELS = ["观察", "内镜", "手术"]
SEED = 20260914
TEMPORAL_SPLIT_YEAR = 2023          # <= 建模，> 验证
C_GRID = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]
THRESHOLDS = np.arange(0.01, 0.80, 0.01)

BASE = ["age_years", "male", "weight_kg", "temp_c", "log_ingest_hours"]
SYMPTOMS = ["sym_abdpain", "sym_vomit", "sym_hematemesis", "sym_fever",
            "sym_dysphagia", "sym_distension", "sign_tenderness", "sign_peritoneal"]
LABS = ["lab_wbc", "lab_neut_pct", "lab_alb"]


def feature_columns(df):
    """自动纳入已有的异物类型与影像列——重标注数据并入后无需改脚本。"""
    fb = [c for c in df.columns if c.startswith("fb_")]
    imaging = [c for c in df.columns
               if c.startswith(("loc_", "xray_"))
               and c not in ("xray_phase",)
               and pd.api.types.is_numeric_dtype(df[c])]
    feats = BASE + fb + SYMPTOMS + imaging + LABS
    return [c for c in feats if c in df.columns]


# --------------------------------------------------------------------------
# 插补
# --------------------------------------------------------------------------
def observed_bounds(block):
    """每个变量的观测最小/最大值，用作插补取值的上下界。

    sample_posterior=True 是从无界正态后验抽样，会抽出临床上不可能的值：
    实测出现过负体重、负白细胞、−13% 与 109% 的中性粒细胞比例
    （11220 个插补值里 20 个，0.18%）。对模型影响可忽略，但补充图 S1
    一画出来就看得见，审稿人会问。

    夹到观测范围内是 MICE 的常规做法，也不必为每个变量维护一张临床阈值表；
    代价是插补值不会比观测到的任何一例更极端，在本队列（n=1238、缺失
    11–21%）观测范围已足够充分，这个代价可以接受。

    二分类列与结局列的观测范围本身就是 0/1，无须特殊处理。
    """
    lo = block.min(axis=0).to_numpy(dtype=float)
    hi = block.max(axis=0).to_numpy(dtype=float)
    # 整列缺失时 min/max 为 NaN，退回无界，否则 sklearn 会报错
    lo = np.where(np.isnan(lo), -np.inf, lo)
    hi = np.where(np.isnan(hi), np.inf, hi)
    # 常量列会使 min == max，sklearn 要求严格小于。时间验证子集里
    # sym_dysphagia 恒为 0 即属此列（它本身没有缺失，但边界仍要通过校验）。
    flat = hi <= lo
    hi = np.where(flat, lo + np.maximum(np.abs(lo), 1.0) * 1e-6, hi)
    return lo, hi


def impute(X, y, n_imputations, seed, include_outcome=True):
    """链式方程多重插补。

    插补模型纳入结局可减少偏倚（结局与缺失相关时尤其重要，本队列正是如此）；
    预测时不使用结局，故不构成泄漏。时间验证集按部署场景不纳入结局。
    """
    out = []
    for i in range(n_imputations):
        block = X.copy()
        if include_outcome and y is not None:
            for k in range(len(LABELS)):
                block[f"__y{k}"] = (y == k).astype(float)
        lo, hi = observed_bounds(block)
        imputer = IterativeImputer(max_iter=10, sample_posterior=True,
                                   min_value=lo, max_value=hi,
                                   random_state=seed + i)
        filled = pd.DataFrame(imputer.fit_transform(block), columns=block.columns,
                              index=block.index)
        out.append(filled[X.columns])
    return out


# --------------------------------------------------------------------------
# 建模
# --------------------------------------------------------------------------
def select_penalty(X, y, seed):
    """交叉验证选择惩罚强度与类型，以多分类 log-loss 为准则。"""
    from sklearn.metrics import log_loss

    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    best = (np.inf, "l2", 1.0)
    for penalty in ("l2", "l1"):
        for C in C_GRID:
            losses = []
            for tr, te in cv.split(X, y):
                sc = StandardScaler().fit(X.iloc[tr])
                clf = LogisticRegression(
                    penalty=penalty, C=C, max_iter=5000,
                    solver="saga" if penalty == "l1" else "lbfgs")
                clf.fit(sc.transform(X.iloc[tr]), y[tr])
                losses.append(log_loss(y[te], clf.predict_proba(sc.transform(X.iloc[te])),
                                       labels=[0, 1, 2]))
            mean_loss = float(np.mean(losses))
            if mean_loss < best[0]:
                best = (mean_loss, penalty, C)
    return best[1], best[2], best[0]


def fit_model(X, y, penalty, C):
    scaler = StandardScaler().fit(X)
    clf = LogisticRegression(penalty=penalty, C=C, max_iter=5000,
                             solver="saga" if penalty == "l1" else "lbfgs")
    clf.fit(scaler.transform(X), y)
    return scaler, clf


def performance(y, proba):
    aucs = one_vs_rest_auc(y, proba)
    pdi_value, pdi_per_class = pdi(y, proba)
    return {
        "auc_观察": aucs[0], "auc_内镜": aucs[1], "auc_手术": aucs[2],
        "macro_auc": float(np.mean(aucs)), "micro_auc": micro_auc(y, proba),
        "pdi": pdi_value, "brier": multiclass_brier(y, proba),
    }


# --------------------------------------------------------------------------
# Bootstrap 乐观度校正
# --------------------------------------------------------------------------
def bootstrap_optimism(X, y, penalty, C, n_boot, seed):
    """Harrell 法：乐观度 = 自助样本上的表现 − 同一模型在原样本上的表现。

    惩罚强度在全样本上选定后固定，未纳入自助循环——这会略微低估乐观度，
    须在正文交代。把交叉验证选参也放进循环的计算量是其数十倍。
    """
    rng = np.random.default_rng(seed)
    keys = ["macro_auc", "pdi", "brier"]
    optimism = {k: [] for k in keys}

    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < len(LABELS):
            continue
        sc, clf = fit_model(X.iloc[idx], y[idx], penalty, C)
        p_boot = clf.predict_proba(sc.transform(X.iloc[idx]))
        p_orig = clf.predict_proba(sc.transform(X))
        b, o = performance(y[idx], p_boot), performance(y, p_orig)
        for k in keys:
            optimism[k].append(b[k] - o[k])
    return {k: float(np.mean(v)) if v else np.nan for k, v in optimism.items()}


def cross_validated_proba(X, y, penalty, C, m_cv, seed, n_splits=5):
    """折内插补的交叉验证预测概率。

    插补器只在训练折上拟合，再变换验证折；验证折不纳入结局。
    如此避免了「先在全样本插补、再交叉验证」造成的跨折信息流动。
    """
    proba = np.zeros((len(y), len(LABELS)))
    cv = StratifiedKFold(n_splits, shuffle=True, random_state=seed)
    for tr, te in cv.split(X, y):
        Xtr, Xte, ytr = X.iloc[tr], X.iloc[te], y[tr]
        fold = np.zeros((len(te), len(LABELS)))
        for i in range(m_cv):
            block = Xtr.copy()
            for k in range(len(LABELS)):
                block[f"__y{k}"] = (ytr == k).astype(float)
            lo, hi = observed_bounds(block)      # 只用训练折的范围，避免跨折泄漏
            imp = IterativeImputer(max_iter=10, sample_posterior=True,
                                   min_value=lo, max_value=hi,
                                   random_state=seed + i)
            imp.fit(block)
            tr_filled = pd.DataFrame(imp.transform(block), columns=block.columns,
                                     index=Xtr.index)[X.columns]
            # 验证折不带结局列：用训练折的均值占位，仅为满足列结构，
            # 插补器对这些列的输出被丢弃。
            te_block = Xte.copy()
            for k in range(len(LABELS)):
                te_block[f"__y{k}"] = np.nan
            te_filled = pd.DataFrame(imp.transform(te_block), columns=block.columns,
                                     index=Xte.index)[X.columns]
            sc, clf = fit_model(tr_filled, ytr, penalty, C)
            fold += clf.predict_proba(sc.transform(te_filled))
        proba[te] = fold / m_cv
    return proba


# --------------------------------------------------------------------------
# Rubin 规则
# --------------------------------------------------------------------------
def pool_coefficients(fits, feature_names):
    """按 Rubin 规则合并各插补集的系数。

    总方差 = 组内方差 + (1 + 1/m) × 组间方差。此处未对每次拟合估计标准误
    （惩罚回归的标准误本身有争议），故仅报告点估计与组间离散度。
    """
    rows = []
    coefs = np.array([f.coef_ for _, f in fits])         # (m, classes, features)
    for k, label in enumerate(LABELS):
        for j, name in enumerate(feature_names):
            values = coefs[:, k, j]
            rows.append({"类别": label, "变量": name,
                         "系数": float(values.mean()),
                         "OR": float(np.exp(values.mean())),
                         "插补间SD": float(values.std(ddof=1)) if len(values) > 1 else 0.0})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 预测概率落盘
# --------------------------------------------------------------------------
def save_predictions(blocks, path):
    """把逐例预测概率写出，供作图脚本读取。

    三套概率的含义完全不同，混用会让图与正文对不上，故用 set 列区分：

      apparent  模型在自己的训练数据上预测——必然乐观，只作诊断，不可入稿
      cv        折内插补的 5 折交叉验证——**内部效能的主报告值，Fig 4 用这个**
      temporal  2024 年以后的独立时段——时间外部验证

    分开落盘而非只存一套，是为了让作图脚本无法「随手拿错那一套」：
    取哪一套必须在代码里写明 set 值。
    """
    rows = []
    for name, y_true, proba in blocks:
        for i in range(len(y_true)):
            rows.append({"set": name, "label": int(y_true[i]),
                         "p_obs": proba[i, 0], "p_endo": proba[i, 1],
                         "p_surg": proba[i, 2]})
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


# --------------------------------------------------------------------------
# 图
# --------------------------------------------------------------------------
# 图件进入英文稿件，故图内一律用英文标签；
# matplotlib 亦无 CJK 字体，中文会渲染成方框。
FIG_LABELS = ["Observation", "Endoscopy", "Surgery"]


def make_figures(y, proba, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve

    os.makedirs(outdir, exist_ok=True)
    colors = ["#5C8A1E", "#0A7EA4", "#BE3241"]
    plt.rcParams.update({"font.size": 9, "figure.dpi": 200})

    # 这张 ROC 画的是表观概率（模型在自己的训练数据上预测），必然乐观，
    # 只作诊断。稿件用的 Fig 4 由 scripts/build_figure4.py 从交叉验证与
    # 时间验证的概率作图。文件名与标题都写明，免得被顺手贴进稿件。
    fig, ax = plt.subplots(figsize=(4.2, 4.4))
    for k, label in enumerate(FIG_LABELS):
        fpr, tpr, _ = roc_curve((y == k).astype(int), proba[:, k])
        auc = one_vs_rest_auc(y, proba)[k]
        ax.plot(fpr, tpr, color=colors[k], lw=1.6,
                label=f"{label} (AUC {auc:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set_xlabel("1 − Specificity"); ax.set_ylabel("Sensitivity")
    ax.set_title("APPARENT (in-sample) — diagnostic only\nnot for publication; see Fig 4",
                 fontsize=8, color="#BE3241")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(f"{outdir}/roc_apparent_DIAGNOSTIC.png"); plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.4))
    for k, (ax, label) in enumerate(zip(axes, FIG_LABELS)):
        pts = calibration_curve_points(y, proba, k)
        ax.plot([0, 1], [0, 1], "k--", lw=0.8)
        ax.plot([p for p, _, _ in pts], [o for _, o, _ in pts],
                "o-", color=colors[k], lw=1.4, ms=4)
        slope, intercept = calibration_slope_intercept(y, proba)[k]
        ax.set_title(f"{label}\nslope {slope:.2f}, intercept {intercept:.2f}")
        ax.set_xlabel("Predicted"); ax.set_ylabel("Observed" if k == 0 else "")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(f"{outdir}/calibration.png"); plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.4))
    for k, (ax, label) in enumerate(zip(axes, FIG_LABELS)):
        nb, all_nb = net_benefit(y, proba, k, THRESHOLDS)
        ax.plot(THRESHOLDS, nb, color=colors[k], lw=1.6, label="Model")
        ax.plot(THRESHOLDS, all_nb, color="0.5", lw=1.0, label="Treat all")
        ax.axhline(0, color="k", lw=0.8, label="Treat none")
        ax.set_ylim(min(-0.02, float(nb.min()) * 0.5), max(0.05, float(nb.max()) * 1.2))
        ax.set_title(label); ax.set_xlabel("Threshold probability")
        ax.set_ylabel("Net benefit" if k == 0 else "")
        if k == 0:
            ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(f"{outdir}/decision_curve.png"); plt.close(fig)


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imputations", type=int, default=20)
    ap.add_argument("--bootstrap", type=int, default=500)
    ap.add_argument("--quick", action="store_true", help="m=3, B=50，供冒烟测试")
    args = ap.parse_args()
    m = 3 if args.quick else args.imputations
    n_boot = 50 if args.quick else args.bootstrap

    os.makedirs("outputs/figures", exist_ok=True)
    df = pd.read_csv("outputs/cohort.csv")
    feats = feature_columns(df)
    y = df["label"].to_numpy()
    X = df[feats]

    L = []
    a = L.append
    a("=" * 78)
    a("正式分析：多重插补 + 惩罚多分类回归 + Bootstrap 乐观度校正")
    a("=" * 78)
    a(f"样本 {len(y)}　分组 {dict(zip(LABELS, np.bincount(y)))}")
    a(f"预测因子 {len(feats)} 个　插补 m={m}　自助 B={n_boot}")
    a(f"缺失率 >0 的变量：{int((X.isna().mean() > 0).sum())}")
    a("")

    a("-" * 78)
    a("一、惩罚强度选择（交叉验证，准则为多分类 log-loss）")
    a("-" * 78)
    X_median = X.fillna(X.median())
    penalty, C, loss = select_penalty(X_median, y, SEED)
    a(f"  选定：penalty={penalty}, C={C}（log-loss {loss:.4f}）")
    a("  说明：在中位数填补的数据上选参，再固定用于各插补集，")
    a("        以避免 m×网格×交叉验证的计算量。")
    a("")

    a("-" * 78)
    a(f"二、多重插补（m={m}，插补模型纳入结局）")
    a("-" * 78)
    imputed = impute(X, y, m, SEED, include_outcome=True)
    a(f"  完成 {len(imputed)} 份插补数据集")
    a("")

    a("-" * 78)
    a("三、表观效能（各插补集平均）")
    a("-" * 78)
    fits, probas, perfs = [], [], []
    for Xi in imputed:
        sc, clf = fit_model(Xi, y, penalty, C)
        fits.append((sc, clf))
        p = clf.predict_proba(sc.transform(Xi))
        probas.append(p)
        perfs.append(performance(y, p))
    mean_proba = np.mean(probas, axis=0)
    apparent = {k: float(np.mean([p[k] for p in perfs])) for k in perfs[0]}
    for k, v in apparent.items():
        spread = np.std([p[k] for p in perfs], ddof=1) if len(perfs) > 1 else 0
        a(f"  {k:<12} {v:.4f}　（插补间 SD {spread:.4f}）")
    a("")

    a("-" * 78)
    a(f"四、Bootstrap 乐观度校正（B={n_boot}，在第 1 份插补集上）")
    a("-" * 78)
    opt = bootstrap_optimism(imputed[0], y, penalty, C, n_boot, SEED)
    for k, v in opt.items():
        corrected = apparent[k] - v
        a(f"  {k:<12} 表观 {apparent[k]:.4f}　乐观度 {v:+.4f}　校正后 {corrected:.4f}")
    a("  说明：惩罚强度在循环外选定，故乐观度略被低估，正文须交代。")
    a("")

    a("-" * 78)
    a("四b、插补泄漏诊断（必读）")
    a("-" * 78)
    a("  插补模型纳入结局可减少系数偏倚，但若只在全样本上插补一次，")
    a("  被插补的预测因子就携带了结局信息；此后的 Bootstrap 不重做插补，")
    a("  校正不到这部分乐观度。下面用「插补不纳入结局」重算表观效能作对照。")
    free = impute(X, None, max(3, m // 4), SEED + 999, include_outcome=False)
    free_perf = []
    for Xi in free:
        sc, clf = fit_model(Xi, y, penalty, C)
        free_perf.append(performance(y, clf.predict_proba(sc.transform(Xi))))
    for k in ("macro_auc", "pdi"):
        with_y = apparent[k]
        without_y = float(np.mean([p[k] for p in free_perf]))
        a(f"  {k:<12} 纳入结局 {with_y:.4f}　不纳入 {without_y:.4f}　"
          f"差 {with_y - without_y:+.4f}")
    gap = apparent["macro_auc"] - float(np.mean([p["macro_auc"] for p in free_perf]))
    if gap > 0.01:
        a("")
        a(f"  -> 差值 {gap:.3f} 不可忽略。正文报告内部效能时应以「不纳入结局的插补」")
        a("     为准，或把插补移入 Bootstrap 循环内重做；纳入结局的插补仅用于估计系数。")
    else:
        a("  -> 差值很小，两种插补方式对效能估计影响有限。")
    a("")
    a("-" * 78)
    a("四c、折内插补的交叉验证（内部效能的主报告值）")
    a("-" * 78)
    a("  每一折只用训练折拟合插补器，再变换验证折；验证折插补不纳入结局。")
    a("  插补、标准化、拟合全部在折内完成，不存在跨折信息流动——")
    a("  这是最保守也最可辩护的内部效能估计。")
    cv_proba = cross_validated_proba(X, y, penalty, C, m_cv=max(3, m // 4), seed=SEED)
    cv_perf = performance(y, cv_proba)
    for k, v in cv_perf.items():
        a(f"  {k:<12} {v:.4f}")
    a("")
    a(f"  对照：表观 {apparent['macro_auc']:.4f}　"
      f"Bootstrap 校正 {apparent['macro_auc'] - opt['macro_auc']:.4f}　"
      f"折内交叉验证 {cv_perf['macro_auc']:.4f}")
    if apparent["macro_auc"] - opt["macro_auc"] - cv_perf["macro_auc"] > 0.01:
        a("  -> Bootstrap 校正值高于交叉验证值。原因是惩罚强度与插补均在循环外完成，")
        a("     乐观度因而被低估。**正文应以折内交叉验证值为内部效能的主报告值。**")
    a("")
    a("-" * 78)
    a("五、校准（各插补集概率平均后计算）")
    a("-" * 78)
    for k, (slope, intercept) in enumerate(calibration_slope_intercept(y, mean_proba)):
        a(f"  {LABELS[k]:<4} 斜率 {slope:.3f}（理想 1）　截距 {intercept:+.3f}（理想 0）")
    a("")

    a("-" * 78)
    a("六、时间外部验证")
    a("-" * 78)
    dev = (df["admit_year"] <= TEMPORAL_SPLIT_YEAR).to_numpy()
    Xd, yd = X[dev], y[dev]
    Xv, yv = X[~dev], y[~dev]
    a(f"  建模 {int(dev.sum())} 例（≤{TEMPORAL_SPLIT_YEAR}）"
      f"　验证 {int((~dev).sum())} 例（>{TEMPORAL_SPLIT_YEAR}）")
    a("  验证集插补不纳入结局，以匹配真实部署场景。")
    dev_imp = impute(Xd, yd, m, SEED, include_outcome=True)
    val_imp = impute(Xv, None, m, SEED, include_outcome=False)
    val_probas = []
    for Xi, Xj in zip(dev_imp, val_imp):
        sc, clf = fit_model(Xi, yd, penalty, C)
        val_probas.append(clf.predict_proba(sc.transform(Xj)))
    val_proba = np.mean(val_probas, axis=0)
    for k, v in performance(yv, val_proba).items():
        a(f"  {k:<12} {v:.4f}")
    for k, (slope, intercept) in enumerate(calibration_slope_intercept(yv, val_proba)):
        a(f"  {LABELS[k]:<4} 校准斜率 {slope:.3f}　截距 {intercept:+.3f}")
    a("")

    save_predictions([("apparent", y, mean_proba),
                      ("cv", y, cv_proba),
                      ("temporal", yv, val_proba)],
                     "outputs/predictions.csv")
    a("  逐例预测概率已写入 outputs/predictions.csv（set 列区分三套）。")
    a("")

    a("-" * 78)
    a("七、系数（Rubin 规则合并）")
    a("-" * 78)
    coef_df = pool_coefficients(fits, feats)
    coef_df.to_csv("outputs/model_coefficients.csv", index=False, encoding="utf-8-sig")
    for label in LABELS:
        top = (coef_df[coef_df["类别"] == label]
               .reindex(coef_df[coef_df["类别"] == label]["系数"].abs()
                        .sort_values(ascending=False).index).head(8))
        a(f"  【{label}】绝对值最大的 8 项：")
        for _, r in top.iterrows():
            a(f"    {r['变量']:<20} β={r['系数']:+.3f}  OR={r['OR']:.3f}"
              f"  (插补间SD {r['插补间SD']:.3f})")
    a("  完整系数表见 outputs/model_coefficients.csv")
    a("")

    a("-" * 78)
    a("八、变量贡献（线性模型的精确 SHAP：β_j ×（x_j − 均值））")
    a("-" * 78)
    sc0, clf0 = fits[0]
    Xs = sc0.transform(imputed[0])
    for k, label in enumerate(LABELS):
        _, imp = linear_shap(clf0.coef_, clf0.intercept_, Xs, feats, k)
        top = sorted(imp.items(), key=lambda x: -x[1])[:6]
        a(f"  【{label}】" + "　".join(f"{n}={v:.3f}" for n, v in top))
    a("")

    make_figures(y, mean_proba, "outputs/figures")
    a("诊断图已输出：outputs/figures/"
      "{roc_apparent_DIAGNOSTIC,calibration,decision_curve}.png")
    a("稿件 Fig 4 由 scripts/build_figure4.py 生成，用的是交叉验证与时间验证的概率。")
    a("=" * 78)

    report = "\n".join(L)
    with open("outputs/definitive_results.txt", "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()

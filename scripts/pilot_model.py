# -*- coding: utf-8 -*-
"""
预试验建模: 评估「观察/内镜/手术」三分类的可判别性，为正式研究提供效能预期。

比较多分类 Logistic 回归与随机森林，报告 one-vs-rest AUC、宏平均 AUC、
多分类 Brier 评分与混淆矩阵。缺失值用中位数填补(正式分析应改用多重插补)。
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

LABELS = {0: "观察", 1: "内镜", 2: "手术"}

BASE_FEATURES = ["age_years", "male", "weight_kg", "temp_c", "log_ingest_hours"]
FB_FEATURES = ["fb_battery", "fb_magnet", "fb_sharp", "fb_coin", "fb_pit", "fb_long",
               "fb_plastic", "fb_multiple"]
SYM_FEATURES = ["sym_abdpain", "sym_vomit", "sym_hematemesis", "sym_fever",
                "sym_dysphagia", "sym_distension", "sign_tenderness", "sign_peritoneal"]
LOC_FEATURES = ["loc_esophagus", "loc_stomach", "loc_duodenum", "loc_smallbowel",
                "loc_colorectal", "xray_radiopaque"]
LAB_FEATURES = ["lab_wbc", "lab_neut_pct", "lab_crp", "lab_alb"]

BLOCKS = {
    "A 人口学+病史": BASE_FEATURES,
    "B +异物类型": BASE_FEATURES + FB_FEATURES,
    "C +症状体征": BASE_FEATURES + FB_FEATURES + SYM_FEATURES,
    "D +影像定位": BASE_FEATURES + FB_FEATURES + SYM_FEATURES + LOC_FEATURES,
    "E +实验室(全模型)": BASE_FEATURES + FB_FEATURES + SYM_FEATURES + LOC_FEATURES + LAB_FEATURES,
}


def multiclass_brier(y, proba):
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y)), y] = 1
    return float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))


def evaluate(name, clf, X, y, cv):
    proba = cross_val_predict(clf, X, y, cv=cv, method="predict_proba")
    aucs = [roc_auc_score((y == k).astype(int), proba[:, k]) for k in range(3)]
    return {
        "模型": name,
        "观察AUC": aucs[0], "内镜AUC": aucs[1], "手术AUC": aucs[2],
        "宏平均AUC": float(np.mean(aucs)),
        "准确率": accuracy_score(y, proba.argmax(1)),
        "Brier": multiclass_brier(y, proba),
    }, proba


# --------------------------------------------------------------------------
# 敏感性分析: 每一项针对一条具体的方法学质疑
# --------------------------------------------------------------------------
FULL = BASE_FEATURES + FB_FEATURES + SYM_FEATURES + LOC_FEATURES + LAB_FEATURES

SENSITIVITY = [
    ("主分析", None, FULL,
     "全队列，缺失以中位数填补"),
    ("S1 仅首次住院", lambda d: d["first_admission"] == 1, FULL,
     "10 例再入院违反观测独立性（审稿质疑 6）"),
    ("S2 剔除全部化验", None, BASE_FEATURES + FB_FEATURES + SYM_FEATURES + LOC_FEATURES,
     "化验可能在决策后抽取（审稿质疑 2）"),
    ("S3 仅有决策前影像者", lambda d: d["has_xray"] == 1, FULL,
     "影像特征非全队列可得，检验其代表性"),
    ("S4 仅决策前化验可用者", lambda d: d["lab_predecision"] == 1, FULL,
     "同上，针对化验"),
    ("S5 完整病例分析", "complete", FULL,
     "不做任何填补（方法学计划要求）"),
    ("S6 剔除 CRP", None,
     BASE_FEATURES + FB_FEATURES + SYM_FEATURES + LOC_FEATURES
     + ["lab_wbc", "lab_neut_pct", "lab_alb"],
     "CRP 缺失 68.7% 且缺失与治疗相关，见缺失机制诊断"),
]


MISSING_CHECK = ["lab_crp", "lab_wbc", "lab_alb", "xray_radiopaque"]


def missingness_diagnostics(df, y, cv_seed=42):
    """检查缺失本身是否携带治疗信息。

    若「做了哪些检查」就能预测治疗方式，说明缺失并非随机，而是医师行为的投影。
    这种情况下中位数填补会把该信号一并带进模型——填补值系统性地偏离观测值，
    模型可借此反推「此人未做该项检查」。正式分析必须用多重插补，
    且插补模型须纳入结局变量；缺失指示变量本身绝不可作为预测因子。
    """
    print("=" * 88)
    print("缺失机制诊断")
    print("=" * 88)
    rate = (df.groupby("label_name")[MISSING_CHECK]
              .apply(lambda g: g.isna().mean() * 100).round(1))
    print("各治疗组的缺失率(%):")
    print(rate.to_string())

    ind = pd.DataFrame({c + "_missing": df[c].isna().astype(int) for c in MISSING_CHECK})
    cv = StratifiedKFold(5, shuffle=True, random_state=cv_seed)
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
    proba = cross_val_predict(clf, ind, y, cv=cv, method="predict_proba")
    aucs = [roc_auc_score((y == k).astype(int), proba[:, k]) for k in range(3)]
    macro = float(np.mean(aucs))
    print(f"\n仅用缺失指示变量（不含任何数值）预测治疗方式:")
    print(f"  观察={aucs[0]:.3f}  内镜={aucs[1]:.3f}  手术={aucs[2]:.3f}  宏平均={macro:.3f}")
    if macro > 0.60:
        print("  -> 缺失显著携带治疗信息。正式分析必须用多重插补（插补模型纳入结局），"
              "不可用单一值填补；缺失指示变量不得作为预测因子。")
    else:
        print("  -> 缺失与治疗方式关联较弱。")
    return macro


def run_sensitivity(df, y_all, cv_seed=42):
    """逐项敏感性分析。

    除效能外还报告「类别偏移」——子集三类构成比与全队列的最大绝对差。
    子集若在治疗分组上严重失衡，其 AUC 不可与主分析直接比较：偏移来自
    选择效应而非模型表现。
    """
    base_prop = np.bincount(y_all, minlength=3) / len(y_all)
    rows = []
    for name, rule, feats, rationale in SENSITIVITY:
        if rule is None:
            mask = pd.Series(True, index=df.index)
        elif rule == "complete":
            mask = df[feats].notna().all(axis=1)
        else:
            mask = rule(df)

        sub, y = df.loc[mask], y_all[mask.to_numpy()]
        counts = np.bincount(y, minlength=3)
        shift = float(np.abs(counts / max(len(y), 1) - base_prop).max())
        if counts.min() < 25:
            rows.append({"分析": name, "n": len(y), "观察/内镜/手术": "/".join(map(str, counts)),
                         "类别偏移": shift, "观察AUC": np.nan, "内镜AUC": np.nan,
                         "手术AUC": np.nan, "宏平均AUC": np.nan,
                         "说明": f"最小类仅 {counts.min()} 例，不足以估计"})
            continue

        X = sub[feats]
        X = X.fillna(X.median())
        clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
        n_splits = min(5, int(counts.min()))
        cv = StratifiedKFold(n_splits, shuffle=True, random_state=cv_seed)
        proba = cross_val_predict(clf, X, y, cv=cv, method="predict_proba")
        aucs = [roc_auc_score((y == k).astype(int), proba[:, k]) for k in range(3)]
        rows.append({"分析": name, "n": len(y), "观察/内镜/手术": "/".join(map(str, counts)),
                     "类别偏移": shift, "观察AUC": aucs[0], "内镜AUC": aucs[1],
                     "手术AUC": aucs[2], "宏平均AUC": float(np.mean(aucs)),
                     "说明": rationale})
    return pd.DataFrame(rows)


def main():
    df = pd.read_csv("outputs/cohort.csv")
    y = df["label"].to_numpy()
    cv = StratifiedKFold(5, shuffle=True, random_state=42)

    print(f"样本量 n={len(y)}   分组 观察/内镜/手术 = {np.bincount(y)}\n")

    print("=" * 88)
    print("变量分层递增: 每一块特征带来的增量价值 (多分类 Logistic, 5 折交叉验证)")
    print("=" * 88)
    rows = []
    for block, feats in BLOCKS.items():
        X = df[feats].fillna(df[feats].median())
        clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
        res, _ = evaluate(block, clf, X, y, cv)
        rows.append(res)
    print(pd.DataFrame(rows).set_index("模型").round(3).to_string())

    full = BLOCKS["E +实验室(全模型)"]
    X = df[full].fillna(df[full].median())

    print("\n" + "=" * 88)
    print("全模型: 算法比较")
    print("=" * 88)
    rows, probas = [], {}
    models = {
        "多分类 Logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)),
        "随机森林": RandomForestClassifier(n_estimators=1000, min_samples_leaf=5, random_state=42),
    }
    for name, clf in models.items():
        res, proba = evaluate(name, clf, X, y, cv)
        rows.append(res)
        probas[name] = proba
    print(pd.DataFrame(rows).set_index("模型").round(3).to_string())

    print("\n混淆矩阵 (多分类 Logistic, 行=实际 列=预测):")
    pred = pd.Series(probas["多分类 Logistic"].argmax(1)).map(LABELS)
    print(pd.crosstab(pd.Series(y).map(LABELS), pred).to_string())

    print("\n" + "=" * 88)
    print("时间外部验证 (2016-2023 建模 -> 2024-2026 验证)")
    print("=" * 88)
    train = df["admit_year"] <= 2023
    Xtr, Xte = X[train.to_numpy()], X[(~train).to_numpy()]
    ytr, yte = y[train.to_numpy()], y[(~train).to_numpy()]
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)
    aucs = [roc_auc_score((yte == k).astype(int), proba[:, k]) for k in range(3)]
    print(f"训练集 n={len(ytr)} {np.bincount(ytr)}   验证集 n={len(yte)} {np.bincount(yte)}")
    print(f"验证集 AUC  观察={aucs[0]:.3f}  内镜={aucs[1]:.3f}  手术={aucs[2]:.3f}  宏平均={np.mean(aucs):.3f}")
    print(f"验证集 准确率={accuracy_score(yte, proba.argmax(1)):.3f}  Brier={multiclass_brier(yte, proba):.3f}")

    print("\n" + "=" * 88)
    missingness_diagnostics(df, y)

    print("\n" + "=" * 88)
    print("敏感性分析 (多分类 Logistic, 5 折交叉验证)")
    print("=" * 88)
    sens = run_sensitivity(df, y)
    show = sens.drop(columns=["说明"]).set_index("分析")
    print(show.round(3).to_string())
    print("\n各项针对的质疑:")
    for _, r in sens.iterrows():
        print(f"  {r['分析']:<18} {r['说明']}")
    SHIFT_LIMIT = 0.10
    biased = sens[sens["类别偏移"] > SHIFT_LIMIT]
    if len(biased):
        print(f"\n类别构成显著偏移的分析（偏移 > {SHIFT_LIMIT:.0%}，其 AUC 不可与主分析直接比较）:")
        for _, r in biased.iterrows():
            print(f"  {r['分析']}：n={r['n']}，三类 {r['观察/内镜/手术']}，"
                  f"偏移 {r['类别偏移']:.0%}")
        print("  子集的构成本身受选择效应影响，效能差异未必反映模型表现。")

    primary = sens.loc[sens["分析"] == "主分析", "宏平均AUC"].iloc[0]
    clean = sens[(sens["类别偏移"] <= SHIFT_LIMIT) & sens["宏平均AUC"].notna()]
    drift_all = (sens["宏平均AUC"] - primary).abs().max()
    drift_clean = (clean["宏平均AUC"] - primary).abs().max()
    print(f"\n与主分析的宏平均 AUC 最大差异: 全部 {drift_all:.3f}；"
          f"剔除构成偏移者后 {drift_clean:.3f}")
    print("差异小于 0.05 可在正文表述为「结论稳健」" if drift_clean < 0.05
          else "差异较大，需在正文中具体说明是哪一项分析、为何不同")

    print("\n" + "=" * 88)
    print("全模型变量重要性 (随机森林 Gini)")
    print("=" * 88)
    rf = RandomForestClassifier(n_estimators=1000, min_samples_leaf=5, random_state=42).fit(X, y)
    imp = pd.Series(rf.feature_importances_, index=full).sort_values(ascending=False)
    print(imp.head(15).round(4).to_string())


if __name__ == "__main__":
    main()

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
    print("全模型变量重要性 (随机森林 Gini)")
    print("=" * 88)
    rf = RandomForestClassifier(n_estimators=1000, min_samples_leaf=5, random_state=42).fit(X, y)
    imp = pd.Series(rf.feature_importances_, index=full).sort_values(ascending=False)
    print(imp.head(15).round(4).to_string())


if __name__ == "__main__":
    main()

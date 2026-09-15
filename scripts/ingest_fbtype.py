# -*- coding: utf-8 -*-
"""
并入异物类型人工核验结果。

用法:
    python3 scripts/ingest_fbtype.py annotation/异物类型核验表单.xlsx [第二位核验者.xlsx]

输出:
    outputs/fbtype_verified.csv   人工判定结果，供 build_cohort.py 覆盖正则判定
    outputs/fbtype_report.txt     正则准确率（C 组）与双人 Kappa（双人子集）

两个指标分别回答审稿人的两个问题：
    正则 vs 人工  自动抽取准不准（C 抽检组，未受正则提示影响）
    人工 vs 人工  判读一不一致（双人子集）
"""
import sys

import numpy as np
import pandas as pd

SHEET = "核验表"
KEY = "科研就诊编号"

LABEL_TO_FIELD = {
    "纽扣电池": "fb_battery", "磁性异物": "fb_magnet", "尖锐异物": "fb_sharp",
    "硬币或金属钝物": "fb_coin", "圆球状钝物": "fb_round", "果核": "fb_pit",
    "长条状异物": "fb_long", "塑料或玩具": "fb_plastic", "水银或体温计": "fb_mercury",
    "食物团块": "fb_food", "其他": "fb_other",
}
NON_TYPE = {"原文未说明", "非异物病例"}
COUNT_BAND = {"1": 1.0, "2": 2.0, "3-5": 4.0, "≥6": 7.0, "不能确定": np.nan}


def read_form(path):
    df = pd.read_excel(path, sheet_name=SHEET)
    if KEY not in df.columns:
        raise SystemExit(f"{path} 的「{SHEET}」工作表缺少「{KEY}」列")
    return df


def cohens_kappa(a, b):
    mask = a.notna() & b.notna()
    a, b = a[mask].astype(str), b[mask].astype(str)
    if len(a) == 0:
        return np.nan, 0
    cats = sorted(set(a) | set(b))
    idx = {c: i for i, c in enumerate(cats)}
    m = np.zeros((len(cats), len(cats)))
    for x, y in zip(a, b):
        m[idx[x], idx[y]] += 1
    n = m.sum()
    po = np.trace(m) / n
    pe = (m.sum(0) * m.sum(1)).sum() / (n * n)
    if np.isclose(pe, 1.0):
        return np.nan, int(n)
    return (po - pe) / (1 - pe), int(n)


def regex_accuracy(df):
    """C 抽检组：正则判定 vs 人工判定。"""
    sub = df[df["核验组"].astype(str).str.startswith("C")].copy()
    sub = sub[sub["异物类型"].notna()]
    if sub.empty:
        return None
    # 正则判定列为「类别名」或「（未归类）」；C 组均为单类命中
    agree = sub["正则判定"].astype(str).str.strip() == sub["异物类型"].astype(str).str.strip()
    # 人工判为「原文未说明」时，正则本不该命中，单独计为错判
    lines = [f"C 抽检组 n={len(sub)}",
             f"  正则与人工一致: {int(agree.sum())} ({agree.mean() * 100:.1f}%)"]
    wrong = sub[~agree]
    if len(wrong):
        lines.append("  不一致明细（正则 -> 人工，计数）:")
        pairs = (wrong["正则判定"].astype(str) + " -> " + wrong["异物类型"].astype(str))
        for k, v in pairs.value_counts().items():
            lines.append(f"    {k}: {v}")
    return "\n".join(lines)


def derive(df):
    out = pd.DataFrame({KEY: df[KEY]})
    primary = df["异物类型"].astype(str).str.strip()
    secondary = df.get("次要类型", pd.Series("", index=df.index)).astype(str).str.strip()

    out["fbtype_verified"] = df["异物类型"].notna().astype(int)
    out["fbtype_primary"] = primary.where(df["异物类型"].notna())
    out["fbtype_unstated"] = primary.isin(NON_TYPE).astype(int)

    for label, field in LABEL_TO_FIELD.items():
        out[f"{field}_manual"] = ((primary == label) | (secondary == label)).astype(int)

    if "数目" in df.columns:
        out["fbtype_count"] = df["数目"].map(COUNT_BAND)
    if "原文词语" in df.columns:
        out["fbtype_term"] = df["原文词语"]
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    primary = read_form(sys.argv[1])
    out = derive(primary)
    out.to_csv("outputs/fbtype_verified.csv", index=False, encoding="utf-8-sig")

    done = int(out["fbtype_verified"].sum())
    lines = [f"已核验 {done}/{len(out)} 行", ""]

    acc = regex_accuracy(primary)
    if acc:
        lines += ["=" * 56, "正则抽取准确率", "=" * 56, acc, ""]

    if done:
        named = out.loc[(out["fbtype_verified"] == 1) & (out["fbtype_unstated"] == 0),
                        "fbtype_primary"]
        lines += ["=" * 56, "人工判定的类型分布", "=" * 56, named.value_counts().to_string(),
                  f"\n原文未说明/非异物: {int(out['fbtype_unstated'].sum())}", ""]
        if "fbtype_term" in out:
            terms = out["fbtype_term"].dropna()
            terms = terms[terms.astype(str).str.strip() != ""]
            if len(terms):
                lines += ["词典回补候选（人工记录的原文词语，按频次）:",
                          terms.value_counts().head(30).to_string(), ""]

    if len(sys.argv) > 2:
        second = read_form(sys.argv[2])
        a = primary.set_index(KEY)
        b = second.set_index(KEY)
        shared = a.index.intersection(b.index)
        if "双人核验" in a.columns:
            shared = shared.intersection(a.index[a["双人核验"] == "是"])
        lines += ["=" * 56, f"双人核验一致性（Cohen's Kappa），子集 n={len(shared)}", "=" * 56]
        for f in ["异物类型", "次要类型", "数目"]:
            if f in a.columns and f in b.columns:
                k, n = cohens_kappa(a.loc[shared, f], b.loc[shared, f])
                lines.append(f"  {f:<10} Kappa={k:.3f}   有效配对 n={n}"
                             if not np.isnan(k) else f"  {f:<10} Kappa=NA（取值无变异）")
        lines.append("\n一般 κ>0.80 为优秀，0.61–0.80 为良好；<0.60 需两人重新统一判读口径后返工。")

    report = "\n".join(lines)
    with open("outputs/fbtype_report.txt", "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print(report)
    print("\n已写出 outputs/fbtype_verified.csv 与 outputs/fbtype_report.txt")


if __name__ == "__main__":
    main()

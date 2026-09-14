# -*- coding: utf-8 -*-
"""
把填好的 X 线重标注表单并入分析数据集。

用法:
    python3 scripts/ingest_annotation.py annotation/X线重标注表单.xlsx [第二位阅片者的文件.xlsx]

单文件  -> 生成 outputs/xray_annotation.csv
双文件  -> 另在双人阅片子集上计算 Cohen's Kappa，写入 outputs/kappa_report.txt

输出的 xray_annotation.csv 由 build_cohort.py 读入，取代原先基于报告文本的正则定位。
"""
import sys

import numpy as np
import pandas as pd

SHEET = "标注表"
KEY = "科研就诊编号"

# 标注部位 -> 建模用的解剖分组。胃与幽门以远的区分是决策的第一依据。
SEGMENT = {
    "食管上段": "esophagus", "食管中段": "esophagus", "食管下段": "esophagus",
    "胃": "stomach", "十二指肠": "duodenum",
    "小肠": "small_bowel", "结肠": "colorectal", "直肠": "colorectal",
    "多处": "multiple", "不能确定": "unknown", "无异物": "none",
}
# 内镜可及性: 食管/胃/十二指肠可经内镜取出，幽门以远一般只能观察或手术
ENDOSCOPIC_REACH = {"esophagus", "stomach", "duodenum"}

COUNT_BAND = {"1": 1.0, "2": 2.0, "3-5": 4.0, "≥6": 7.0, "不能确定": np.nan}

# 指南常用阈值(mm)。阈值随年龄而异且各指南略有出入，正式分析须按所引指南确认，
# 并以原始毫米值做阈值敏感性分析——这正是分开记录长径短径的用意。
PYLORUS_MM = 25    # 短径超过此值难以通过幽门
DUODENUM_MM = 60   # 长径超过此值难以通过十二指肠 C 形襻

KAPPA_FIELDS = ["异物可见", "部位", "数目", "成串成团", "形态", "双环征", "影像判断类型"]


def read_form(path):
    df = pd.read_excel(path, sheet_name=SHEET)
    if KEY not in df.columns:
        raise SystemExit(f"{path} 的「{SHEET}」工作表缺少「{KEY}」列")
    return df


def cohens_kappa(a, b):
    """未加权 Cohen's Kappa。两列须等长且已对齐。"""
    mask = a.notna() & b.notna()
    a, b = a[mask].astype(str), b[mask].astype(str)
    if len(a) == 0:
        return np.nan, 0
    cats = sorted(set(a) | set(b))
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    m = np.zeros((k, k))
    for x, y in zip(a, b):
        m[idx[x], idx[y]] += 1
    n = m.sum()
    po = np.trace(m) / n
    pe = (m.sum(0) * m.sum(1)).sum() / (n * n)
    if np.isclose(pe, 1.0):
        return np.nan, int(n)
    return (po - pe) / (1 - pe), int(n)


def derive(df):
    out = pd.DataFrame({KEY: df[KEY]})
    out["xray_annotated"] = df["部位"].notna().astype(int)
    out["xray_fb_visible"] = df["异物可见"].map({"是": 1, "否": 0}).astype("Float64")

    seg = df["部位"].map(SEGMENT)
    out["xray_segment"] = seg
    for name in ["esophagus", "stomach", "duodenum", "small_bowel", "colorectal"]:
        out[f"loc_{name}"] = (seg == name).astype("Int64").where(seg.notna())
    # 内镜可及性: 多处按最近端处理（保守，倾向可及）
    out["xray_endoscopic_reach"] = (
        seg.isin(ENDOSCOPIC_REACH) | (seg == "multiple")
    ).astype("Int64").where(seg.notna())

    exact = pd.to_numeric(df.get("数目_精确"), errors="coerce")
    out["xray_count"] = exact.fillna(df["数目"].map(COUNT_BAND))
    out["xray_multiple"] = (out["xray_count"] >= 2).astype("Int64").where(out["xray_count"].notna())
    out["xray_long_mm"] = pd.to_numeric(df.get("长径_mm"), errors="coerce")
    out["xray_short_mm"] = pd.to_numeric(df.get("短径_mm"), errors="coerce")

    # 指南阈值在此套用，原始毫米值原样保存——日后调整阈值不必重新阅片。
    # 短径决定能否过幽门(限制因素是最小横截面)，长径决定能否过十二指肠 C 形襻。
    # 阈值随年龄而异，婴幼儿更低；正式分析应按所引指南确认，并做阈值敏感性分析。
    out["xray_wide_gt25"] = (out["xray_short_mm"] > PYLORUS_MM).astype("Int64").where(
        out["xray_short_mm"].notna())
    out["xray_long_gt60"] = (out["xray_long_mm"] > DUODENUM_MM).astype("Int64").where(
        out["xray_long_mm"].notna())

    for col, name in [("成串成团", "xray_clumped"), ("合并其他金属", "xray_magnet_plus_metal"),
                      ("双环征", "xray_double_ring"),
                      ("膈下游离气体", "xray_free_air"), ("肠梗阻征象", "xray_obstruction")]:
        if col in df.columns:
            out[name] = df[col].map({"是": 1, "否": 0}).astype("Float64")

    # 多枚磁体或单枚磁体合并金属，均按指南需干预——后者易被漏掉，故单列。
    is_magnet = df.get("影像判断类型", pd.Series(dtype=object)).eq("磁性球形")
    out["xray_magnet_risk"] = (
        (is_magnet & (out["xray_count"] >= 2))
        | out.get("xray_magnet_plus_metal", pd.Series(0, index=out.index)).eq(1)
    ).astype("Int64")

    if "形态" in df.columns:
        out["xray_shape"] = df["形态"]
    if "影像判断类型" in df.columns:
        out["xray_type"] = df["影像判断类型"]
    if "片子时相" in df.columns:
        out["xray_phase"] = df["片子时相"]
        # 决策后拍摄的片子不得作为预测因子
        out["xray_predecision"] = df["片子时相"].isin(["术前片", "无手术"]).astype(int)
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    primary = read_form(sys.argv[1])
    out = derive(primary)
    out.to_csv("outputs/xray_annotation.csv", index=False, encoding="utf-8-sig")

    done = int(out["xray_annotated"].sum())
    print(f"已标注 {done}/{len(out)} 行")
    if done:
        seg = out.loc[out["xray_annotated"] == 1, "xray_segment"]
        located = seg.notna() & ~seg.isin(["unknown", "none"])
        print(f"定位到具体节段 {int(located.sum())} 例 "
              f"（原报告文本仅能定位 516 例，本次应显著高于该数）")
        print("\n节段分布:")
        print(seg.value_counts().to_string())
        if "xray_predecision" in out:
            print(f"\n可用于建模（术前片 / 无手术）: {int(out['xray_predecision'].sum())}")
    print("\n已写出 outputs/xray_annotation.csv")

    if len(sys.argv) > 2:
        second = read_form(sys.argv[2])
        a = primary.set_index(KEY)
        b = second.set_index(KEY)
        shared = a.index.intersection(b.index)
        if "双人阅片" in a.columns:
            shared = shared.intersection(a.index[a["双人阅片"] == "是"])
        lines = [f"双人阅片一致性（Cohen's Kappa），子集 n={len(shared)}", "=" * 52]
        for f in KAPPA_FIELDS:
            if f in a.columns and f in b.columns:
                k, n = cohens_kappa(a.loc[shared, f], b.loc[shared, f])
                lines.append(f"{f:<14} Kappa={k:.3f}   有效配对 n={n}"
                             if not np.isnan(k) else f"{f:<14} Kappa=NA（取值无变异）")
        if "最大径_mm" in a.columns:
            x = pd.to_numeric(a.loc[shared, "最大径_mm"], errors="coerce")
            y = pd.to_numeric(b.loc[shared, "最大径_mm"], errors="coerce")
            m = x.notna() & y.notna()
            if m.sum() > 1:
                lines.append(f"{'最大径_mm':<14} Pearson r={x[m].corr(y[m]):.3f}   n={int(m.sum())}")
        report = "\n".join(lines)
        with open("outputs/kappa_report.txt", "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print("\n" + report)
        print("\n已写出 outputs/kappa_report.txt")


if __name__ == "__main__":
    main()

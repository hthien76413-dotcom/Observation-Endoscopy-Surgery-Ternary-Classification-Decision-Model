# -*- coding: utf-8 -*-
"""
生成 X 线重标注的工作清单。

输出:
  annotation/worklist.csv          阅片工作清单（1073 行，每行一次住院的首次 X 线）
  annotation/original_reports.csv  原放射科报告全文，按序号对应

两个关键判定:

1. 片子时相。首次 X 线必须早于治疗决策才能作预测因子。判定优先用手麻系统的
   「手术开始时间」（精确到分钟）；`住院病历手术记录` 的时间字段 100% 为 00:00，
   只有日期，拿它做时序比较会把几乎所有片子误判为「决策后」，故仅在无手麻记录时
   降级为同日判定。

2. 双人阅片子集。从可用于建模的行中固定种子随机抽取 200 例，供 Cohen's Kappa。
"""
import os

import numpy as np
import pandas as pd

XLSX = "10年消化道异物原始数据.xlsx"
OUTDIR = "annotation"
SEED = 20260914
N_DOUBLE_READ = 200

COLUMNS = ["序号", "科研就诊编号", "性别", "年龄_岁", "入院时间", "检查时间", "距入院_h",
           "X线次数", "报告名称", "主诉", "片子时相", "双人阅片", "需特别处理"]

PHASE_ORDER = {"术前片": 0, "无手术": 1, "同日-时序不明": 2, "决策后片": 3}


def operation_times(xlsx):
    """返回 (精确时刻 Series, 仅日期 Series)。"""
    sa = pd.read_excel(xlsx, sheet_name="手麻系统信息")
    exact = (sa.assign(t=pd.to_datetime(sa["手术开始时间"], errors="coerce"))
               .dropna(subset=["t"]).groupby("科研就诊编号")["t"].min())

    op = pd.read_excel(xlsx, sheet_name="住院病历手术记录")
    dates = pd.to_datetime(op["手术日期及时间"], errors="coerce").dt.normalize()
    date_only = (op.assign(d=dates).dropna(subset=["d"])
                   .groupby("科研就诊编号")["d"].min())
    return exact, date_only


def classify_phase(row):
    if pd.notna(row["_exact"]):
        return "术前片" if row["_t"] < row["_exact"] else "决策后片"
    if pd.notna(row["_dateop"]):
        day = row["_t"].normalize()
        if day < row["_dateop"]:
            return "术前片"
        if day > row["_dateop"]:
            return "决策后片"
        return "同日-时序不明"
    return "无手术"


def build():
    os.makedirs(OUTDIR, exist_ok=True)
    base = pd.read_excel(XLSX, sheet_name="病案首页基本信息")
    xray = pd.read_excel(XLSX, sheet_name="X线报告")
    adm = pd.read_excel(XLSX, sheet_name="儿科入院记录")
    exact, date_only = operation_times(XLSX)

    xray["_t"] = pd.to_datetime(xray["检查时间"], errors="coerce")
    base["_adm"] = pd.to_datetime(base["入院日期"], errors="coerce")

    first = xray.sort_values("_t").groupby("科研就诊编号", as_index=False).first()
    n_films = xray.groupby("科研就诊编号").size().rename("X线次数")

    w = (first.merge(base[["科研就诊编号", "性别", "年龄（岁）", "_adm"]], on="科研就诊编号", how="left")
              .merge(n_films, on="科研就诊编号", how="left")
              .merge(adm[["科研就诊编号", "主诉"]], on="科研就诊编号", how="left"))
    w["_exact"] = w["科研就诊编号"].map(exact)
    w["_dateop"] = w["科研就诊编号"].map(date_only)
    w["报告名称"] = w["报告名称"].astype(str).str.replace("\n", "").str.strip()
    w["片子时相"] = w.apply(classify_phase, axis=1)

    w["需特别处理"] = ""
    w.loc[w["片子时相"] == "决策后片", "需特别处理"] = "首次片晚于手术开始，本次住院无术前片"
    w.loc[w["片子时相"] == "同日-时序不明", "需特别处理"] = (
        "与手术同日、手术记录无时刻，请据 PACS 时间确认是否术前")
    w.loc[~w["报告名称"].str.contains("胸|腹|盆"), "需特别处理"] = "非胸腹盆片，请确认是否另有相关片"
    w.loc[w["报告名称"].str.contains("造影"), "需特别处理"] = "造影检查，判读标准不同"

    usable = w.index[w["片子时相"].isin(["术前片", "无手术"])].to_numpy()
    picked = np.random.default_rng(SEED).choice(
        usable, size=min(N_DOUBLE_READ, len(usable)), replace=False)
    w["双人阅片"] = np.where(w.index.isin(set(picked)), "是", "")

    w["入院时间"] = w["_adm"].dt.strftime("%Y-%m-%d %H:%M")
    w["检查时间"] = w["_t"].dt.strftime("%Y-%m-%d %H:%M")
    w["距入院_h"] = ((w["_t"] - w["_adm"]).dt.total_seconds() / 3600).round(1)
    w["年龄_岁"] = w["年龄（岁）"].round(1)

    w = w.sort_values(["片子时相", "检查时间"],
                      key=lambda c: c.map(PHASE_ORDER) if c.name == "片子时相" else c)
    w = w.reset_index(drop=True)
    w.insert(0, "序号", range(1, len(w) + 1))

    w[COLUMNS].to_csv(f"{OUTDIR}/worklist.csv", index=False, encoding="utf-8-sig")
    (w[["序号", "科研就诊编号", "报告名称", "检查所见", "检查结论"]]
        .to_csv(f"{OUTDIR}/original_reports.csv", index=False, encoding="utf-8-sig"))

    counts = w["片子时相"].value_counts()
    print(f"工作清单 {len(w)} 行")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print(f"可用于建模（术前片 + 无手术）: {int(counts.reindex(['术前片', '无手术']).fillna(0).sum())}")
    print(f"双人阅片子集: {(w['双人阅片'] == '是').sum()}")
    print(f"需特别处理: {(w['需特别处理'] != '').sum()}")


if __name__ == "__main__":
    build()

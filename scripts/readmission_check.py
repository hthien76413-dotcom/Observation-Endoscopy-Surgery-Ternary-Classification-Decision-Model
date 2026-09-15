# -*- coding: utf-8 -*-
"""
观察组 30 日再入院核查。

回答论文中最关键的一个标签效度问题：被判为「观察」的患儿，
是否真的安全，还是只是把干预推迟到了下一次住院。

输出:
  outputs/readmission_report.txt

**这项核查的射程有限，正文必须写明**：本数据集只包含消化道异物相关住院，
因此只能发现「再次因异物在本院住院」的病例。以下情形查不到——
患儿在外院就诊、以其他诊断入院、或仅在门诊随访。
故「未发现再入院」应表述为「本院异物相关再入院未见」，
不可表述为「无延迟干预」。
"""
import os
import re

import numpy as np
import pandas as pd

XLSX = "10年消化道异物原始数据.xlsx"
WINDOW_DAYS = 30

SURG_PAT = (r"开腹|剖腹|腹腔镜|切开异物取出|破裂修补|穿孔修补|吻合术|部分切除"
            r"|裂伤|阑尾切除|中转|肠粘连松解|病损切除|胃修补|引流术")
ENDO_PAT = r"内镜|胃镜|食管镜|十二指肠镜|结肠镜"
LABELS = {0: "观察", 1: "内镜", 2: "手术"}


def load_labels():
    proc = {}
    for sheet in ("住院病历手术记录", "手麻系统信息"):
        df = pd.read_excel(XLSX, sheet_name=sheet)
        for visit, name in zip(df["科研就诊编号"], df["手术名称"]):
            proc.setdefault(visit, []).append(str(name))

    def classify(visit):
        names = proc.get(visit)
        if not names:
            return 0
        joined = "|".join(names)
        if re.search(SURG_PAT, joined):
            return 2
        if re.search(ENDO_PAT, joined):
            return 1
        return np.nan
    return classify


def build():
    os.makedirs("outputs", exist_ok=True)
    b = pd.read_excel(XLSX, sheet_name="病案首页基本信息")
    b["入院"] = pd.to_datetime(b["入院日期"], errors="coerce")
    b["出院"] = pd.to_datetime(b["出院日期"], errors="coerce")
    b["label"] = b["科研就诊编号"].map(load_labels())
    b = b[b["label"].notna()].copy()
    b["label"] = b["label"].astype(int)
    b["组"] = b["label"].map(LABELS)

    b = b.sort_values(["科研患者编号", "入院"]).reset_index(drop=True)
    nxt = b.groupby("科研患者编号").shift(-1)
    b["下次入院"] = nxt["入院"]
    b["下次组"] = nxt["组"]
    b["下次就诊编号"] = nxt["科研就诊编号"]
    b["间隔天"] = (b["下次入院"] - b["出院"]).dt.days

    b["30日内再入院"] = (b["间隔天"].notna() & (b["间隔天"] >= 0)
                         & (b["间隔天"] <= WINDOW_DAYS))

    lines = []
    a = lines.append
    a("=" * 72)
    a(f"观察组 {WINDOW_DAYS} 日再入院核查")
    a("=" * 72)
    a("")
    a("射程说明：本数据集只包含消化道异物相关住院，故只能发现「再次因异物在本院")
    a("住院」的病例。患儿转外院、以其他诊断入院、或仅门诊随访，均查不到。")
    a("正文应表述为「本院异物相关再入院未见」，不可表述为「无延迟干预」。")
    a("")

    a(f"出院日期缺失 {int(b['出院'].isna().sum())} 例，无法计算间隔。")
    a(f"可评估的住院 {int(b['出院'].notna().sum())} / {len(b)}")
    a("")

    a("-" * 72)
    a(f"各组 {WINDOW_DAYS} 日内再入院")
    a("-" * 72)
    for g in ["观察", "内镜", "手术"]:
        sub = b[b["组"] == g]
        ok = sub["出院"].notna()
        n_re = int(sub.loc[ok, "30日内再入院"].sum())
        a(f"  {g}: {n_re} / {int(ok.sum())} ({n_re / max(int(ok.sum()), 1) * 100:.2f}%)")
    a("")

    obs_re = b[(b["组"] == "观察") & b["30日内再入院"]]
    a("-" * 72)
    a("观察组再入院明细（标签效度的核心证据）")
    a("-" * 72)
    if obs_re.empty:
        a("  未发现观察组患儿在 30 日内因异物再次入院。")
    else:
        for _, r in obs_re.iterrows():
            a(f"  患者 {r['科研患者编号']}：首次 {r['入院'].date()} 观察，"
              f"出院 {r['出院'].date()}，{int(r['间隔天'])} 天后再入院 → {r['下次组']}")
        escalate = obs_re[obs_re["下次组"].isin(["内镜", "手术"])]
        a("")
        a(f"  其中再入院时接受干预（内镜或手术）: {len(escalate)} 例")
        if len(escalate):
            a("  —— 这些属于「观察失败」，须在正文与 Limitations 中明确报告，")
            a("     并从「观察组 0 例不良结局」的表述中剔除。")
    a("")

    a("-" * 72)
    a("全部多次住院患儿（不限组别与窗口）")
    a("-" * 72)
    rep = b["科研患者编号"].value_counts()
    for pid in rep[rep > 1].index:
        g = b[b["科研患者编号"] == pid].sort_values("入院")
        seq = " → ".join(
            f"{r['入院'].date()} {r['组']}" for _, r in g.iterrows())
        gaps = [int(x) for x in (g["入院"].shift(-1) - g["出院"]).dt.days.dropna()]
        a(f"  患者 {pid}: {seq}")
        a(f"    出院至下次入院间隔: {gaps} 天")
    a("")

    a("-" * 72)
    a("观察组住院期间的并发症（与再入院互补的另一条证据）")
    a("-" * 72)
    a("按「入院病情」字段区分入院时已有与住院期间新发——")
    a("只有后者才是观察本身的不良结局。")
    a("")
    dx = pd.read_excel(XLSX, sheet_name="病案出院诊断编目后")
    dx["诊断疾病名称"] = dx["诊断疾病名称"].astype(str)
    obs_ids = set(b.loc[b["组"] == "观察", "科研就诊编号"])
    for name, pat in [("穿孔", r"穿孔"), ("梗阻", r"梗阻"), ("腹膜炎", r"腹膜炎"),
                      ("瘘", r"瘘"), ("脓毒症", r"脓毒|败血")]:
        hit = dx[dx["科研就诊编号"].isin(obs_ids)
                 & dx["诊断疾病名称"].str.contains(pat)]
        poa = hit[hit["入院病情"] == "有"]["科研就诊编号"].nunique()
        new_onset = hit[hit["入院病情"] == "无"]["科研就诊编号"].nunique()
        unclear = hit[~hit["入院病情"].isin(["有", "无"])]["科研就诊编号"].nunique()
        a(f"  观察组 {name}: 合计 {hit['科研就诊编号'].nunique()}"
          f"（入院时已有 {poa}，住院新发 {new_onset}，不明 {unclear}）")
    a("")
    a("  注：入院时已有者多为与异物无关的合并病（如阑尾炎伴脓肿、粪便嵌塞、结肠炎），")
    a("      不构成观察失败。")
    a("")
    a("=" * 72)

    report = "\n".join(lines)
    with open("outputs/readmission_report.txt", "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print(report)


if __name__ == "__main__":
    build()

# -*- coding: utf-8 -*-
"""
儿童消化道异物「观察 / 内镜 / 手术」三分类决策模型 —— 队列与特征构建

输入: 10年消化道异物原始数据.xlsx (20 个工作表的 EMR 抽取)
输出: outputs/cohort.csv          建模用分析数据集(一行一次住院)
      outputs/data_profile.txt    数据概况与缺失报告

设计原则(重要):
  只纳入"治疗决策时点之前"可获得的变量，避免信息泄漏。
  术中诊断、出院诊断、住院天数、手术记录内容等均为决策后信息，仅用于
  结局定义与标签校验，不得进入预测因子。
"""
import os
import re

import numpy as np
import pandas as pd

XLSX = "10年消化道异物原始数据.xlsx"
OUTDIR = "outputs"

# --------------------------------------------------------------------------
# 1. 治疗标签: 观察(0) / 内镜(1) / 手术(2)
# --------------------------------------------------------------------------
# 说明: 本中心儿童内镜取异物在全麻下于手术室完成，故记录在手术记录/手麻系统，
#       而非内镜报告表(该表仅 18 条)。标签须由手术名称正则判定。
SURG_PAT = (
    r"开腹|剖腹|腹腔镜|切开异物取出|破裂修补|穿孔修补|吻合术|部分切除"
    r"|裂伤|阑尾切除|中转|肠粘连松解|病损切除|胃修补|引流术"
)
ENDO_PAT = r"内镜|胃镜|食管镜|十二指肠镜|结肠镜"

LABELS = {0: "观察", 1: "内镜", 2: "手术"}


def load_procedures(path):
    """汇总每次住院的全部手术名称(手术记录 + 手麻系统)。"""
    proc = {}
    for sheet in ("住院病历手术记录", "手麻系统信息"):
        df = pd.read_excel(path, sheet_name=sheet)
        for visit, name in zip(df["科研就诊编号"], df["手术名称"]):
            proc.setdefault(visit, []).append(str(name))
    return proc


def assign_label(visit, proc):
    """手术优先于内镜: 一次住院内若既内镜又开腹，归为手术组。"""
    names = proc.get(visit)
    if not names:
        return 0
    joined = "|".join(names)
    if re.search(SURG_PAT, joined):
        return 2
    if re.search(ENDO_PAT, joined):
        return 1
    return np.nan  # 非异物相关手术(如疝、骨科)，予以排除


# --------------------------------------------------------------------------
# 2. 自由文本抽取
# --------------------------------------------------------------------------
UNIT_HOURS = {"分钟": 1 / 60, "小时": 1, "天": 24, "日": 24, "周": 168, "月": 720, "年": 8760}


def parse_ingestion_hours(chief_complaint):
    """从主诉解析误食至就诊时长(小时)。如 '误食异物3小时余' -> 3.0"""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(分钟|小时|天|日|周|月|年)", str(chief_complaint))
    if not match:
        return np.nan
    return float(match.group(1)) * UNIT_HOURS[match.group(2)]


# 异物类型词典。允许一例命中多类(如"磁力珠"同时为磁性与多发)。
FB_TYPES = {
    "fb_battery": r"纽扣电池|扣式电池|钮扣电池|电池",
    "fb_magnet": r"磁力珠|巴克球|磁珠|磁铁|吸铁石|磁性",
    "fb_sharp": r"钉|针|发卡|发夹|别针|订书|刀片|牙签|铁丝|螺丝|耳钉|鱼刺|玻璃",
    "fb_coin": r"硬币|钱币|金属片|戒指|钥匙",
    "fb_pit": r"枣核|果核",
    "fb_long": r"棒棒糖棍|棍|笔|吸管|绳|牙刷",
    "fb_plastic": r"塑料|玩具|积木|弹珠",
    "fb_food": r"食物团|肉块|馒头|蛋壳",
    "fb_multiple": r"多发|两枚|三枚|数枚|多枚|多个|数个|\d+\s*颗",
}

# 症状/体征。用否定前瞻排除"无腹痛"这类阴性描述。
SYMPTOMS = {
    "sym_abdpain": r"(?<!无)(?<!否认)腹痛",
    "sym_vomit": r"(?<!无)(?<!否认)呕吐",
    "sym_hematemesis": r"呕血|黑便|便血|血便",
    "sym_fever": r"(?<!无)(?<!否认)发热",
    "sym_dysphagia": r"流涎|吞咽困难|拒食|不能进食|吞咽疼痛",
    "sym_distension": r"(?<!无)(?<!否认)腹胀",
    "sign_tenderness": r"压痛",
    "sign_peritoneal": r"反跳痛|肌紧张|板状腹|腹膜刺激征",
}

# 影像学定位。食管/胃属内镜可及，幽门以远多可观察。
LOCATIONS = {
    "loc_esophagus": r"食管",
    "loc_stomach": r"胃(?!肠)(?!镜)",
    "loc_duodenum": r"十二指肠",
    "loc_smallbowel": r"小肠|空肠|回肠",
    "loc_colorectal": r"结肠|直肠|乙状|盲肠",
}


def flag(series, pattern):
    return series.str.contains(pattern, regex=True, na=False).astype(int)


# --------------------------------------------------------------------------
# 3. 实验室检查: 取入院后最早一次结果
# --------------------------------------------------------------------------
LAB_ITEMS = {
    "实验室检查_血常规": {
        "lab_wbc": "白细胞计数定量-定量结果",
        "lab_neut_pct": "中性粒细胞百分数定量-定量结果",
        "lab_hb": "血红蛋白浓度定量-定量结果",
        "lab_plt": "血小板计数定量-定量结果",
    },
    "实验室检查_血C反应蛋白（CRP）测定": {"lab_crp": "超敏C反应蛋白定量-定量结果"},
    "实验室检查_血液肝功能测定": {"lab_alb": "白蛋白定量-定量结果"},
}


def resolve_censored(quant, qual):
    """CRP 等指标低于检测限时，定量列为空而定性列记为 '<0.78'。
    按检验流行病学惯例以 LOD/2 代入，避免将 48% 的低值误判为缺失。"""
    value = pd.to_numeric(quant, errors="coerce")
    lod = pd.to_numeric(
        qual.astype(str).str.extract(r"<\s*(\d+(?:\.\d+)?)", expand=False), errors="coerce"
    )
    return value.fillna(lod / 2)


def earliest_labs(path):
    """每次住院取报告时间最早的一次检验，代表决策时点的化验状态。"""
    out = []
    for sheet, mapping in LAB_ITEMS.items():
        df = pd.read_excel(path, sheet_name=sheet)
        df["报告时间"] = pd.to_datetime(df["报告时间"], errors="coerce")
        if sheet.endswith("（CRP）测定"):
            df["超敏C反应蛋白定量-定量结果"] = resolve_censored(
                df["超敏C反应蛋白定量-定量结果"], df["超敏C反应蛋白定量-定性结果"]
            )
        df = df.sort_values("报告时间").groupby("就诊编号", as_index=False).first()
        keep = df[["就诊编号"] + list(mapping.values())].rename(columns={v: k for k, v in mapping.items()})
        out.append(keep.rename(columns={"就诊编号": "科研就诊编号"}))
    labs = out[0]
    for extra in out[1:]:
        labs = labs.merge(extra, on="科研就诊编号", how="outer")
    for col in labs.columns:
        if col != "科研就诊编号":
            labs[col] = pd.to_numeric(labs[col], errors="coerce")
    return labs


# --------------------------------------------------------------------------
# 4. 结局(仅用于标签校验与描述，不作预测因子)
# --------------------------------------------------------------------------
OUTCOME_PAT = {
    "out_perforation": r"穿孔",
    "out_obstruction": r"梗阻",
    "out_peritonitis": r"腹膜炎",
    "out_fistula": r"瘘",
    "out_sepsis": r"脓毒|败血",
    "out_stricture": r"狭窄",
}


def build():
    os.makedirs(OUTDIR, exist_ok=True)

    base = pd.read_excel(XLSX, sheet_name="病案首页基本信息")
    adm = pd.read_excel(XLSX, sheet_name="儿科入院记录")
    dx = pd.read_excel(XLSX, sheet_name="病案出院诊断编目后")
    xray = pd.read_excel(XLSX, sheet_name="X线报告")

    proc = load_procedures(XLSX)
    base["label"] = base["科研就诊编号"].map(lambda v: assign_label(v, proc))

    df = base.merge(adm, on=["科研患者编号", "科研就诊编号"], how="left")

    # ---- 时间与人口学 ----
    df["入院日期"] = pd.to_datetime(df["入院日期"], errors="coerce")
    df["admit_year"] = df["入院日期"].dt.year
    df["age_years"] = pd.to_numeric(df["年龄（岁）"], errors="coerce")
    df["male"] = (df["性别"] == "男性").astype(int)
    df["weight_kg"] = pd.to_numeric(df["体重(kg)"], errors="coerce")
    df["temp_c"] = pd.to_numeric(df["体温"], errors="coerce")
    df["ingest_hours"] = df["主诉"].map(parse_ingestion_hours)
    df["log_ingest_hours"] = np.log1p(df["ingest_hours"])

    # ---- 文本特征 ----
    history = (
        df["主诉"].fillna("") + " " + df["现病史"].fillna("") + " "
        + df["门（急）诊诊断名称"].fillna("") + " " + df["初步诊断"].fillna("")
    )
    exam = history + " " + df["专科情况（体检）"].fillna("") + " " + df["体格检查"].fillna("")

    for name, pat in FB_TYPES.items():
        df[name] = flag(history, pat)
    for name, pat in SYMPTOMS.items():
        df[name] = flag(exam, pat)

    # ---- 影像定位: 取首次 X 线报告 ----
    xray["报告时间"] = pd.to_datetime(xray["报告时间"], errors="coerce")
    xray["text"] = xray["检查所见"].astype(str) + " " + xray["检查结论"].astype(str)
    first_xray = xray.sort_values("报告时间").groupby("科研就诊编号", as_index=False).first()
    for name, pat in LOCATIONS.items():
        first_xray[name] = flag(first_xray["text"], pat)
    first_xray["xray_radiopaque"] = flag(first_xray["text"], r"不透X光异物|不透X线异物|金属异物|异物影")
    df = df.merge(
        first_xray[["科研就诊编号", "xray_radiopaque"] + list(LOCATIONS)],
        on="科研就诊编号", how="left",
    )
    df["has_xray"] = df["xray_radiopaque"].notna().astype(int)

    # ---- 化验 ----
    df = df.merge(earliest_labs(XLSX), on="科研就诊编号", how="left")

    # ---- 结局 ----
    dx["诊断疾病名称"] = dx["诊断疾病名称"].astype(str)
    for name, pat in OUTCOME_PAT.items():
        ids = set(dx.loc[dx["诊断疾病名称"].str.contains(pat), "科研就诊编号"])
        df[name] = df["科研就诊编号"].isin(ids).astype(int)
    df["los_days"] = pd.to_numeric(df["实际住院天数"], errors="coerce")

    # ---- 排除非异物相关手术 ----
    excluded = df["label"].isna().sum()
    df = df[df["label"].notna()].copy()
    df["label"] = df["label"].astype(int)
    df["label_name"] = df["label"].map(LABELS)

    keep = (
        ["科研患者编号", "科研就诊编号", "admit_year", "label", "label_name"]
        + ["age_years", "male", "weight_kg", "temp_c", "ingest_hours", "log_ingest_hours"]
        + list(FB_TYPES) + list(SYMPTOMS) + ["has_xray", "xray_radiopaque"] + list(LOCATIONS)
        + ["lab_wbc", "lab_neut_pct", "lab_hb", "lab_plt", "lab_crp", "lab_alb"]
        + list(OUTCOME_PAT) + ["los_days"]
    )
    cohort = df[keep]
    cohort.to_csv(f"{OUTDIR}/cohort.csv", index=False, encoding="utf-8-sig")

    # ---- 数据概况 ----
    lines = []
    lines.append("=" * 72)
    lines.append("队列概况")
    lines.append("=" * 72)
    lines.append(f"纳入住院次数: {len(cohort)}   唯一患儿: {cohort['科研患者编号'].nunique()}")
    lines.append(f"排除(非异物相关手术): {excluded}")
    lines.append(f"入院年份: {int(cohort['admit_year'].min())} - {int(cohort['admit_year'].max())}")
    lines.append("")
    lines.append("治疗分组:")
    for k, v in cohort["label_name"].value_counts().items():
        lines.append(f"  {k}: {v} ({v / len(cohort) * 100:.1f}%)")
    lines.append("")
    lines.append("按年份 x 治疗:")
    lines.append(pd.crosstab(cohort["admit_year"], cohort["label_name"]).to_string())
    lines.append("")
    lines.append("变量缺失率(%):")
    miss = (cohort.isna().mean() * 100).round(1)
    lines.append(miss[miss > 0].sort_values(ascending=False).to_string())
    lines.append("")
    lines.append("结局:")
    for name in OUTCOME_PAT:
        lines.append(f"  {name}: {int(cohort[name].sum())} ({cohort[name].mean() * 100:.1f}%)")

    report = "\n".join(lines)
    with open(f"{OUTDIR}/data_profile.txt", "w", encoding="utf-8") as fh:
        fh.write(report)
    print(report)
    return cohort


if __name__ == "__main__":
    build()

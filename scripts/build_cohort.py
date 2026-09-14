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

  时相过滤: 影像与化验不仅要"类型正确"，还要"时点正确"。拍摄或报告晚于
  手术开始的结果属于决策后信息，其特征一律置为缺失。判定时刻取自手麻系统的
  「手术开始时间」(精确到分钟); `住院病历手术记录` 的时间字段 100% 为 00:00、
  只有日期，不能用于时序比较，仅在无手麻记录时降级为同日判定。
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


# 异物类型词典。
#
# 词表由 1238 份现病史实测归纳而来，非凭空拟定：初版仅凭常见词，
# 282 例(22.7%)无法归类，实际多为词典缺词而非原文未写——
# 「吸铁磁」「枣胡」「李子核」「游戏币」「围棋子」「体温计水银」等均未收。
# 补全后未归类降至约 15%，其余由人工核验补充(scripts/build_fbtype_form.py)。
#
# 两处易错，勿简化:
#   骨: 必须写成「鱼骨|鸡骨|猪骨|骨头」。裸「骨」会命中「胸骨后疼痛」
#       「锁骨」「喉软骨软化」等非异物语境。
#   针: 「针灸针」「缝纫针」本身就是异物，但「做针灸时」不是。逐词列举而非用裸「针」。
FB_TYPES = {
    "fb_battery": r"纽扣电池|钮扣电池|扣式电池|电池",
    "fb_magnet": r"磁力珠|巴克球|磁珠|磁铁|吸铁石|吸铁磁|磁性|磁体|吸铁",
    "fb_sharp": (r"螺丝钉|螺钉|螺丝|螺丝刀|铁钉|图钉|钉子|订书钉|订书针|耳钉|别针|回形针"
                 r"|绣花针|缝衣针|缝纫针|针灸针|取卡针|大头针|发卡|发夹|刀片|刮胡刀|牙签"
                 r"|铁丝|钢丝|鱼刺|鱼骨|鸡骨|猪骨|骨头|玻璃渣|玻璃片|夹子"),
    "fb_coin": (r"硬币|钱币|游戏币|一元|一角|五角|金属片|铁片|金属五角星|金属饰品"
                r"|戒指|耳环|钥匙|纽扣(?!电池)|拉链|金属手链"),
    "fb_round": r"钢珠|玻璃球|玻璃珠|玻璃弹珠|弹珠|围棋子|棋子|串珠|珠子|滚珠|轴承",
    "fb_pit": r"枣核|枣胡|果核|李子核|西梅核|杏核|桃核|荔枝核|龙眼核|核桃",
    "fb_long": (r"棒棒糖棍|棒棒糖棒|棍|铅笔|钢笔|彩笔|笔套|笔盖|笔帽|卷笔刀|吸管|绳"
                r"|牙刷|弹簧|头发|发丝|筷子|棉签"),
    "fb_plastic": r"塑料|玩具|积木|橡皮|贴纸|海绵",
    "fb_mercury": r"水银|体温计",
    "fb_multiple": r"多发|两枚|三枚|数枚|多枚|多个|数个|\d+\s*[颗枚粒个块]",
}

# 症状/体征。
#
# 直接用正则找关键词会严重高估：病历模板总会把体征写全，
# 「全腹压痛阴性，反跳痛阴性」里同样含「压痛」「反跳痛」。
# 早期版本据此得出压痛阳性率 99.5%(1232/1238)，实际仅约 7.4%。
#
# 改为分句级否定作用域：按标点切分，若否定词出现在症状词之前，判为阴性。
# 这同时覆盖两种写法——「无恶心、无呕吐」(逐项带否定) 与
# 「无恶心呕吐」(一个否定词管两项)。
# 冒号必须切分: 「压痛：无」若不切，否定词落在症状词之后会被误判为阳性。
CLAUSE_SPLIT = r"[。；;，,、：:\n]"
NEGATORS = r"无|未见|未闻|未及|未触及|未出现|不伴|否认|阴性|\(-\)|（-）"

SYMPTOMS = {
    "sym_abdpain": r"腹痛",
    "sym_vomit": r"呕吐",
    "sym_hematemesis": r"呕血|黑便|便血|血便",
    "sym_fever": r"发热|发烧",
    "sym_dysphagia": r"流涎|吞咽困难|拒食|不能进食|吞咽疼痛",
    "sym_distension": r"腹胀",
}

# 体征在病历中以「阳性/阴性」记录，须按该记法判读，不能只找关键词。
#
# 只取 `专科情况（体检）`——那是腹部专科查体。`体格检查` 是全身查体，
# 含乳突、副鼻窦、甲状腺的压痛描述，混进来会把耳鼻喉的体征当成腹部体征。
SIGNS = {
    "sign_tenderness": r"压痛",
    "sign_peritoneal": r"反跳痛|肌紧张|板状腹|腹膜刺激征",
}
POSITIVE_MARK = r"\s*[（(]?\s*(?:阳性|\+|＋)"

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


def assert_positive(series, pattern):
    """分句级否定作用域：某一分句内，否定词出现在症状词之前则该句不算阳性。

    只要有任意一个分句作出阳性陈述即判为 1。
    """
    neg = re.compile(NEGATORS)
    sym = re.compile(pattern)
    split = re.compile(CLAUSE_SPLIT)

    def judge(text):
        for clause in split.split(str(text)):
            m = sym.search(clause)
            if not m:
                continue
            n = neg.search(clause)
            if n is None or n.start() > m.start():
                return 1
        return 0

    return series.fillna("").map(judge).astype(int)


def sign_positive(series, pattern):
    """体征按「阳性/阴性」记法判读；无该记法时回退到分句级否定。"""
    explicit = series.str.contains(f"(?:{pattern}){POSITIVE_MARK}", regex=True, na=False)
    has_mark = series.str.contains(
        f"(?:{pattern})\\s*[（(]?\\s*(?:阳性|阴性|\\+|＋|-|－)", regex=True, na=False)
    fallback = assert_positive(series, pattern).astype(bool)
    return np.where(has_mark, explicit, fallback).astype(int)


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
    # CRP 仍然抽取，但不作预测因子: 缺失 68.7% 且与治疗方式相关(内镜组 85.0% 无 CRP)。
    # 保留它是为了 Table 1 的基线描述、缺失机制诊断，以及敏感性分析 S6 的对照。
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


def earliest_labs(path, exact, date_only):
    """每次住院取报告时间最早的一次检验，并按时相过滤。

    报告时间晚于手术开始的化验属于决策后信息，其数值置为缺失。
    该判定偏保守——标本多在报告前数小时采集(中位提前 3.8 h)，
    但只有报告时间可用，宁可少用也不引入泄漏。
    """
    out = []
    for sheet, mapping in LAB_ITEMS.items():
        df = pd.read_excel(path, sheet_name=sheet)
        df["报告时间"] = pd.to_datetime(df["报告时间"], errors="coerce")
        if sheet.endswith("（CRP）测定"):
            df["超敏C反应蛋白定量-定量结果"] = resolve_censored(
                df["超敏C反应蛋白定量-定量结果"], df["超敏C反应蛋白定量-定性结果"]
            )
        df = df.sort_values("报告时间").groupby("就诊编号", as_index=False).first()
        keep = df[["就诊编号", "报告时间"] + list(mapping.values())].rename(
            columns={v: k for k, v in mapping.items()})
        keep = keep.rename(columns={"就诊编号": "科研就诊编号", "报告时间": f"_t_{sheet}"})
        out.append(keep)

    labs = out[0]
    for extra in out[1:]:
        labs = labs.merge(extra, on="科研就诊编号", how="outer")

    value_cols = [c for m in LAB_ITEMS.values() for c in m]
    for col in value_cols:
        labs[col] = pd.to_numeric(labs.get(col), errors="coerce")

    # 每张表各自判定时相，逐表置空，最后汇总一个总体标记
    time_cols = [c for c in labs.columns if c.startswith("_t_")]
    predecision_any = pd.Series(False, index=labs.index)
    for sheet, mapping in LAB_ITEMS.items():
        tcol = f"_t_{sheet}"
        phase = decision_phase(labs["科研就诊编号"], labs[tcol], exact, date_only)
        keep_mask = phase.isin(PREDECISION_PHASES)
        labs = blank_out(labs, list(mapping), keep_mask)
        predecision_any |= keep_mask & labs[tcol].notna()
    labs["lab_predecision"] = predecision_any.astype(int)
    return labs.drop(columns=time_cols)


# --------------------------------------------------------------------------
# 4. 决策时点: 判定某项检查是否在治疗决策之前完成
# --------------------------------------------------------------------------
# 可用于建模的时相。"无手术"者本次住院无操作，入院时的检查均在决策之前。
PREDECISION_PHASES = {"术前", "无手术"}


def operation_times(path):
    """返回 (精确手术开始时刻, 仅日期的手术日期)。

    手麻系统的「手术开始时间」精确到分钟，是唯一可用于时序比较的字段。
    `住院病历手术记录.手术日期及时间` 全部为 00:00，只有日期。
    """
    sa = pd.read_excel(path, sheet_name="手麻系统信息")
    exact = (sa.assign(t=pd.to_datetime(sa["手术开始时间"], errors="coerce"))
               .dropna(subset=["t"]).groupby("科研就诊编号")["t"].min())

    op = pd.read_excel(path, sheet_name="住院病历手术记录")
    dates = pd.to_datetime(op["手术日期及时间"], errors="coerce").dt.normalize()
    date_only = (op.assign(d=dates).dropna(subset=["d"])
                   .groupby("科研就诊编号")["d"].min())
    return exact, date_only


def decision_phase(visits, times, exact, date_only):
    """逐条判定检查时刻相对手术开始的时相。

    返回值: 术前 / 决策后 / 同日不明 / 无手术 / 时间缺失
    「同日不明」= 手术仅有日期、检查与之同日，无法判断先后，保守起见不作预测因子。
    """
    e = visits.map(exact)
    d = visits.map(date_only)
    t = pd.to_datetime(times, errors="coerce")

    phase = pd.Series("无手术", index=visits.index, dtype=object)
    phase[t.isna()] = "时间缺失"

    has_exact = e.notna() & t.notna()
    phase[has_exact & (t < e)] = "术前"
    phase[has_exact & (t >= e)] = "决策后"

    only_date = e.isna() & d.notna() & t.notna()
    day = t.dt.normalize()
    phase[only_date & (day < d)] = "术前"
    phase[only_date & (day > d)] = "决策后"
    phase[only_date & (day == d)] = "同日不明"
    return phase


def blank_out(df, columns, keep_mask):
    """把不满足 keep_mask 的行在指定列上置为缺失。"""
    for col in columns:
        df.loc[~keep_mask, col] = np.nan
    return df


# --------------------------------------------------------------------------
# 5. 结局(仅用于标签校验与描述，不作预测因子)
# --------------------------------------------------------------------------
# 编码诊断「因病人家属原因未进行操作」= 计划中的操作因家属拒绝而未执行。
# 这类病例会被记为「观察」，但并非医师判断可以观察——标签含义不同，须单列。
# 文本里的「家长要求出院」不可用作同类标记：359 例中含 137 例内镜、22 例手术，
# 多为治疗完成后的常规出院用语，不特异。
FAMILY_DECLINED_PAT = r"家属原因未进行操作|家属原因未进行"

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
    exact, date_only = operation_times(XLSX)

    df = base.merge(adm, on=["科研患者编号", "科研就诊编号"], how="left")

    # ---- 时间与人口学 ----
    df["入院日期"] = pd.to_datetime(df["入院日期"], errors="coerce")
    df["admit_year"] = df["入院日期"].dt.year
    # 同一患儿的首次住院标记，供「仅首次住院」的敏感性分析使用。
    # 只存布尔值不存日期: cohort.csv 会进版本库，精确日期会降低去标识化程度。
    df["first_admission"] = (
        df["入院日期"].rank(method="first").groupby(df["科研患者编号"]).transform("min")
        == df["入院日期"].rank(method="first")
    ).astype(int)
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
    abdominal_exam = df["专科情况（体检）"].fillna("")

    for name, pat in FB_TYPES.items():
        df[name] = flag(history, pat)
    for name, pat in SYMPTOMS.items():
        df[name] = assert_positive(history, pat)
    for name, pat in SIGNS.items():
        df[name] = sign_positive(abdominal_exam, pat)

    # ---- 影像定位: 取首次 X 线，按检查时间(而非报告时间)排序 ----
    # 决策依据是拍片时刻；报告可能滞后数小时，用报告时间会错判时序。
    xray["检查时间"] = pd.to_datetime(xray["检查时间"], errors="coerce")
    xray["text"] = xray["检查所见"].astype(str) + " " + xray["检查结论"].astype(str)
    first_xray = xray.sort_values("检查时间").groupby("科研就诊编号", as_index=False).first()
    for name, pat in LOCATIONS.items():
        first_xray[name] = flag(first_xray["text"], pat)
    first_xray["xray_radiopaque"] = flag(
        first_xray["text"], r"不透X光异物|不透X线异物|金属异物|异物影")
    first_xray["xray_phase"] = decision_phase(
        first_xray["科研就诊编号"], first_xray["检查时间"], exact, date_only)

    # 首次片晚于手术开始者，本次住院没有决策前影像，其影像特征一律置空
    keep_mask = first_xray["xray_phase"].isin(PREDECISION_PHASES)
    first_xray = blank_out(first_xray, ["xray_radiopaque"] + list(LOCATIONS), keep_mask)

    df = df.merge(
        first_xray[["科研就诊编号", "xray_phase", "xray_radiopaque"] + list(LOCATIONS)],
        on="科研就诊编号", how="left",
    )
    df["xray_phase"] = df["xray_phase"].fillna("无影像")
    df["has_xray"] = df["xray_radiopaque"].notna().astype(int)

    # ---- 化验 ----
    df = df.merge(earliest_labs(XLSX, exact, date_only), on="科研就诊编号", how="left")
    df["lab_predecision"] = df["lab_predecision"].fillna(0).astype(int)

    # ---- 结局 ----
    dx["诊断疾病名称"] = dx["诊断疾病名称"].astype(str)
    declined = set(dx.loc[dx["诊断疾病名称"].str.contains(FAMILY_DECLINED_PAT),
                          "科研就诊编号"])
    df["family_declined"] = df["科研就诊编号"].isin(declined).astype(int)
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
        ["科研患者编号", "科研就诊编号", "admit_year", "first_admission", "label", "label_name"]
        + ["age_years", "male", "weight_kg", "temp_c", "ingest_hours", "log_ingest_hours"]
        + list(FB_TYPES) + list(SYMPTOMS) + list(SIGNS)
        + ["xray_phase", "has_xray", "xray_radiopaque"] + list(LOCATIONS)
        + ["lab_predecision", "lab_wbc", "lab_neut_pct", "lab_hb", "lab_plt", "lab_crp", "lab_alb"]
        + list(OUTCOME_PAT) + ["family_declined", "los_days"]
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
    lines.append(f"首次住院 {int(cohort['first_admission'].sum())} 例"
                 f"（再入院 {len(cohort) - int(cohort['first_admission'].sum())} 例）")
    lines.append("")
    lines.append("影像时相(首次 X 线相对手术开始):")
    for k, v in cohort["xray_phase"].value_counts().items():
        usable = " <- 可用于建模" if k in PREDECISION_PHASES else ""
        lines.append(f"  {k}: {v}{usable}")
    lines.append(f"  可用影像特征的病例: {int(cohort['has_xray'].sum())}")
    lines.append("")
    lines.append(f"决策前化验可用: {int(cohort['lab_predecision'].sum())}")
    lines.append("")
    n_dec = int(cohort["family_declined"].sum())
    lines.append(f"因家属拒绝而未操作: {n_dec} 例"
                 f"（均记为观察组：{int(cohort.loc[cohort['family_declined'] == 1, 'label'].eq(0).sum())}）")
    lines.append("  这些病例并非医师判断可观察，标签含义不同，须做剔除后的敏感性分析。")
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

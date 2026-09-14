# -*- coding: utf-8 -*-
"""
生成 Table 1：三组（观察 / 内镜 / 手术）基线特征比较。

输出:
  outputs/table1.csv    纯数据，便于二次加工
  outputs/table1.md     仓库内查阅
  outputs/Table1.docx   投稿用三线表，可直接粘入 Word 稿件

统计方法:
  连续变量  中位数(IQR)，Kruskal-Wallis 检验，效应量 epsilon^2
  分类变量  n(%)，Pearson 卡方；任一期望频数 <5 时改用蒙特卡洛置换检验
            （SciPy 的 fisher_exact 仅支持 2x2，RxC 用置换更稳妥），效应量 Cramer's V

只纳入治疗决策时点之前可获得的变量。结局与并发症不属于基线特征，
另见 outputs/table2_outcomes.*。
"""
import os

import numpy as np
import pandas as pd
from scipy import stats

RNG = np.random.default_rng(20260914)
N_PERM = 10000
GROUPS = ["观察", "内镜", "手术"]

# (显示名, 列名, 类型)  类型: cont 连续 / bin 二分类
ROWS = [
    ("__人口学__", None, None),
    ("年龄，岁", "age_years", "cont"),
    ("体重，kg", "weight_kg", "cont"),
    ("男性", "male", "bin"),

    ("__误食史__", None, None),
    ("误食至就诊时长，h", "ingest_hours", "cont"),

    ("__异物类型__", None, None),
    ("纽扣电池", "fb_battery", "bin"),
    ("磁性异物", "fb_magnet", "bin"),
    ("尖锐异物", "fb_sharp", "bin"),
    ("硬币或金属片", "fb_coin", "bin"),
    ("枣核或果核", "fb_pit", "bin"),
    ("长条状异物", "fb_long", "bin"),
    ("塑料或玩具", "fb_plastic", "bin"),
    ("多发异物", "fb_multiple", "bin"),

    ("__症状与体征__", None, None),
    ("体温，°C", "temp_c", "cont"),
    ("腹痛", "sym_abdpain", "bin"),
    ("呕吐", "sym_vomit", "bin"),
    ("呕血或黑便", "sym_hematemesis", "bin"),
    ("发热", "sym_fever", "bin"),
    ("吞咽困难或流涎", "sym_dysphagia", "bin"),
    ("腹胀", "sym_distension", "bin"),
    ("腹部压痛", "sign_tenderness", "bin"),
    ("腹膜刺激征", "sign_peritoneal", "bin"),

    ("__影像（决策前首次 X 线）__", None, None),
    ("有决策前 X 线", "has_xray", "bin"),
    ("不透 X 线异物", "xray_radiopaque", "bin"),
    ("食管", "loc_esophagus", "bin"),
    ("胃", "loc_stomach", "bin"),
    ("十二指肠", "loc_duodenum", "bin"),
    ("小肠", "loc_smallbowel", "bin"),
    ("结直肠", "loc_colorectal", "bin"),

    ("__实验室（决策前首次结果）__", None, None),
    ("白细胞计数，10^9/L", "lab_wbc", "cont"),
    ("中性粒细胞百分比，%", "lab_neut_pct", "cont"),
    ("白蛋白，g/L", "lab_alb", "cont"),
    ("C 反应蛋白，mg/L", "lab_crp", "cont"),
]

OUTCOME_ROWS = [
    ("穿孔", "out_perforation", "bin"),
    ("肠梗阻", "out_obstruction", "bin"),
    ("腹膜炎", "out_peritonitis", "bin"),
    ("消化道瘘", "out_fistula", "bin"),
    ("脓毒症", "out_sepsis", "bin"),
    ("狭窄", "out_stricture", "bin"),
    ("住院天数", "los_days", "cont"),
]


def fmt_p(p):
    if pd.isna(p):
        return "—"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def median_iqr(x):
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) == 0:
        return "—"
    return f"{x.median():.1f} ({x.quantile(.25):.1f}–{x.quantile(.75):.1f})"


def n_pct(x):
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) == 0:
        return "—"
    return f"{int(x.sum())} ({x.mean() * 100:.1f})"


def kruskal(df, col):
    """Kruskal-Wallis + epsilon^2 效应量。"""
    arrays = [pd.to_numeric(df.loc[df["label_name"] == g, col], errors="coerce").dropna()
              for g in GROUPS]
    if any(len(a) < 2 for a in arrays):
        return np.nan, np.nan
    h, p = stats.kruskal(*arrays)
    n = sum(len(a) for a in arrays)
    eps2 = (h - len(arrays) + 1) / (n - len(arrays)) if n > len(arrays) else np.nan
    return p, max(eps2, 0.0)


def chi_or_perm(df, col):
    """卡方；期望频数不足时改用置换检验。返回 (p, Cramer's V, 是否用了置换)。"""
    sub = df[["label_name", col]].dropna()
    table = pd.crosstab(sub["label_name"], sub[col])
    if table.shape[0] < 2 or table.shape[1] < 2:
        return np.nan, np.nan, False
    chi2, p, _, expected = stats.chi2_contingency(table)
    n = table.to_numpy().sum()
    v = np.sqrt(chi2 / (n * (min(table.shape) - 1))) if n else np.nan

    if expected.min() < 5:
        p = permutation_chi2(sub["label_name"], sub[col], chi2)
        return p, v, True
    return p, v, False


def _chi2_stat(counts):
    """由 RxC 频数矩阵直接算卡方统计量，避开 pandas，置换循环才跑得动。"""
    n = counts.sum()
    if n == 0:
        return 0.0
    exp = np.outer(counts.sum(1), counts.sum(0)) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(exp > 0, (counts - exp) ** 2 / exp, 0.0)
    return float(terms.sum())


def permutation_chi2(groups, values, observed_chi2, n_perm=N_PERM):
    """在组标签上做置换，得到卡方统计量的经验 P 值。

    期望频数 <5 时卡方的渐近分布不可靠，而 SciPy 的 fisher_exact 仅支持 2x2，
    RxC 用置换最稳妥。
    """
    g, lv_g = pd.factorize(groups)
    v, lv_v = pd.factorize(values)
    k, m = len(lv_g), len(lv_v)
    base = np.bincount(g * m + v, minlength=k * m).reshape(k, m)
    if _chi2_stat(base) == 0:
        return 1.0

    extreme = 0
    for _ in range(n_perm):
        pv = RNG.permutation(v)
        c = np.bincount(g * m + pv, minlength=k * m).reshape(k, m)
        extreme += _chi2_stat(c) >= observed_chi2 - 1e-12
    return (extreme + 1) / (n_perm + 1)


def build_block(df, rows, with_total=True):
    out, perm_used = [], []
    counts = df["label_name"].value_counts()
    for label, col, kind in rows:
        if col is None:
            out.append({"变量": label.strip("_"), "__section__": True})
            continue
        miss = int(df[col].isna().sum())
        rec = {"变量": label, "__section__": False,
               "缺失": miss if miss else ""}
        if kind == "cont":
            for g in GROUPS:
                rec[g] = median_iqr(df.loc[df["label_name"] == g, col])
            if with_total:
                rec["合计"] = median_iqr(df[col])
            p, eff = kruskal(df, col)
            rec["P 值"], rec["效应量"] = fmt_p(p), ("" if pd.isna(eff) else f"{eff:.3f}")
        else:
            for g in GROUPS:
                rec[g] = n_pct(df.loc[df["label_name"] == g, col])
            if with_total:
                rec["合计"] = n_pct(df[col])
            p, v, used = chi_or_perm(df, col)
            rec["P 值"], rec["效应量"] = fmt_p(p), ("" if pd.isna(v) else f"{v:.3f}")
            if used:
                perm_used.append(label)
        out.append(rec)

    header = {"变量": "例数", "__section__": False, "缺失": ""}
    for g in GROUPS:
        header[g] = f"{int(counts.get(g, 0))}"
    if with_total:
        header["合计"] = f"{len(df)}"
    header["P 值"] = ""
    header["效应量"] = ""
    return [header] + out, perm_used


def to_frame(records, with_total=True):
    cols = ["变量"] + GROUPS + (["合计"] if with_total else []) + ["缺失", "P 值", "效应量"]
    df = pd.DataFrame(records)
    for c in cols:
        if c not in df:
            df[c] = ""
    return df[cols + ["__section__"]].fillna("")


def write_markdown(path, title, frame, notes):
    cols = [c for c in frame.columns if c != "__section__"]
    lines = [f"### {title}", "", "| " + " | ".join(cols) + " |",
             "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in frame.iterrows():
        if r["__section__"]:
            lines.append(f"| **{r['变量']}** |" + " |" * (len(cols) - 1))
        else:
            lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    lines += ["", *notes]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def write_docx(path, blocks):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(9)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    def rule(row, position, size=12):
        """三线表: 只在表首、表头下、表尾画横线。"""
        for cell in row.cells:
            borders = OxmlElement("w:tcBorders")
            el = OxmlElement(f"w:{position}")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(size))
            el.set(qn("w:color"), "000000")
            borders.append(el)
            cell._tc.get_or_add_tcPr().append(borders)

    for title, frame, notes in blocks:
        h = doc.add_paragraph()
        run = h.add_run(title)
        run.bold = True
        run.font.size = Pt(10.5)

        cols = [c for c in frame.columns if c != "__section__"]
        table = doc.add_table(rows=1, cols=len(cols))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True

        hdr = table.rows[0]
        for i, c in enumerate(cols):
            p = hdr.cells[i].paragraphs[0]
            p.add_run(c).bold = True
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
        rule(hdr, "top", 18)
        rule(hdr, "bottom")

        last = None
        for _, r in frame.iterrows():
            row = table.add_row()
            if r["__section__"]:
                run = row.cells[0].paragraphs[0].add_run(r["变量"])
                run.bold = True
                run.italic = True
            else:
                for i, c in enumerate(cols):
                    p = row.cells[i].paragraphs[0]
                    p.add_run(str(r[c]))
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
            last = row
        if last is not None:
            rule(last, "bottom", 18)

        for n in notes:
            p = doc.add_paragraph()
            run = p.add_run(n)
            run.font.size = Pt(8)
        doc.add_paragraph()

    doc.save(path)


def main():
    os.makedirs("outputs", exist_ok=True)
    df = pd.read_csv("outputs/cohort.csv")

    recs, perm = build_block(df, ROWS)
    t1 = to_frame(recs)
    notes1 = [
        "连续变量以中位数（四分位距）表示，采用 Kruskal-Wallis 检验，效应量为 epsilon²；"
        "分类变量以 n（%）表示，采用 Pearson 卡方检验，效应量为 Cramér's V。",
        f"期望频数不足 5 的变量改用蒙特卡洛置换检验（{N_PERM} 次重抽样）："
        + ("、".join(perm) if perm else "无"),
        "「缺失」列为该变量的缺失例数；空白表示无缺失。",
        "仅纳入治疗决策时点之前可获得的变量。影像与实验室结果已按时相过滤，"
        "拍摄或报告晚于手术开始者不予纳入。",
        "C 反应蛋白缺失 68.7% 且缺失与治疗方式相关（内镜组 85.0% 缺失），"
        "故列于此仅作描述，未纳入预测模型。",
        "P 值为描述性比较，未针对多重检验作校正。",
    ]

    orecs, operm = build_block(df, OUTCOME_ROWS)
    t2 = to_frame(orecs)
    notes2 = [
        "结局与并发症为治疗后信息，不属于基线特征，仅用于描述与标签校验，未进入预测模型。",
        f"期望频数不足 5 的变量改用蒙特卡洛置换检验（{N_PERM} 次重抽样）："
        + ("、".join(operm) if operm else "无"),
    ]

    t1.drop(columns="__section__").to_csv("outputs/table1.csv", index=False, encoding="utf-8-sig")
    t2.drop(columns="__section__").to_csv("outputs/table2_outcomes.csv", index=False,
                                          encoding="utf-8-sig")
    write_markdown("outputs/table1.md", "Table 1　三组基线特征比较", t1, notes1)
    write_markdown("outputs/table2_outcomes.md", "Table 2　三组结局与并发症比较", t2, notes2)
    write_docx("outputs/Table1.docx",
               [("Table 1　三组基线特征比较", t1, notes1),
                ("Table 2　三组结局与并发症比较", t2, notes2)])

    print(t1.drop(columns="__section__").to_string(index=False))
    print()
    print(t2.drop(columns="__section__").to_string(index=False))
    print("\n已写出 outputs/table1.{csv,md}、table2_outcomes.{csv,md}、Table1.docx")
    if perm:
        print(f"使用置换检验的变量: {'、'.join(perm)}")


if __name__ == "__main__":
    main()

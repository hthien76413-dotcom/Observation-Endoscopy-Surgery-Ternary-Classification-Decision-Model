# -*- coding: utf-8 -*-
"""
按患者编号汇出完整病程，供人工病历回顾。

用法:
    python3 scripts/case_review.py 3682242 36109560

输出 outputs/case_review.txt（默认不入版本库，见 .gitignore）——
该文件把单个患儿的自由文本病历集中在一处，比原始表格更易识别个人，
故只在本地查阅，不提交、不作为补充材料。
"""
import sys

import pandas as pd

XLSX = "10年消化道异物原始数据.xlsx"

# (工作表, 患者列, 就诊列, 时间列, 要显示的字段)
SOURCES = [
    ("儿科入院记录", "科研患者编号", "科研就诊编号", None,
     ["主诉", "现病史", "既往史", "专科情况（体检）", "体温", "体重(kg)", "初步诊断"]),
    ("X线报告", "科研患者编号", "科研就诊编号", "检查时间",
     ["报告名称", "检查时间", "检查所见", "检查结论"]),
    ("CT报告", "科研患者编号", "科研就诊编号", "检查时间",
     ["报告名称", "检查时间", "检查所见", "检查结论"]),
    ("超声报告", "科研患者编号", "科研就诊编号", "超声检查时间",
     ["超声报告名称", "超声检查时间", "超声检查所见", "超声检查结论"]),
    ("手麻系统信息", "科研患者编号", "科研就诊编号", "手术开始时间",
     ["手术名称", "手术类别", "麻醉方式", "手术开始时间", "手术结束时间", "手术持续时间"]),
    ("住院病历手术记录", "科研患者编号", "科研就诊编号", "手术日期及时间",
     ["手术日期及时间", "术中诊断", "手术名称", "手术经过"]),
    ("住院病历出院记录", "科研患者编号", "科研就诊编号", None,
     ["入院情况", "诊疗经过", "出院诊断", "出院情况", "出院医嘱"]),
]

LABS = [("实验室检查_血常规", ["白细胞计数定量-定量结果", "中性粒细胞百分数定量-定量结果",
                              "血红蛋白浓度定量-定量结果", "血小板计数定量-定量结果"]),
        ("实验室检查_血C反应蛋白（CRP）测定", ["超敏C反应蛋白定量-定量结果",
                                              "超敏C反应蛋白定量-定性结果"])]


def show(v):
    t = str(v).strip()
    return "（空）" if t in ("", "nan", "NaT") else t


def review(pids):
    base = pd.read_excel(XLSX, sheet_name="病案首页基本信息")
    dx = pd.read_excel(XLSX, sheet_name="病案出院诊断编目后")
    base["入院"] = pd.to_datetime(base["入院日期"], errors="coerce")
    base["出院"] = pd.to_datetime(base["出院日期"], errors="coerce")

    sheets = {}
    for name, *_ in SOURCES:
        sheets[name] = pd.read_excel(XLSX, sheet_name=name)
    lab_data = {n: pd.read_excel(XLSX, sheet_name=n) for n, _ in LABS}

    out = []
    a = out.append
    for pid in pids:
        pid = int(pid)
        adms = base[base["科研患者编号"] == pid].sort_values("入院")
        if adms.empty:
            a(f"未找到患者 {pid}")
            continue
        a("=" * 78)
        a(f"患者 {pid}　共 {len(adms)} 次住院")
        a("=" * 78)

        for k, (_, r) in enumerate(adms.iterrows(), start=1):
            visit = r["科研就诊编号"]
            a("")
            a("─" * 78)
            a(f"第 {k} 次住院　就诊编号 {visit}")
            a(f"  {r['性别']}，{r['年龄（岁）']:.1f} 岁　"
              f"入院 {r['入院']}　出院 {r['出院']}　住院 {r['实际住院天数']} 天")
            a(f"  入院科别：{show(r['入院科别'])}　门急诊诊断：{show(r['门（急）诊诊断名称'])}")
            a("─" * 78)

            for name, _pc, vc, tcol, fields in SOURCES:
                df = sheets[name]
                sub = df[df[vc] == visit]
                if sub.empty:
                    continue
                if tcol and tcol in sub.columns:
                    sub = sub.sort_values(tcol)
                a("")
                a(f"【{name}】")
                for _, row in sub.iterrows():
                    for f in fields:
                        if f in row.index:
                            a(f"  {f}: {show(row[f])}")
                    if len(sub) > 1:
                        a("  " + "·" * 40)

            a("")
            a("【出院诊断】")
            d = dx[dx["科研就诊编号"] == visit]
            for _, row in d.iterrows():
                a(f"  {show(row['诊断疾病名称'])}"
                  f"（主要诊断：{show(row['是否主要诊断'])}，"
                  f"入院病情：{show(row['入院病情'])}，"
                  f"出院情况：{show(row['出院情况'])}）")

            a("")
            a("【实验室】")
            for sheet, cols in LABS:
                ld = lab_data[sheet]
                sub = ld[ld["就诊编号"] == visit]
                if sub.empty:
                    continue
                sub = sub.sort_values("报告时间")
                for _, row in sub.iterrows():
                    vals = ", ".join(f"{c.split('-')[0]}={show(row[c])}"
                                     for c in cols if c in row.index)
                    a(f"  {show(row['报告时间'])}  {vals}")
        a("")

    text = "\n".join(out)
    with open("outputs/case_review.txt", "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    review(sys.argv[1:])

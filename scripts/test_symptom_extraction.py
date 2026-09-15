# -*- coding: utf-8 -*-
"""症状与体征抽取的分句否定测试。

早期版本把「全腹压痛阴性」也算作压痛阳性，导致阳性率 99.5%。
这些用例钉住修正后的行为。
"""
import sys

import pandas as pd

sys.path.insert(0, "scripts")
from build_cohort import SIGNS, SYMPTOMS, assert_positive, sign_positive  # noqa: E402


CASES_SYM = [
    ("无恶心、无呕吐、无腹痛", "sym_vomit", 0, "逐项带否定"),
    ("无恶心、无呕吐、无腹痛", "sym_abdpain", 0, "逐项带否定"),
    ("无恶心呕吐", "sym_vomit", 0, "一个否定词管两项"),
    ("无恶心、伴呕吐、伴腹痛", "sym_vomit", 1, "同句中部分阳性"),
    ("无恶心、伴呕吐、伴腹痛", "sym_abdpain", 1, "同句中部分阳性"),
    ("阵发性右下腹痛", "sym_abdpain", 1, "无否定词的阳性描述"),
    ("患儿误食硬币，无发热，伴呕吐 3 次", "sym_fever", 0, "长句中的否定"),
    ("患儿误食硬币，无发热，伴呕吐 3 次", "sym_vomit", 1, "长句中的阳性"),
    ("否认腹痛", "sym_abdpain", 0, "否认式否定"),
    ("未出现呕吐", "sym_vomit", 0, "未出现"),
    ("呕血 2 次", "sym_hematemesis", 1, "呕血"),
    ("", "sym_vomit", 0, "空文本"),
]

CASES_SIGN = [
    ("腹部软，全腹压痛阴性，反跳痛阴性", "sign_tenderness", 0, "阴性记法"),
    ("腹部软，全腹压痛阴性，反跳痛阴性", "sign_peritoneal", 0, "阴性记法"),
    ("腹部软，脐周压痛阳性，反跳痛阴性", "sign_tenderness", 1, "阳性记法"),
    ("腹部软，脐周压痛阳性，反跳痛阴性", "sign_peritoneal", 0, "同句一阳一阴"),
    ("压痛（+），反跳痛（-）", "sign_tenderness", 1, "括号加号"),
    ("压痛（+），反跳痛（-）", "sign_peritoneal", 0, "括号减号"),
    ("全腹肌紧张阳性", "sign_peritoneal", 1, "肌紧张阳性"),
    ("腹部平软，无压痛", "sign_tenderness", 0, "无阴阳记法时回退到否定作用域"),
    ("腹部拒按，有压痛", "sign_tenderness", 1, "无阴阳记法时的阳性"),
]


def run():
    fails = []
    for text, field, want, why in CASES_SYM:
        got = int(assert_positive(pd.Series([text]), SYMPTOMS[field]).iloc[0])
        (print(f"  OK  {field:<18} {why}") if got == want
         else fails.append(f"  {field} «{text}» 期望 {want} 实得 {got}  ({why})"))
    for text, field, want, why in CASES_SIGN:
        got = int(sign_positive(pd.Series([text]), SIGNS[field])[0])
        (print(f"  OK  {field:<18} {why}") if got == want
         else fails.append(f"  {field} «{text}» 期望 {want} 实得 {got}  ({why})"))
    assert not fails, "抽取错误:\n" + "\n".join(fails)
    print("\n全部通过")


if __name__ == "__main__":
    run()

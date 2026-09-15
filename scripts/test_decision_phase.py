# -*- coding: utf-8 -*-
"""decision_phase 的分支测试。时相判错会直接导致信息泄漏或白丢数据，值得钉住。"""
import sys

import pandas as pd

sys.path.insert(0, "scripts")
from build_cohort import PREDECISION_PHASES, blank_out, decision_phase  # noqa: E402

T = pd.Timestamp


def run():
    exact = pd.Series({"A": T("2024-05-10 14:00"), "B": T("2024-05-10 09:00")})
    date_only = pd.Series({"C": T("2024-05-10"), "D": T("2024-05-10"), "E": T("2024-05-10")})

    cases = [
        ("A", T("2024-05-10 08:00"), "术前",    "精确时刻，检查在手术前"),
        ("A", T("2024-05-10 14:00"), "决策后",  "与手术开始同一分钟，保守判为决策后"),
        ("A", T("2024-05-10 16:00"), "决策后",  "精确时刻，检查在手术后"),
        ("B", T("2024-05-09 23:00"), "术前",    "跨日仍按精确时刻判定"),
        ("C", T("2024-05-09 23:00"), "术前",    "仅日期，检查早一天"),
        ("D", T("2024-05-10 07:00"), "同日不明", "仅日期且同日，无法判先后"),
        ("E", T("2024-05-11 07:00"), "决策后",  "仅日期，检查晚一天"),
        ("Z", T("2024-05-10 07:00"), "无手术",  "无任何手术记录"),
        ("A", pd.NaT,                "时间缺失", "检查时间缺失"),
    ]
    visits = pd.Series([c[0] for c in cases])
    times = pd.Series([c[1] for c in cases])
    got = decision_phase(visits, times, exact, date_only)

    failures = []
    for i, (v, t, want, why) in enumerate(cases):
        if got[i] != want:
            failures.append(f"  就诊={v} 时刻={t} 期望={want} 实得={got[i]}  ({why})")
        else:
            print(f"  OK  {want:<6} {why}")
    assert not failures, "时相判定错误:\n" + "\n".join(failures)

    usable = got.isin(PREDECISION_PHASES)
    assert usable.tolist() == [True, False, False, True, True, False, False, True, False], \
        f"可用掩码不符: {usable.tolist()}"
    print(f"  OK  可用于建模的时相仅 {sorted(PREDECISION_PHASES)}，「同日不明」「时间缺失」均排除")

    df = pd.DataFrame({"v": [1, 2, 3], "loc": [1, 1, 1], "other": [9, 9, 9]})
    df = blank_out(df, ["loc"], pd.Series([True, False, True]))
    assert df["loc"].isna().tolist() == [False, True, False], "blank_out 置空位置错误"
    assert df["other"].tolist() == [9, 9, 9], "blank_out 误伤了未指定的列"
    print("  OK  blank_out 只置空指定列的指定行")

    print("\n全部通过")


if __name__ == "__main__":
    run()

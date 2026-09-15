# -*- coding: utf-8 -*-
"""
生成 Fig 3：异物类型 → 治疗方式 → 结局 的桑基（冲积）图。

输出 outputs/figures/fig3_sankey.{pdf,png}

**为什么暂时不画「位置」环**：方案原定四段（类型→位置→治疗→结局），但目前
1238 例中仅 193 例（15.6%）能从 X 线报告文本定位到具体消化道节段，
其余会全部挤进一个「未定位」节点，既不美观也无信息。
`outputs/xray_annotation.csv` 一旦生成（X 线重标注回流），本脚本会**自动插入**
该环，无需改代码。

**配色**：流按治疗方式着色，沿用与 Fig 1/2 及 ROC/校准/DCA 相同的三色系
（已通过色盲分辨度校验）。节点用中性灰，不与流争色。这样读者顺着颜色
就能看出「哪类异物流向手术」。
"""
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.path import Path  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402

MGMT_COLORS = {"手术": "#BE3241", "内镜": "#0A7EA4", "观察": "#5C8A1E"}
MGMT_ORDER = ["手术", "内镜", "观察"]
OUTCOME_ORDER = ["穿孔", "其他并发症", "无并发症"]
EN = {
    "手术": "Surgery", "内镜": "Endoscopy", "观察": "Observation",
    "穿孔": "Perforation", "其他并发症": "Other complication", "无并发症": "Uncomplicated",
    "磁性异物": "Magnetic", "纽扣电池": "Button battery", "尖锐异物": "Sharp",
    "硬币或金属钝物": "Coin / blunt metal", "果核": "Fruit pit",
    "长条状异物": "Long object", "其他": "Other", "未归类": "Not classified",
    "食管": "Oesophagus", "胃": "Stomach", "十二指肠": "Duodenum",
    "小肠": "Small bowel", "结直肠": "Colorectal", "位置不明": "Not localised",
}
NODE = "#7A8C92"
INK = "#15232A"
MUTED = "#5A6B72"

# 异物可同时命中多类，桑基图的流必须互斥，故按临床风险优先级指派唯一主类。
PRIORITY = [("fb_magnet", "磁性异物"), ("fb_battery", "纽扣电池"),
            ("fb_sharp", "尖锐异物"), ("fb_mercury", "其他"),
            ("fb_coin", "硬币或金属钝物"), ("fb_round", "其他"),
            ("fb_pit", "果核"), ("fb_long", "长条状异物"), ("fb_plastic", "其他")]
COMPLICATIONS = ["out_obstruction", "out_peritonitis", "out_fistula",
                 "out_sepsis", "out_stricture"]


def prepare(df):
    def primary(row):
        for col, name in PRIORITY:
            if row.get(col, 0) == 1:
                return name
        return "未归类"

    df = df.copy()
    df["类型"] = df.apply(primary, axis=1)
    df["治疗"] = df["label_name"]
    df["结局"] = np.where(df["out_perforation"] == 1, "穿孔",
                          np.where(df[COMPLICATIONS].sum(axis=1) > 0,
                                   "其他并发症", "无并发症"))

    stages = ["类型"]
    annotation = "outputs/xray_annotation.csv"
    if os.path.exists(annotation):
        # 重标注回流后自动插入位置环
        ann = pd.read_csv(annotation)
        seg = {"esophagus": "食管", "stomach": "胃", "duodenum": "十二指肠",
               "small_bowel": "小肠", "colorectal": "结直肠"}
        ann["位置"] = ann["xray_segment"].map(seg).fillna("位置不明")
        df = df.merge(ann[["科研就诊编号", "位置"]], on="科研就诊编号", how="left")
        df["位置"] = df["位置"].fillna("位置不明")
        stages.append("位置")
        print("检测到 outputs/xray_annotation.csv，已插入「位置」环")
    stages += ["治疗", "结局"]
    return df, stages


def node_order(df, stages):
    """节点排序以减少交叉：类型按手术占比降序，其余用固定的临床顺序。"""
    order = {}
    surg_share = (df.groupby("类型")["治疗"].apply(lambda s: (s == "手术").mean()))
    order["类型"] = list(surg_share.sort_values(ascending=False).index)
    if "位置" in stages:
        order["位置"] = [s for s in ["食管", "胃", "十二指肠", "小肠", "结直肠", "位置不明"]
                         if s in set(df["位置"])]
    order["治疗"] = MGMT_ORDER
    order["结局"] = OUTCOME_ORDER
    return order


def ribbon(ax, x0, x1, y0a, y0b, y1a, y1b, color, alpha=0.55):
    """两节点之间的三次贝塞尔色带。"""
    xm = (x0 + x1) / 2
    verts = [(x0, y0a), (xm, y0a), (xm, y1a), (x1, y1a),
             (x1, y1b), (xm, y1b), (xm, y0b), (x0, y0b), (x0, y0a)]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=color, edgecolor="none",
                           alpha=alpha, zorder=1))


def build():
    os.makedirs("outputs/figures", exist_ok=True)
    df, stages = prepare(pd.read_csv("outputs/cohort.csv"))
    order = node_order(df, stages)
    total = len(df)

    gap = total * 0.022                       # 节点之间的留白，按总量比例
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(8.6, 5.0 if len(stages) == 3 else 6.0))
    ax.set_axis_off()

    xs = np.linspace(0.10, 0.90, len(stages))
    bar_w = 0.016

    # 各列节点的纵向位置
    pos = {}
    for stage, x in zip(stages, xs):
        counts = df[stage].value_counts().reindex(order[stage]).fillna(0)
        height = counts.sum() + gap * (len(counts) - 1)
        y = height
        for name, v in counts.items():
            if v == 0:
                continue
            pos[(stage, name)] = [y - v, y]          # [bottom, top]
            y -= v + gap
    span = max(t for _, t in pos.values())
    for k in pos:
        pos[k] = [v / span for v in pos[k]]

    # 色带：按治疗方式着色
    for i in range(len(stages) - 1):
        s0, s1 = stages[i], stages[i + 1]
        x0, x1 = xs[i] + bar_w / 2, xs[i + 1] - bar_w / 2
        # 「治疗」既是环节又是着色依据，分组键须去重
        keys = list(dict.fromkeys([s0, s1, "治疗"]))
        links = df.groupby(keys).size().reset_index(name="v").query("v > 0")
        off0 = {n: pos[(s0, n)][1] for n in order[s0] if (s0, n) in pos}
        off1 = {n: pos[(s1, n)][1] for n in order[s1] if (s1, n) in pos}
        links = links.sort_values([s0, s1], key=lambda c: c.map(
            {n: i for i, n in enumerate(order[c.name])}))
        for _, r in links.iterrows():
            v = r["v"] / span
            a, b = r[s0], r[s1]
            y0a, y0b = off0[a], off0[a] - v
            y1a, y1b = off1[b], off1[b] - v
            ribbon(ax, x0, x1, y0a, y0b, y1a, y1b, MGMT_COLORS[r["治疗"]])
            off0[a] -= v
            off1[b] -= v

    # 节点与标签
    for stage, x in zip(stages, xs):
        last = stage == stages[-1]
        for name in order[stage]:
            if (stage, name) not in pos:
                continue
            bot, top = pos[(stage, name)]
            colour = MGMT_COLORS.get(name, NODE)
            ax.add_patch(Rectangle((x - bar_w / 2, bot), bar_w, top - bot,
                                   facecolor=colour, edgecolor="none", zorder=3))
            n = int(round((top - bot) * span))
            label = f"{EN.get(name, name)}  {n}"
            ax.text(x - bar_w if not last else x + bar_w, (bot + top) / 2, label,
                    ha="right" if not last else "left", va="center",
                    fontsize=8.2, color=INK, zorder=4)

    titles = {"类型": "Object type", "位置": "Location", "治疗": "Management",
              "结局": "Outcome"}
    for stage, x in zip(stages, xs):
        ax.text(x, 1.045, titles[stage], ha="center", va="bottom",
                fontsize=9.4, color=INK, fontweight="bold")

    ax.set_xlim(-0.06, 1.06)
    ax.set_ylim(-0.045, 1.09)
    ax.text(0, -0.052,
            "Ribbons are coloured by management. Objects matching more than one "
            "category are assigned to the highest-risk one\n"
            "(magnetic > button battery > sharp > coin or blunt metal > fruit pit > "
            "long > other). Most perforations were present\n"
            "on admission and were therefore the indication for surgery rather than "
            "a consequence of it.",
            transform=ax.transAxes, fontsize=7.4, color=MUTED, va="top")

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"outputs/figures/fig3_sankey.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("已生成 outputs/figures/fig3_sankey.{pdf,png}")
    print(f"  环节：{' -> '.join(titles[s] for s in stages)}")
    print(f"\n类型 x 治疗：\n{pd.crosstab(df['类型'], df['治疗']).to_string()}")


if __name__ == "__main__":
    build()

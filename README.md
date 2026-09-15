# 儿童消化道异物「观察 / 内镜 / 手术」三分类决策模型

基于单中心 10 年（2016-07—2026-06）住院数据，建立并时间验证儿童消化道异物的
三分类治疗决策模型，并规划 SCI 论文产出。

## 队列

| | |
|---|---|
| 住院次数 / 唯一患儿 | 1238 / 1228 |
| 年龄 | 中位 3.2 岁（IQR 1.8–5.7） |
| 观察 / 内镜 / 手术 | 583 (47.1%) / 520 (42.0%) / 135 (10.9%) |
| 穿孔 | 78 (6.3%)，其中 44 例（56%）由磁性异物导致 |

## 预试验效能（5 折交叉验证）

| 模型 | 观察 AUC | 内镜 AUC | 手术 AUC | 宏平均 AUC |
|---|---|---|---|---|
| 多分类 Logistic | 0.719 | 0.728 | 0.908 | 0.785 |
| 随机森林 | 0.726 | 0.739 | 0.923 | 0.796 |

时间外部验证（2016–2023 → 2024–2026）：手术 AUC **0.945**，宏平均 AUC 0.773。

## 目录

```
docs/SCI论文写作方案.md    完整论文规划（选题、期刊、统计计划、图表、大纲、时间表）
scripts/build_cohort.py    队列与特征构建
scripts/pilot_model.py     预试验建模与验证
outputs/                   分析数据集与结果
```

## 复现

```bash
pip install pandas openpyxl scikit-learn
python3 scripts/build_cohort.py
python3 scripts/pilot_model.py
```

## 数据说明

原始数据 `10年消化道异物原始数据.xlsx` 含 20 个工作表的 EMR 抽取。
三个必须注意的特性详见 `docs/SCI论文写作方案.md` §一：

1. 内镜取异物记录在**手术/手麻系统**而非内镜报告表（该表仅 18 条）
2. CRP 为**左删失**数据，低于检测限的结果在定性列记为 `<0.78`
3. X 线报告的解剖定位文本质量差，557 例无法定位到具体节段；且首次片未必拍于决策之前

## 伦理

回顾性研究，数据已去标识化。发表前需确认补充材料不含原始自由文本。

## X 线重标注

当前最大的效能缺口是影像定位。表单与手册已就绪：

```bash
python3 scripts/build_worklist.py          # 生成工作清单
python3 scripts/build_annotation_form.py   # 生成 annotation/X线重标注表单.xlsx
# 阅片完成后
python3 scripts/ingest_annotation.py annotation/X线重标注表单.xlsx [第二位阅片者.xlsx]
```

判读标准见 `docs/X线重标注手册.md`。1073 例中 985 例可直接用于建模
（50 例首次片晚于手术开始，38 例与手术同日、时序不明）。

## Table 1

```bash
python3 scripts/build_table1.py
```

生成 `outputs/Table1.docx`（投稿用三线表，含 Table 1 基线特征与 Table 2 结局比较）、
`outputs/table1.{csv,md}` 与 `outputs/table2_outcomes.{csv,md}`。

连续变量报告中位数（IQR）与 Kruskal-Wallis 检验（效应量 epsilon²），分类变量报告
n(%) 与卡方检验（效应量 Cramér's V）；任一期望频数 <5 时改用蒙特卡洛置换检验。

## 异物类型人工核验

```bash
python3 scripts/build_fbtype_form.py     # 生成 annotation/异物类型核验表单.xlsx
python3 scripts/ingest_fbtype.py annotation/异物类型核验表单.xlsx [第二位核验者.xlsx]
```

411 例待核验（未归类 186 + 多类命中 25 + 抽检 200），双人子集 100 例。
回流同时给出正则 vs 人工准确率与人工 vs 人工 Kappa。

## 投稿初稿

```bash
python3 scripts/build_manuscript.py
```

由 `manuscript/draft_content.py` 生成 `manuscript/Manuscript_draft.{docx,md}`
与 `manuscript/TODO_checklist.md`。

**初稿不可直接投稿**：Results 与结论段为占位，参考文献表刻意留空。
改稿编辑 `draft_content.py` 后重跑，三份产物同步更新。

## 观察组安全性核查

```bash
python3 scripts/readmission_check.py
```

30 日再入院核查。观察组住院期间无穿孔、无新发并发症，但 **2/577（0.35%）
出院后 30 日内返院接受手术**——「0 例不良结局」的说法不成立。
射程限于本院异物相关住院，详见 `outputs/readmission_report.txt`。

## 正式分析

```bash
python3 scripts/test_metrics.py              # 指标实现的构造数据验证
python3 scripts/definitive_analysis.py       # 全量约 4 分钟
python3 scripts/definitive_analysis.py --quick   # 冒烟测试
```

MICE 多重插补（m=20，插补模型纳入结局）＋ 惩罚多分类回归（交叉验证选参）
＋ Bootstrap 乐观度校正（B=500）＋ 折内插补的交叉验证 ＋ 时间外部验证
＋ 逐类校准 ＋ 多分类 DCA ＋ PDI ＋ 线性 SHAP。

输出 `outputs/definitive_results.txt`、`outputs/model_coefficients.csv`、
`outputs/figures/{roc,calibration,decision_curve}.png`。

**内部效能以折内交叉验证为主报告值**，脚本会自动对照三种估计并提示。

## Fig 1 流程图

```bash
python3 scripts/build_figure1.py
```

输出 `outputs/figures/fig1_flow.{pdf,png}`。所有数字从 `outputs/cohort.csv`
实时读取，不硬编码——队列定义改动后重跑即同步，不会出现图与正文对不上。

## Fig 2 逐年构成比

```bash
python3 scripts/build_figure2.py
```

三种治疗方式的逐年构成比（100% 堆积柱）。手术置于底层——只有最底层基线固定、
厚度可直接读出，而手术占比是本文最关心也变化最剧烈的量（6.4%–32.0%）。
落点在治疗决策而非异物流行病学，与磁性异物论文无重叠。

## Fig 3 桑基图

```bash
python3 scripts/build_figure3.py
```

异物类型 → 治疗方式 → 结局。缎带按治疗方式着色，与 Fig 1/2、ROC、校准、DCA
共用同一套三色。类型节点按手术占比降序排列，以减少缎带交叉。

**为什么暂时只有三段。** 原规划的「消化道位置」一层需要每例的确切节段，但现有
X 线报告文本只能定位 193/1238（15.6%），画出来约 84% 会落在「无法定位」一个
巨节点上，主线反被掩盖。脚本已留好接口：`outputs/xray_annotation.csv` 一旦
回流，`prepare()` 自动插入该层，重跑即成四段图（figsize 与 y 轴留白也会跟着调整）。

**一个异物匹配多类时取风险最高的一类**（磁性 > 纽扣电池 > 尖锐 > 硬币或金属钝物
> 果核 > 长条 > 其他），避免同一例被重复计入。

穿孔多为入院时已存在（`入院病情` 字段），是手术指征而非手术后果，图注中已注明——
否则易被读成「手术导致穿孔」。

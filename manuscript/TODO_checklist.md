# 投稿前待办清单

由 `scripts/build_manuscript.py` 自动生成。共 31 处占位、10 处待补文献、13 处预试验数值。

## 一、正式分析完成后必须替换的占位

- [ ] 正式分析的判别效能——one-vs-rest AUC、宏平均、时间验证结果、校准斜率与截距
- [ ] 净获益与列线图的关键结果
- [ ] 依正式结果改写
- [ ] 医院名称与级别
- [ ] 检索策略——ICD 编码 T18.x 及/或诊断文本，需与病案室确认后写明
- [ ] 说明人工核验的例数与一致性——建议随机抽取 100 例由一位不参与建模的医师独立核对分类
- [ ] 影像定位重新标注完成后，补充节段定位、长径/短径与磁体数目的定义
- [ ] 人工核验的准确率与 Cohen's kappa——由异物类型核验表单的 C 抽检组与双人子集产出
- [ ] 填补诊断——插补前后分布比较图，置补充材料
- [ ] 按 Riley 等的最小样本量标准计算并写明结果
- [ ] 说明是 LASSO 还是 ridge，以及惩罚参数如何选择
- [ ] 分析软件与版本
- [ ] 批件号与批准日期
- [ ] 2020 年的解释——需核对该年是否因疫情期间就诊延迟、仅重症就医而改变了住院人群构成；n=50 是全期最小，比例波动本身也大，勿过度解读
- [ ] 调阅这两例病历，说明再入院时的异物位置与手术所见——surgery. Review of both records showed an object retained for weeks with a clear indication for intervention, and in both the index discharge followed a family decision rather than a clinical judgement that observation was appropriate. In one, a pebble measuring 19 x 11 mm had lodged at the ileocaecal region for 11 days with rectal bleeding, and was removed at laparotomy after laparoscopy and colonoscopy failed to retrieve it. In the other, two magnetic objects had been retained for a month and computed tomography showed them apposed across the gastric wall; the child returned with a gastrocolic fistula and gastric perforation requiring repair.
Obstruction, peritonitis or sepsis appeared among the discharge diagnoses of ten observation admissions, but in every instance the diagnosis was coded as present on admission rather than arising during the admission, and several were unrelated to the ingested object (appendicitis with abscess, faecal impaction, colitis). No new-onset complication was recorded in the observation group.
This cohort contains only admissions for foreign body ingestion at this institution, so the readmission analysis cannot detect children who presented elsewhere, were admitted under a different diagnosis, or were managed in outpatient follow-up. The figures above should be read as institution-level foreign-body readmission, not as an absence of delayed intervention.
【TODO: 全部效能结果。当前预试验值（5 折交叉验证、中位数填补、未做重标注）为：多分类 Logistic 宏平均 AUC 0.788（观察 0.725、内镜 0.735、手术 0.904）；随机森林宏平均 0.796；时间验证手术 AUC 0.945、宏平均 0.773。这些数字仅供占位，正式分析后整段重写
- [ ] 校准结果——逐类校准斜率与截距、校准曲线（Fig 4）
- [ ] 决策曲线分析结果——各类别在临床相关阈值区间的净获益（Fig 5）
- [ ] 依正式模型改写
- [ ] 依正式结果填表并改写
- [ ] 首段依正式结果改写
- [ ] 重标注完成后，补充磁体数目与「单枚磁体合并其他金属」的分析——后者风险等同多枚磁体，易被漏判
- [ ] 与指南的关系及临床落地——依正式结果与列线图/在线计算器的最终形式撰写。要点：本模型不取代规则式指南，而是为指南未覆盖的灰区提供概率化补充；说明拟以何种形式在急诊分诊中使用
- [ ] 引用核验所得准确率与 kappa
- [ ] 若最终仍存在其他局限，一并补入
- [ ] Conclusion 段——依正式结果撰写。两句：模型可用于急诊分诊，尤其能高特异度地前置识别需手术者；决策灰区集中于观察与内镜之间，该区间最需要共识与决策支持
- [ ] 批件号
- [ ] 基金资助或声明无资助
- [ ] 各作者利益冲突声明
- [ ] 按 CRediT 分类逐人填写
- [ ] 与磁性异物论文的措辞保持一致
- [ ] 仓库地址

## 二、需要补入的真实文献

**不要编造文献。** 每条标注了需要哪一类，请检索后填入真实引用。

- [ ] `[REF-1]` 现行儿童消化道异物处理指南，如 ESPGHAN/NASPGHAN 或 ASGE
- [ ] `[REF-2]` 儿童消化道异物流行病学综述
- [ ] `[REF-3]` 既有二分类预测研究
- [ ] `[REF-4]` 同上
- [ ] `[REF-5]` TRIPOD+AI 2024 声明
- [ ] `[REF-6]` STROBE 声明
- [ ] `[REF-7]` Riley 等预测模型最小样本量方法学文献
- [ ] `[REF-8]` Bootstrap 乐观度校正方法学文献
- [ ] `[REF-9]` 决策曲线分析方法学文献
- [ ] `[REF-10]` 作者本人的磁性异物论文，见刊后补入完整引用；投稿时若仍在审，按期刊要求随稿提供

## 三、来自预试验、须以正式分析结果更新的数值

这些值来自 5 折交叉验证 + 中位数填补，**未**做影像重标注、
**未**做多重插补与 Bootstrap 校正，不能作为最终结果发表。

- [ ] Penalised multinomial logistic regression was fitted with multiple imputation, internally validated by bootstrap optimism correction, and temporally validated on admissions from 2024 onwards.
- [ ] 49 first films were obtained after the procedure had begun and 37 shared its date with no time recorded
- [ ] 981
- [ ] 85.0%
- [ ] 55.2%
- [ ] 0.602
- [ ] 20
- [ ] 68.7%
- [ ] 500
- [ ] 62.9%
- [ ] +0.108 macro-averaged AUC
- [ ] 0.010
- [ ] from a macro-averaged AUC of 0.788 to 0.794, and for the observation class from 0.725 to 0.735

## 四、投稿前的格式核对

- [ ] 核实 J Pediatr Surg 现行 author guidelines：字数上限、结构式摘要格式与词数、图表数量、参考文献格式、预印本政策
- [ ] TRIPOD+AI 清单逐条填写，作为补充材料
- [ ] 与磁性异物论文逐项核对数字口径（队列定义、磁体例数、穿孔数、伦理批件号）
- [ ] 按方案 §七 排查 Fig 2 与 Table 4 是否与磁性异物论文重复
- [ ] 投稿信中主动披露同队列的在审稿件
- [ ] 确认补充材料不含任何原始自由文本

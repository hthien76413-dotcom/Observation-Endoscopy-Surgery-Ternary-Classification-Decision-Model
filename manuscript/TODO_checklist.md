# 投稿前待办清单

由 `scripts/build_manuscript.py` 自动生成。共 30 处占位、11 处待补文献、13 处预试验数值。

## 一、正式分析完成后必须替换的占位

- [ ] 正式分析的判别效能——one-vs-rest AUC、宏平均、时间验证结果、校准斜率与截距
- [ ] 净获益与列线图的关键结果
- [ ] 依正式结果改写
- [ ] 医院名称与级别
- [ ] 检索策略——ICD 编码 T18.x 及/或诊断文本，需与病案室确认后写明
- [ ] 说明人工核验的例数与一致性——建议随机抽取 100 例由一位不参与建模的医师独立核对分类
- [ ] 影像定位重新标注完成后，补充节段定位、长径/短径与磁体数目的定义
- [ ] 人工核验的准确率与 Cohen's kappa——由异物类型核验表单的 C 抽检组与双人子集产出
- [ ] 学习曲线敏感性分析，依 outputs/learning_curve.txt 改写为正式段落。要点（措辞须谨慎，不可越过观测范围外推）：固定测试集（n=248）+ 训练池分层子抽样（n=99→990）显示观察/内镜的判别力尾段斜率仅为头段的 0.10–0.12（手术类作对照为 0.17，走平更早符合预期），即在当前训练池规模内已大体走平而非仍在陡峭爬升。这一观察与「样本不足」这一替代解释方向相反，为「观察/内镜边界不清是决策本身的性质」提供了一条独立于上文 Riley 核算的旁证。但**必须与上一段的样本量短缺并置陈述，不可单独使用去掩盖它**：曲线只覆盖到 n=990，走平也可能只是「当前规模内爬得慢」，不等同于「给再多同类数据也不会再涨」——没有做任何超出观测范围的外推，写作时须保留「in the available sample」一类限定语
- [ ] 批件号与批准日期
- [ ] 逐一核对后确认「两文不共用任何图表与结果」这一句成立——Fig 2 与 Table 4 是风险点。该文已定稿投出，图表清单固定，现在即可核；核完前不要把这句当已证实的事实投出去
- [ ] 2020 年的解释——需核对该年是否因疫情期间就诊延迟、仅重症就医而改变了住院人群构成；n=50 是全期最小，比例波动本身也大，勿过度解读
- [ ] 调阅这两例病历，说明再入院时的异物位置与手术所见——surgery. Review of both records showed an object retained for weeks with a clear indication for intervention, and in both the index discharge followed a family decision rather than a clinical judgement that observation was appropriate. In one, a pebble measuring 19 x 11 mm had lodged at the ileocaecal region for 11 days with rectal bleeding, and was removed at laparotomy after laparoscopy and colonoscopy failed to retrieve it. In the other, two magnetic objects had been retained for a month and computed tomography showed them apposed across the gastric wall; the child returned with a gastrocolic fistula and gastric perforation requiring repair.
Obstruction, peritonitis or sepsis appeared among the discharge diagnoses of ten observation admissions, but in every instance the diagnosis was coded as present on admission rather than arising during the admission, and several were unrelated to the ingested object (appendicitis with abscess, faecal impaction, colitis). No new-onset complication was recorded in the observation group.
This cohort contains only admissions for foreign body ingestion at this institution, so the readmission analysis cannot detect children who presented elsewhere, were admitted under a different diagnosis, or were managed in outpatient follow-up. The figures above should be read as institution-level foreign-body readmission, not as an absence of delayed intervention.
【TODO: 全部效能结果。当前预试验值（5 折交叉验证、中位数填补、未做重标注）为：多分类 Logistic 宏平均 AUC 0.788（观察 0.725、内镜 0.735、手术 0.904）；随机森林宏平均 0.796；时间验证手术 AUC 0.945、宏平均 0.773。这些数字仅供占位，正式分析后整段重写。改写时须引 Fig 4，并以折内交叉验证值为内部效能的主报告值——表观 0.832 与 Bootstrap 校正 0.814 均偏乐观，不可单报
- [ ] 校准结果——逐类校准斜率与截距、校准曲线（Fig 5A）。要点已明确：交叉验证校准良好（斜率 0.95/0.98/1.13，截距均近 0），时间验证截距明显漂移（观察 +0.43、内镜 −0.28、手术 −0.55），方向与构成比变化一致。须写明「判别力经受住时间验证、校准没有」，并给出重估截距的建议——否则读者会默认时间验证通过即可直接部署
- [ ] 决策曲线分析结果——各类别在临床相关阈值区间的净获益（Fig 5B）。模型优于两条参照线的区间：观察 0.15–0.71、内镜 0.07–0.79、手术 0.02–0.78。低于该区间时 treat-all 更优，这是阈值低于患病率时的常态，须一并说明，不要只报优势区间
- [ ] 依正式模型改写
- [ ] 依正式结果填表并改写
- [ ] 首段依正式结果改写
- [ ] 补一句引学习曲线（§2.5 末段 / outputs/learning_curve.txt）——观察/内镜的判别力在现有训练池规模内已大体走平（尾/头斜率比 0.10–0.12），为此处论点提供旁证；但同段须同时提醒读者这与样本量核算（§2.5，该对比较仍需 2095 例）并非互相矛盾而是同一枚硬币的两面，不要写成学习曲线已经「证明」了这一论点
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
- [ ] `[REF-8]` Pate/Riley 多分类最小样本量文献
- [ ] `[REF-9]` 决策曲线分析方法学文献
- [ ] `[REF-10]` 作者本人的磁性异物论文，已投 JPGN 在审。须向用户索取题目、作者序与投稿日期；见刊或挂出 medRxiv 预印本后补入完整引用，在此之前按 「under review」 处理

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

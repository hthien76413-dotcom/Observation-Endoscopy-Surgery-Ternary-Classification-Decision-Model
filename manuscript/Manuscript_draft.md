# Ternary decision model for observation, endoscopy, or surgery in children with gastrointestinal foreign body ingestion: development and temporal validation in 1238 admissions

*Running head: A three-class decision model for paediatric GI foreign bodies*

> **这是初稿，不可直接投稿。**
> 正文含 30 处 `【TODO】` 占位、11 处 `[REF-n]` 待补文献。
> `《数字》` 标记的值来自预试验（5 折交叉验证、中位数填补、未做影像重标注），
> 正式分析后必须更新。清单见 `TODO_checklist.md`。

## Abstract

**Background/Purpose.** Most ingested foreign bodies in children pass spontaneously, yet a substantial minority require endoscopic retrieval and a small minority require surgery. Current guidance is rule-based and addresses high-risk objects explicitly, but offers little quantitative support for the largest group — the asymptomatic child with a blunt object beyond the oesophagus. Existing prediction studies are binary and modest in size, and observation is rarely modelled as an active, predictable decision. We aimed to develop and temporally validate a model that predicts which of three management pathways a child will require.

**Methods.** Single-centre retrospective cohort of 1238 admissions in 1228 children (July 2016 to June 2026). The outcome was the management actually delivered: observation, endoscopic retrieval, or surgery. Candidate predictors were restricted to information available before the treatment decision, verified against operating-theatre timestamps. 《Penalised multinomial logistic regression was fitted with multiple imputation, internally validated by bootstrap optimism correction, and temporally validated on admissions from 2024 onwards.》 Discrimination, calibration, and net benefit were assessed.

**Results.** Management was observation in 583 (47.1%), endoscopy in 520 (42.0%), and surgery in 135 (10.9%). 【TODO: 正式分析的判别效能——one-vs-rest AUC、宏平均、时间验证结果、校准斜率与截距】 Perforation occurred in 78 admissions (6.3%), none during an admission managed by observation; two observed children (0.35%) were readmitted within 30 days and underwent surgery. 【TODO: 净获益与列线图的关键结果】

**Conclusions.** 【TODO: 依正式结果改写】 The need for surgery was predictable with high discrimination, whereas the boundary between observation and endoscopy was considerably less separable — a finding we interpret as reflecting genuine practice variation rather than model failure, and therefore as identifying the region where decision support is most needed.

**Keywords:** Foreign body ingestion; Child; Gastrointestinal endoscopy; Clinical decision rules; Prediction model; Magnet ingestion

---

## 1. Introduction

Foreign body ingestion is among the commonest presentations in paediatric emergency and surgical practice. The great majority of ingested objects traverse the gastrointestinal tract without intervention, and management guidance therefore centres on identifying the minority that will not [REF-1: 现行儿童消化道异物处理指南，如 ESPGHAN/NASPGHAN 或 ASGE][REF-2: 儿童消化道异物流行病学综述]. That guidance is explicitly rule-based: an oesophageal button battery demands immediate removal, multiple magnets demand intervention, and a sharp object in the oesophagus should not be left in place.

These rules are well founded for the objects they name, but they leave the largest group unaddressed. The asymptomatic child with a blunt, radiopaque object already in the stomach falls outside every categorical indication, and management in this group varies — between institutions, between clinicians, and with the anxiety of the accompanying family. Prediction work in this setting has been limited: published models are almost uniformly binary, asking whether endoscopy will be performed or whether it will succeed, and are typically derived from a few hundred children [REF-3: 既有二分类预测研究][REF-4: 同上]. Observation is treated as the residual category — what happens when nothing is done — rather than as an active decision that might itself be predicted.

We therefore set out to model management as a three-way choice. Using a decade of consecutive admissions at a tertiary paediatric centre, we developed and temporally validated a model predicting whether a child would be managed by observation, endoscopic retrieval, or surgery, using only information available at the point of decision.

## 2. Methods

### 2.1. Study design and participants

We conducted a retrospective cohort study at 【TODO: 医院名称与级别】, a tertiary paediatric centre. All admissions for gastrointestinal foreign body ingestion between 3 July 2016 and 30 June 2026 were identified from the hospital's electronic medical record. 【TODO: 检索策略——ICD 编码 T18.x 及/或诊断文本，需与病案室确认后写明】

The analysis unit was the admission. Six admissions were excluded because the only recorded procedure was unrelated to foreign body ingestion, leaving 1238 admissions in 1228 children; ten children contributed two admissions each. Reporting follows TRIPOD+AI [REF-5: TRIPOD+AI 2024 声明] for the prediction model and STROBE [REF-6: STROBE 声明] for the cohort description.

### 2.2. Outcome

The outcome was the management actually delivered during the admission, in three mutually exclusive classes: observation, endoscopic retrieval, or surgery. Admissions in which both endoscopy and surgery were performed were classified as surgery.

Classification required care specific to this institution. Paediatric endoscopic retrieval here is performed under general anaesthesia in the operating theatre, so it is documented in the operative and anaesthetic records rather than in the endoscopy reporting system; that system contained only 18 records against 520 endoscopic retrievals. Outcome class was therefore derived from procedure names in the operative and anaesthetic records. 【TODO: 说明人工核验的例数与一致性——建议随机抽取 100 例由一位不参与建模的医师独立核对分类】

One further distinction is necessary. Ten admissions carry the coded discharge diagnosis "procedure not performed for reasons attributable to the family", and all ten fall into the observation class. In these children observation was not the clinician's judgement but the outcome of a declined intervention, so the label carries a different meaning; they were flagged and excluded in a prespecified sensitivity analysis. We did not attempt to identify further such admissions from free text: phrases such as "the family requested discharge" appear in 359 records including 137 after endoscopy and 22 after surgery, and are routine discharge wording rather than a marker of refusal.

Complications were extracted from coded discharge diagnoses and were used to describe the cohort and to examine the clinical coherence of the outcome classes; they were not used as predictors.

### 2.3. Predictors

Candidate predictors were restricted to information available before the treatment decision. Intraoperative findings, discharge diagnoses, length of stay and complications were excluded from the predictor set by design.

This restriction was enforced rather than assumed. For every radiograph and laboratory result we compared its timestamp against the start of the procedure, taken from the anaesthetic record, which is recorded to the minute; the operative note stores a date only and cannot support such a comparison. Investigations obtained after the procedure began were treated as unavailable. Radiographs were ordered by acquisition time rather than report time, since the decision rests on when the image was taken. Of 1073 admissions with any radiograph, 《49 first films were obtained after the procedure had begun and 37 shared its date with no time recorded》, leaving 《981》 admissions with imaging usable as a predictor.

Predictors comprised demographic variables (age, sex, weight); interval from ingestion to presentation, parsed from the chief complaint; object type; symptoms and signs; radiographic findings; and laboratory results. 【TODO: 影像定位重新标注完成后，补充节段定位、长径/短径与磁体数目的定义】

Object type, symptoms and signs were extracted from free text with clause-level negation scoping, because the examination template documents every sign whether present or absent — a record reading "tenderness negative, rebound negative" contains both terms. Abdominal signs were taken only from the specialist abdominal examination field, as the general examination documents tenderness of the mastoid, sinuses and thyroid. 【TODO: 人工核验的准确率与 Cohen's kappa——由异物类型核验表单的 C 抽检组与双人子集产出】 The extraction dictionary and rules are provided in Supplementary Material.

### 2.4. Missing data

Missingness in this cohort is informative and must be handled as such. C-reactive protein was absent in 《85.0%》 of the endoscopy group against 《55.2%》 of the observation group, reflecting that children taken promptly to theatre for retrieval do not undergo a full laboratory workup. Indicators of which tests were ordered — carrying no measured value — predicted management with a macro-averaged AUC of 《0.602》, confirming that the pattern of missingness encodes clinician behaviour rather than physiology.

Accordingly, missing values were handled by multiple imputation by chained equations with 《20》 imputations, with the outcome included in the imputation model; single-value imputation was not used, and missingness indicators were not offered as predictors. C-reactive protein was excluded from the predictor set: it contributed negligibly while carrying 《68.7%》 non-random missingness. Complete-case analysis is reported only as a sensitivity analysis.

Draws were constrained to the observed range of each variable. Without that constraint the posterior draws are unbounded and a small number of impossible values appear — negative weights and leucocyte counts, neutrophil percentages outside 0 to 100 — amounting to 20 of 11 220 imputed values before the constraint was applied. Observed and imputed distributions are compared in Supplementary Figure S1. They are not expected to coincide: the missingness is informative, so a perfect overlap would indicate that the imputation model had ignored the outcome and the remaining covariates rather than that it had performed well.

### 2.5. Sample size

The cohort comprises every eligible admission over ten years, so the sample size was fixed by the study period rather than chosen. We therefore report the sample size criteria of Riley and colleagues as an audit of what the available data support, not as an a priori calculation [REF-7: Riley 等预测模型最小样本量方法学文献]. For a multinomial model the criteria were applied to each pairwise comparison in turn and the most demanding taken [REF-8: Pate/Riley 多分类最小样本量文献]. The anticipated Cox–Snell R² was taken from the cross-validated predictions rather than the apparent ones, since using an optimistic R² would understate the sample size required.

With 32 predictor parameters, none of the three comparisons is fully supported. Expressed as whole-cohort equivalents, observation versus surgery requires 1 417 admissions and endoscopy versus surgery 1 471, against the 1 238 available; for both, the binding criterion is that apparent and adjusted Nagelkerke R² differ by no more than 0.05. The observation versus endoscopy comparison requires 2 095, and there the binding criterion is expected shrinkage of no more than 10%.

This shortfall is a property of the clinical problem rather than an oversight, and it runs in the same direction as our central finding. The requirement rises as the outcome becomes harder to predict, and the observation–endoscopy distinction is precisely the one the data separate least well. It is why the model is penalised, why we report fold-internal cross-validation rather than apparent performance, and why we do not propose the observation–endoscopy probabilities as a decision rule. We state it here rather than in the limitations alone, because it bears on how the model should be read throughout.

【TODO: 学习曲线敏感性分析，依 outputs/learning_curve.txt 改写为正式段落。要点（措辞须谨慎，不可越过观测范围外推）：固定测试集（n=248）+ 训练池分层子抽样（n=99→990）显示观察/内镜的判别力尾段斜率仅为头段的 0.10–0.12（手术类作对照为 0.17，走平更早符合预期），即在当前训练池规模内已大体走平而非仍在陡峭爬升。这一观察与「样本不足」这一替代解释方向相反，为「观察/内镜边界不清是决策本身的性质」提供了一条独立于上文 Riley 核算的旁证。但**必须与上一段的样本量短缺并置陈述，不可单独使用去掩盖它**：曲线只覆盖到 n=990，走平也可能只是「当前规模内爬得慢」，不等同于「给再多同类数据也不会再涨」——没有做任何超出观测范围的外推，写作时须保留「in the available sample」一类限定语】

### 2.6. Statistical analysis

The primary model was a penalised multinomial logistic regression with observation as the reference class. The penalty type (L1 or L2) and its strength were selected together by five-fold cross-validation over a grid, minimising multiclass log-loss; an L1 (lasso) penalty was selected, at the inverse-strength value C = 0.1. Selection was performed once on a median-filled copy of the data and the chosen penalty then held fixed across the imputed datasets; this keeps the computation tractable but means the optimism correction is slightly anticonservative, as noted below. Random forest and gradient boosting models were fitted for comparison, to establish whether a more flexible algorithm offered material benefit over an interpretable one.

Internal validation used bootstrap optimism correction with 《500》 resamples, chosen over sample splitting because the available sample does not support discarding data [REF-8: Bootstrap 乐观度校正方法学文献]. Temporal validation used admissions from 2016 to 2023 for development and those from 2024 onwards for validation, giving an independent period rather than a random partition.

Discrimination was summarised by one-versus-rest AUC for each class, macro- and micro-averaged AUC, and the polytomous discrimination index. Calibration was assessed by class-specific calibration curves with slope and intercept. Overall performance used the multiclass Brier score. Clinical utility was assessed by decision curve analysis reporting net benefit per class [REF-9: 决策曲线分析方法学文献]. Variable contributions were summarised with SHAP values; because the model is linear on the log-odds scale these were computed exactly rather than approximated.

Analyses used Python 3.11.15 with scikit-learn 1.9.1, pandas 3.0.5, NumPy 2.4.6, SciPy 1.17.1 and Matplotlib 3.11.2. Multiple imputation used scikit-learn's IterativeImputer, which remains an experimental module in that library. Multiclass discrimination, calibration and net-benefit measures have no established implementation and were written for this study; they are verified against constructed data in the accompanying code.

Prespecified sensitivity analyses addressed: restriction to first admissions; exclusion of all laboratory predictors; restriction to admissions with pre-decision imaging; restriction to admissions with pre-decision laboratory results; complete-case analysis; retention of C-reactive protein; and exclusion of admissions in which a planned procedure was not performed because the family declined it. For each, the class composition of the retained subset was compared with the full cohort, so that a difference in discrimination arising from selection would not be mistaken for a difference in model performance.

### 2.7. Ethics

The study was approved by the institutional ethics committee (【TODO: 批件号与批准日期】) with waiver of informed consent for this retrospective analysis of de-identified records.

### 2.8. Relation to a companion report

This cohort has been partly described in a separate report on the epidemiology of magnetic foreign body ingestion, by the same authors and currently under review [REF-10: 作者本人的磁性异物论文，已投 JPGN 在审。须向用户索取题目、作者序与投稿日期；见刊或挂出 medRxiv 预印本后补入完整引用，在此之前按 「under review」 处理]. The present study addresses a different question, with a different outcome variable and a different analytical approach: that report describes what children swallow and how often magnets perforate, whereas this one predicts which of three management decisions a child will receive. 【TODO: 逐一核对后确认「两文不共用任何图表与结果」这一句成立——Fig 2 与 Table 4 是风险点。该文已定稿投出，图表清单固定，现在即可核；核完前不要把这句当已证实的事实投出去】

## 3. Results

### 3.1. Cohort

Between July 2016 and June 2026, 1238 admissions in 1228 children met the inclusion criteria. Median age was 3.2 years (IQR 1.8–5.8) and 《62.9%》 were boys. Management was observation in 583 admissions (47.1%), endoscopic retrieval in 520 (42.0%), and surgery in 135 (10.9%). Median length of stay was 2 days overall and 9 days in the surgical group. Baseline characteristics by management group are shown in Table 1.

The mix of management delivered shifted over the decade (Fig 2). Observation rose from 43.8% of admissions in 2016 to 59.8% in the first half of 2026, while endoscopic retrieval fell from 47.9% to 31.5%. Surgery remained a small minority throughout except in 2020, when it accounted for 32.0% of 50 admissions. 【TODO: 2020 年的解释——需核对该年是否因疫情期间就诊延迟、仅重症就医而改变了住院人群构成；n=50 是全期最小，比例波动本身也大，勿过度解读】

Perforation was recorded in 78 admissions (6.3%), obstruction in 40 (3.2%) and peritonitis in 33 (2.7%). Of the 78 perforations, 76 were managed surgically and two endoscopically; none occurred during an admission managed by observation.

Because an outcome defined by delivered management could conceal deferred rather than avoided intervention, we examined readmissions. Among 577 observation admissions with a recorded discharge date, two children (0.35%) were readmitted within 30 days and underwent surgery, at 2 and 5 days after discharge; readmission within 30 days occurred in 5 of 520 admissions (0.96%) after endoscopy and 2 of 135 (1.48%) after surgery. 【TODO: 调阅这两例病历，说明再入院时的异物位置与手术所见——surgery. Review of both records showed an object retained for weeks with a clear indication for intervention, and in both the index discharge followed a family decision rather than a clinical judgement that observation was appropriate. In one, a pebble measuring 19 x 11 mm had lodged at the ileocaecal region for 11 days with rectal bleeding, and was removed at laparotomy after laparoscopy and colonoscopy failed to retrieve it. In the other, two magnetic objects had been retained for a month and computed tomography showed them apposed across the gastric wall; the child returned with a gastrocolic fistula and gastric perforation requiring repair.

Obstruction, peritonitis or sepsis appeared among the discharge diagnoses of ten observation admissions, but in every instance the diagnosis was coded as present on admission rather than arising during the admission, and several were unrelated to the ingested object (appendicitis with abscess, faecal impaction, colitis). No new-onset complication was recorded in the observation group.

This cohort contains only admissions for foreign body ingestion at this institution, so the readmission analysis cannot detect children who presented elsewhere, were admitted under a different diagnosis, or were managed in outpatient follow-up. The figures above should be read as institution-level foreign-body readmission, not as an absence of delayed intervention.

### 3.2. Model performance

【TODO: 全部效能结果。当前预试验值（5 折交叉验证、中位数填补、未做重标注）为：多分类 Logistic 宏平均 AUC 0.788（观察 0.725、内镜 0.735、手术 0.904）；随机森林宏平均 0.796；时间验证手术 AUC 0.945、宏平均 0.773。这些数字仅供占位，正式分析后整段重写。改写时须引 Fig 4，并以折内交叉验证值为内部效能的主报告值——表观 0.832 与 Bootstrap 校正 0.814 均偏乐观，不可单报】

【TODO: 校准结果——逐类校准斜率与截距、校准曲线（Fig 5A）。要点已明确：交叉验证校准良好（斜率 0.95/0.98/1.13，截距均近 0），时间验证截距明显漂移（观察 +0.43、内镜 −0.28、手术 −0.55），方向与构成比变化一致。须写明「判别力经受住时间验证、校准没有」，并给出重估截距的建议——否则读者会默认时间验证通过即可直接部署】

【TODO: 决策曲线分析结果——各类别在临床相关阈值区间的净获益（Fig 5B）。模型优于两条参照线的区间：观察 0.15–0.71、内镜 0.07–0.79、手术 0.02–0.78。低于该区间时 treat-all 更优，这是阈值低于患病率时的常态，须一并说明，不要只报优势区间】

### 3.3. Variable importance

【TODO: 依正式模型改写】 In the pilot analysis the interval from ingestion to presentation, object type and abdominal tenderness carried the greatest weight. Object type contributed the largest single increment to discrimination 《+0.108 macro-averaged AUC》, exceeding the contribution of imaging and laboratory variables combined — indicating that the quality of the ingestion history matters more to the decision than the number of investigations performed.

### 3.4. Sensitivity analyses

【TODO: 依正式结果填表并改写】 In the pilot analysis, macro-averaged AUC differed from the primary model by no more than 《0.010》 across all prespecified sensitivity analyses, and no retained subset differed materially from the full cohort in class composition.

## 4. Discussion

【TODO: 首段依正式结果改写】 In a decade of consecutive admissions for paediatric gastrointestinal foreign body ingestion, management fell into three groups of markedly unequal size and predictability. The need for surgery was identified with high discrimination. The boundary between observation and endoscopic retrieval was considerably less separable.

We do not regard that asymmetry as a deficiency of the model. Whether a child requires an operation is determined by objective pathology — perforation, obstruction, or bowel trapped between magnets — and such states leave clear traces in the history, the examination and the film. Whether a blunt object sitting in the stomach of an asymptomatic child is retrieved endoscopically or watched is a different kind of question. It is not fully determined by the child's physiology, and it is influenced by institutional habit, theatre availability, and the distress of the family. A model trained on what clinicians did will reproduce that variability, and its inability to separate the two groups cleanly is a measurement of the variability rather than a failure to detect a signal. On this reading, the region where the model discriminates least is precisely the region where consensus and decision support are most needed. 【TODO: 补一句引学习曲线（§2.5 末段 / outputs/learning_curve.txt）——观察/内镜的判别力在现有训练池规模内已大体走平（尾/头斜率比 0.10–0.12），为此处论点提供旁证；但同段须同时提醒读者这与样本量核算（§2.5，该对比较仍需 2095 例）并非互相矛盾而是同一枚硬币的两面，不要写成学习曲线已经「证明」了这一论点】

Magnetic objects were the leading driver of operative management in this cohort. Their epidemiology over the study period, including the rise in incidence and the associated perforation burden, is reported separately [REF-10]; here they are relevant as the single object type most strongly associated with surgery. 【TODO: 重标注完成后，补充磁体数目与「单枚磁体合并其他金属」的分析——后者风险等同多枚磁体，易被漏判】

【TODO: 与指南的关系及临床落地——依正式结果与列线图/在线计算器的最终形式撰写。要点：本模型不取代规则式指南，而是为指南未覆盖的灰区提供概率化补充；说明拟以何种形式在急诊分诊中使用】

Several features strengthen these findings. The cohort spans a decade of consecutive admissions at a single centre, with no change in the ascertainment method over that period. Predictors were restricted to the pre-decision window by timestamp comparison rather than by assumption, and the effect of that restriction is quantified. Validation was temporal rather than random, testing the model against a period the development data did not contain. The coherence between outcome class and subsequent course — no perforation and no new-onset complication among observed children, with surgery after readmission in 0.35% — supports the clinical validity of the outcome definition, while quantifying rather than assuming the safety of observation.

That both readmitted children had declined intervention at the index admission points to a broader caveat about the outcome label. The observation class contains two distinct situations — observation chosen because it was judged appropriate, and observation arrived at because an offered intervention was refused — and only the first is the decision a model should learn. Excluding the ten admissions where refusal is explicitly coded improved discrimination 《from a macro-averaged AUC of 0.788 to 0.794, and for the observation class from 0.725 to 0.735》, consistent with those labels behaving as noise. Refusal is unlikely to be coded in every instance, so some residual contamination of the observation class should be assumed.

This study has important limitations. First, and most fundamentally, the outcome is the management that was delivered, not the management that was optimal. The model therefore predicts current best practice at this institution and is best understood as a tool for triage and resource anticipation rather than as a causal statement about which treatment a child ought to receive. Observation was safe in the great majority — no perforation, no new-onset complication, and surgery after readmission in 0.35% — but this does not establish that every endoscopy performed was necessary, and the two children who returned for surgery show that the observation label is not uniformly correct — both of them had declined an offered intervention rather than been judged suitable for observation. Prospective evaluation would be required to address that question. Readmission ascertainment is moreover limited to this institution and to foreign-body admissions, so delayed intervention elsewhere would not be detected. Second, the study is single-centre, and although temporal validation demonstrates stability across periods, geographical external validation is absent. Third, object type and clinical features were extracted from free text; 【TODO: 引用核验所得准确率与 kappa】 residual misclassification is possible, particularly for objects the record describes only as "a foreign body". Fourth, imaging was not available before the decision in every admission, and the corresponding sensitivity analysis addresses but does not eliminate this. 【TODO: 若最终仍存在其他局限，一并补入】

【TODO: Conclusion 段——依正式结果撰写。两句：模型可用于急诊分诊，尤其能高特异度地前置识别需手术者；决策灰区集中于观察与内镜之间，该区间最需要共识与决策支持】

---

## Declarations

**Ethics approval.** 【TODO: 批件号】 Waiver of informed consent was granted.

**Funding.** 【TODO: 基金资助或声明无资助】

**Conflicts of interest.** 【TODO: 各作者利益冲突声明】

**Author contributions.** 【TODO: 按 CRediT 分类逐人填写】

**Data availability.** 【TODO: 与磁性异物论文的措辞保持一致】 Individual patient data cannot be shared publicly owing to privacy restrictions; the analysis code and extraction dictionaries are available at 【TODO: 仓库地址】.

## Tables

- Table 1. Baseline characteristics by management group. (已生成：outputs/Table1.docx)
- Table 2. Multinomial regression coefficients, observation as reference. 【TODO】
- Table 3. Model performance, internal and temporal validation. 【TODO】
- Table 4. Object type by management group and perforation rate. (已生成：outputs/table2_outcomes.docx 的对应部分，需按 §七「重复图表风险」重构)

## Figures

- Fig 1. Study flow diagram (TRIPOD/STROBE format). (已生成：outputs/figures/fig1_flow.pdf，矢量)
- Fig 2. Management delivered by year of admission, as a proportion of admissions. (已生成：outputs/figures/fig2_trend.pdf，矢量)
- Fig 3. Sankey diagram of the care pathway: object type to management to outcome. Ribbons are coloured by management. Objects matching more than one category are assigned to the highest-risk one (magnetic > button battery > sharp > coin or blunt metal > fruit pit > long > other). Most perforations were present on admission and were therefore the indication for surgery rather than a consequence of it. (已生成：outputs/figures/fig3_sankey.pdf，矢量。X 线重标注回流后脚本会自动插入「消化道位置」一层，届时重跑即成四段图)
- Fig 4. Receiver operating characteristic curves, one-versus-rest. (A) Internal validation by 5-fold cross-validation with imputation performed separately within each fold (N = 1238). (B) Temporal validation: the model fitted on 2016–2023 admissions applied unchanged to admissions after 2023 (N = 413). Areas under the curve are shown with 95% bootstrap confidence intervals from 2000 resamples of cases; class sizes are in parentheses. Apparent (in-sample) curves are not shown because they overstate discrimination by about 0.03 macro AUC. (已生成：outputs/figures/fig4_roc.pdf，矢量)
- Fig 5. (A) Class-specific calibration and (B) decision curve analysis. (A) Calibration slope / intercept are given above each panel for the cross-validated (CV) and temporal (Temp) predictions; the shaded strip shows the distribution of predicted probabilities. Discrimination survives temporal validation but calibration does not: the intercepts move with the case mix (observation 47.1 → 55.9%, endoscopy 42.0 → 36.3%, surgery 10.9 → 7.7%), so the intercepts would require re-estimation before use in a later period. (B) Net benefit from the cross-validated predictions; shading marks the threshold range over which the model exceeds both default strategies. (已生成：outputs/figures/fig5_calibration_dca.pdf，矢量)
- Fig 6. SHAP summary plot or nomogram. 【TODO】

## References

刻意留空。正文中的 `[REF-n: …]` 标注了需要哪一类文献，
请补入真实引用后再建立本表——生成带占位的参考文献表只会增加误投风险。

# RA-L 投稿实施计划

> **给后续执行者：** 本计划应按任务逐项推进。每个任务都使用复选框（`- [ ]`）记录进度。若由 Codex 继续执行，建议使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`，按任务推进、按阶段复核。

---

## 进度总览（更新于 2026-07-02）

| 任务 | 交付物 | 截止 | 状态 | 备注 |
|---|---|---|---|---|
| T1 锁定故事线 | `docs/ral_story_brief.md` | 06-21 | ✅ 完成 | 叙事已收敛为 EGHC |
| T2 RA-L大纲 | `docs/ral_outline.md` | 06-24 | ✅ 实质完成 | LaTeX 全文五节已按 EGHC 叙事重写 |
| T3 冻结实验协议 | `docs/experiment_protocol.md` | 06-28 | ✅ 实质冻结 | EGHC3_v3 配置已冻结，manifest 完整 |
| T4 主实验复跑 | `data/output/ablation_matrix/EGHC3_v3_qwen35_full/` | 07-05 | ✅ **已完成** | 900 样本 3 splits：**RSR 60.89%, SSR 55.22%**；split 文件完整性已验证 |
| T5 消融实验 | `paper/ablation_table.md` | 07-19 | 🟢 **大幅推进** | 消融矩阵 37 变体（S0-S7/D1/V1 等）+ bootstrap CI 已完成；待整理为 `ablation_table.md` |
| T6 失败分析 | `paper/failure_analysis.md` | 07-26 | 🟡 部分完成 | 分层失败模式已写入 experiments.tex；bootstrap CI 已算；定性分析待补 |
| T7 UR5/真实验证 | `paper/real_validation.md` | 08-09 | ⬜ 未开始 | 默认方案：离线真实图像验证；07-27 前须决策 |
| T8 制作图表 | `paper/figures/` | 08-12 | 🟢 **初版已生成** | 5 个 PDF：system_overview / eghc_architecture / main_results / ablation / route_distribution |
| T9 英文初稿 | `paper/main.tex` | 08-16 | 🟢 **LaTeX 全文结构已就位** | main.tex + 5 个 sections/*.tex 已存在；main.pdf 已编译（07-02）；未提交修改 |
| T10 引用审计 | `paper/citation_claim_audit.md` | 08-20 | ⬜ 未开始 | 当前无不当声称 |
| T11 内部审稿 | `paper/internal_review_report.md` | 08-23 | ⬜ 未开始 | 依赖 T9 |
| T12 双盲格式 | 可投稿 PDF | 08-30 | ⬜ 未开始 | 依赖 T9-T11 |
| T13 最终投稿 | PaperCept 提交 | 09-03 | ⬜ 未开始 | 依赖 T12 |

### 07-02 服务器实查记录

**路径映射修正：**
- 计划路径 `paper_draft/ral_2026/` → 实际路径 `paper/`
- 计划路径 `data/output/ral_2026/` → 实际路径 `data/output/ablation_matrix/`
- 全文计划文件路径已同步更新

**实验数据验证（SSH 直连）：**
- `EGHC3_v3_qwen35_full/`：3 个 split 目录，每 split 12 个 JSON（6 out + 6 details），full_protocol_summary.json 确认
- 消融矩阵 37 个子目录：S0-S7、D1、V1、多个 EGHC 变体、UHS 变体等
- Bootstrap CI（`data/output/statistics/eghc3_bootstrap_ci.*`）：EGHC3_v3 vs S0 → RSR +3.00pp (p=0.027), SSR +7.67pp (p<0.001)
- Call budget 核算完成：EGHC3_v3 平均 3.16 calls/sample

**论文文件验证：**
- `paper/main.tex` + `paper/sections/{introduction,method,experiments,related_work,conclusion}.tex` 全部存在
- `paper/main.pdf` 已编译（221KB，07-02 15:40）
- `paper/figures/` 含 5 个 PDF 图
- 当前分支 `experiment/routing-v2`，有 12 个未提交修改 + 7 个未跟踪文件

**07-02 当天新增（未提交）：**
- `docs/experiments/2026-07-02-eghc-routing-ablation-split0.md`
- `docs/experiments/2026-07-02-eghc-no-mask-repair-split0.md`
- `docs/experiments/2026-07-02-offline-inference-cost-summary.md`
- `data/output/statistics/ral_ablation_call_budget_with_routing.*`

**⚠️ 风险：** 论文所有 sections 今天有修改但未 commit，需立即提交防止丢失。

### 06-29 重大进展记录

**论文全面修订（commit `38108cd`）：**
- 标题改为 "Evidence-Gated Hierarchical Consensus Routing for Free-Form Language-Guided Grasping"
- 核心主张：把 FreeGrasp 的直接 VLM 回答变成可审计的 target/blocker 决策过程
- 全部 5 个 section 重写；三表结构（主对比 / oracle 上界 / 分层分析）

**EGHC3_v3 全量验证完成：**
- 900 样本，3 splits，no GT features, no benchmark difficulty labels
- RSR 60.89%, SSR 55.22%
- 相对 FreeGrasp GPT-4o 报告基线：+13.6pp RSR / +17.0pp SSR
- 相对 S0 同 cache 基线：+3.00pp RSR / +7.67pp SSR
- S1 oracle（67.44%/60.11%）明确标注为 diagnostic upper bound

**Git 提交：** `38108cd` + `ccb16d4`，共 33 个文件变更

**下一步最值得补的：** paired bootstrap/CI，把 EGHC3_v3 vs S0、EGHC3_v3 vs S1 的置信区间补进实验表

### 06-28 进展记录（历史）

**叙事变更：** 核心贡献从"Protocol-Calibrated OVL Reasoning"改为"Evidence-Gated Heterogeneous Cascade (EGHC)"

**最佳候选结果确认：**
- 旧候选 `UHS1_split0`：RSR 61.00%, SSR 53.00%
- 新候选 `EGHC3_v3`（split0）：RSR 62.00%, SSR 57.33%

**Qwen adjudicator 决策：** 固定 `qwen3.5-plus-2026-04-20`，qwen3.7-plus 整体不如 EGHC3_v3

**全量验证启动：** split_0 完成，split_1 部分完成（medium_no_ambi 48/50），split_2 未开始

---

**目标：** 在 2026-09-01 至 2026-09-05 窗口向 IEEE Robotics and Automation Letters（RA-L）提交一篇双盲论文，主题为面向 FreeGrasp 式自由语言抓取的协议校准开放视觉语言推理。

**总体思路：** 这篇文章要按 RA-L letter 来写，而不是按长篇 IROS 初稿来写。全文围绕一个核心主张组织：性能提升不是简单来自“换了更强模型”，而是来自对象 ID 约束、视觉标记、复核策略、Molmo cache 控制和点约束分割共同构成的可执行推理协议。

**技术栈：** FreeGrasp 项目 `E:\freegrasp_project\FreeGrasp_code-main`、Python 评测脚本、FreeGraspData、MiMo/Qwen/GPT-4o 兼容 VLM 调用、Molmo cache、LangSAM 分割、IEEE RA-L 双栏模板、PaperCept 投稿系统。

---

## 一、RA-L 官方约束

- RA-L 定位：发表简洁的机器人与自动化原创研究，包括创新想法、应用结果、理论发现和应用案例。
- 页数限制：标准稿件为 IEEE 双栏 6 页，包括图表和参考文献；最多可付费增加 2 页，绝对上限为 8 页。
- 投稿时间：全年开放投稿；稿件从接收到发表或拒稿通常在 6 个月内完成。
- 评审方式：双盲评审，至少两名独立评审人。
- 多媒体材料：可以提交一个视频、数据仓库、代码和 readme 文件；但不能用补充文本或额外图表绕过正文页数限制。
- 官方说明来源：https://www.ieee-ras.org/publications/ra-l/ra-l-information-for-authors/

## 二、投稿决策

- 目标期刊：IEEE Robotics and Automation Letters。
- 目标投稿窗口：2026-09-01 至 2026-09-05。
- 内部内容冻结：2026-08-25。
- 内部格式冻结：2026-08-30。
- 理想提交日期：2026-09-03。
- 最晚备份提交日期：2026-09-05。
- 工作标题：Protocol-Calibrated Open Vision-Language Reasoning for Free-Form Robotic Grasping。
- 中文核心论点：在自由语言杂乱抓取任务中，本文证明通过对象 ID、视觉标记、复核策略、cache 控制和点约束分割进行协议校准，可以让开放或可替代 VLM 在 FreeGraspData 上超过原 FreeGrasp 论文报告的 GPT-4o 基线；该结论由完整 split 仿真实验、消融实验、失败分析和有边界的 UR5 或真实图像验证支持。

## 三、强制 Go/No-Go 节点

- Go 节点 1，2026-07-05 前：主实验命令必须跑通，并生成 `full_protocol_summary.json`。
- Go 节点 2，2026-07-19 前：主结果表和核心消融表必须完成，并保存样本级日志。
- Go 节点 3，2026-08-09 前：必须完成 UR5 真实机器人验证，或完成明确标注为“真实图像离线验证”的替代证据。
- Go 节点 4，2026-08-20 前：英文 RA-L 初稿必须能压进 8 页以内，包括参考文献。
- Go 节点 5，2026-08-30 前：双盲 PDF、视频、代码 readme 和投稿元数据必须准备完成。
- No-go 规则：如果 2026-07-19 前主结果无法在 fresh Molmo cache 加三 split 条件下复现，不建议 9 月硬投，应先修复实验协议。
- No-go 规则：如果 2026-08-09 前没有 UR5 或真实图像验证，除非消融证据非常强，否则投稿时必须显著降低结论边界。
- No-go 规则：如果 2026-08-30 最终稿仍超过 8 页，应删减次要相关工作、缩小定性图、把演示材料移到视频或代码包，而不是超页。

---

## 四、文件与产物位置

> **路径映射说明（2026-07-02 更新）：** 服务器实际目录结构与最初计划不同。稿件目录为 `paper/`（非 `paper_draft/ral_2026/`），实验结果目录为 `data/output/ablation_matrix/`（非 `data/output/ral_2026/`）。以下已更新为实际路径。服务器路径前缀：`/home/public/zb/FreeGrasp_code-freegrasp_codex/`

**本地（Windows）：**
- 当前基础稿：`E:\freegrasp_project\FreeGrasp_code-main\paper_draft\freegrasp_iros_draft_v3_zh.md`
- 当前图生成脚本：`E:\freegrasp_project\FreeGrasp_code-main\paper_draft\generate_freegrasp_iros_figures_v3.py`
- 当前图 PDF：`E:\freegrasp_project\FreeGrasp_code-main\output\pdf\freegrasp_iros_figures_v3_zh.pdf`
- 主实验脚本：`E:\freegrasp_project\FreeGrasp_code-main\evaluate_mimo_full_protocol.py`
- 单次实验脚本：`E:\freegrasp_project\FreeGrasp_code-main\evaluate_mimo.py`
- 公共评测工具：`E:\freegrasp_project\FreeGrasp_code-main\evaluate_common.py`
- 指标计算工具：`E:\freegrasp_project\FreeGrasp_code-main\calculate_SR.py`

**服务器（实际存放）：**
- RA-L 稿件目录：`paper/`（含 `main.tex`、`sections/`、`figures/`）
- 实验结果目录：`data/output/ablation_matrix/`（含各变体子目录）
- 主实验结果：`data/output/ablation_matrix/EGHC3_v3_qwen35_full/`
- 消融矩阵：`data/output/ablation_matrix/S0/` ~ `S7/`、`D1/`、`V1/` 等
- 统计分析：`data/output/statistics/`（bootstrap CI、call budget）
- 实验日志：`docs/experiments/`
- 视频目录：`paper/video`（待创建）
- 复现材料包：`paper/artifact_package`（待创建）

---

## 任务 1：锁定论文主张、范围和 RA-L 故事线

**截止时间：** 2026-06-21

**输出文件：** `docs/ral_story_brief.md`

- [x] 创建 `docs/ral_story_brief.md`。
- [x] 明确中心主张：本文主要贡献是协议校准，而不是单纯替换模型。
- [x] 将贡献 1 定义为对象 ID 约束的 VLM 推理与修复。
- [x] 将贡献 2 定义为 Molmo 指向点引导的实例绑定与分割后处理。
- [x] 将贡献 3 定义为可复现的 cache/split 评测协议。
- [x] 将贡献 4 定义为校准后的开放模型协议在 FreeGraspData 上超过原 FreeGrasp GPT-4o 报告基线。
- [x] 写清楚结论边界：若没有同环境 GPT-4o 复跑，最强结论只能是”相对原论文报告基线”的提升。
- [x] 决定 RA-L 正文是否包含 UR5 真实机器人实验，或只包含真实图像离线验证。
- [x] 保存一个摘要骨架，包含问题、缺口、方法、结果和边界。

## 任务 2：建立 RA-L 大纲和页数预算

**截止时间：** 2026-06-24

**输出文件：** `docs/ral_outline.md`

- [ ] 将当前 v3 中文稿压缩成 RA-L 结构，包括 Introduction、Related Work、Method、Experiments、Real-World Validation、Conclusion 六个主体部分。
- [ ] 分配页数预算：摘要 0.15 页，引言 0.75 页，相关工作 0.65 页，方法 1.20 页，实验 1.70 页，真实验证 0.60 页，结论 0.20 页，参考文献 0.70 页，图表嵌入这些预算内。
- [ ] 规划 Figure 1 为方法架构图：图像和任务输入 -> Molmo 对象标记 -> VLM 推理 -> ID 修复和复核 -> 点约束 LangSAM -> 抓取候选选择。
- [ ] 规划 Table I 为主结果表：六个子集的 RSR、SSR 和平均值。
- [ ] 规划 Table II 为消融表：完整方法、无 ID repair、无 review、无 point segmentation、旧 cache、model-only。
- [ ] 规划 Figure 2 为定性和失败分析：easy/medium/hard 成功案例加两个失败模式。
- [ ] 根据硬件证据决定 Figure 3 是 UR5/真实场景验证图，还是把真实验证主要放入视频材料。
- [ ] 删除所有无法服务于计划图表或核心论点的段落。

## 任务 3：冻结实验协议

**截止时间：** 2026-06-28

**输出文件：** `docs/experiment_protocol.md`

- [ ] 记录六个子集名称：`easy_no_ambi`、`easy_yes_ambi`、`medium_no_ambi`、`medium_yes_ambi`、`hard_no_ambi`、`hard_yes_ambi`。
- [ ] 记录 split 设置：`0`、`1`、`2`。
- [ ] 记录主实验命令：

```powershell
cd E:\freegrasp_project\FreeGrasp_code-main
python evaluate_mimo_full_protocol.py --model-name mimo-v2.5 --max-output-tokens 713 --subset-policy best_known_v1 --run-root data/output/ablation_matrix/EGHC3_v3_qwen35_full --splits 0 1 2 --fresh-molmo --no-resume
```

- [ ] 记录中断后继续运行命令：

```powershell
cd E:\freegrasp_project\FreeGrasp_code-main
python evaluate_mimo_full_protocol.py --model-name mimo-v2.5 --max-output-tokens 713 --subset-policy best_known_v1 --run-root data/output/ablation_matrix/EGHC3_v3_qwen35_full --splits 0 1 2 --reuse-molmo --resume
```

- [ ] 写明主结果使用 fresh Molmo cache，并且只在所有 split 之前统一生成一次。
- [ ] 写明复用旧 cache 的探索实验只能作为 sensitivity analysis。
- [ ] 写明所有论文表格必须追溯到样本级 JSON 文件，不能只追溯到手工表格。
- [ ] 创建一个 manifest 或 checksum 文件，列出论文中所有被使用的 JSON 结果文件。

## 任务 4：运行主实验并核对结果

**截止时间：** 2026-07-05

**输出文件：** `data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json`

- [ ] 运行任务 3 中的主实验命令。
- [ ] 确认 `data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json` 已生成。
- [ ] 确认每个 split 目录下都有六个 `out_*.json` 文件和六个 `details_*.json` 文件。
- [ ] 将最终汇总表复制到 `paper/results_main_table.md`。
- [ ] 将复跑结果与当前 v3 声称的数值比较：平均 RSR 约 0.6022，平均 SSR 约 0.5489。
- [ ] 如果复跑平均 RSR 或 SSR 与 v3 声称值相差超过 0.03 绝对值，将 v3 数值标注为历史结果，并以新复跑结果为准。
- [ ] 将控制台日志保存到 `data/output/ablation_matrix/EGHC3_v3_qwen35_full/run_log.txt`。

## 任务 5：运行消融实验

**截止时间：** 2026-07-19

**输出文件：** `paper/ablation_table.md`

- [ ] 运行复用 Molmo cache 的完整协议，作为 cache 敏感性分析：

```powershell
cd E:\freegrasp_project\FreeGrasp_code-main
python evaluate_mimo_full_protocol.py --model-name mimo-v2.5 --max-output-tokens 713 --subset-policy best_known_v1 --run-root data/output/ablation_matrix/ablation_reuse_cache --splits 0 1 2 --reuse-molmo --no-resume
```

- [ ] 使用 `evaluate_mimo.py` 和 `--mimo-retry-mode none` 在代表性子集上运行 model-only/no-repair 基线。
- [ ] 使用 `--segmentation-variant baseline` 在代表性子集上运行无点约束分割实验。
- [ ] 使用 `--mimo-retry-mode none` 与 `--mimo-retry-mode id_repair` 比较 ID repair 的贡献。
- [ ] 在 `hard_no_ambi` 和 `hard_yes_ambi` 上运行 hard review 消融。
- [ ] 在 `easy_no_ambi`、`easy_yes_ambi`、`medium_no_ambi`、`medium_yes_ambi` 上运行 target review 消融。
- [ ] 所有消融表使用同样的六子集排序。
- [ ] 在日志支持的情况下，报告 RSR、SSR、invalid-ID rate、parse-failure rate 和 RSR-to-SSR gap。
- [ ] 如果时间紧，优先完成三个消融：无点约束分割、无 ID repair/review、旧 cache 对 fresh cache。

## 任务 6：失败分析和统计分析

**截止时间：** 2026-07-26

**输出文件：** `paper/failure_analysis.md`

- [ ] 将失败类型分为推理选错物体、非法 ID、解析失败、分割到错误实例、分割过大、歧义遮挡物判断错误。
- [ ] 如果样本足够，从每个 hard 子集中至少抽取 10 个失败案例。
- [ ] 生成按子集划分的 RSR-to-SSR gap 图。
- [ ] 使用样本级 bootstrap 或 split-level 聚合计算每个子集的均值和置信区间。
- [ ] 写一段解释为什么 hard ambiguous 场景仍然困难。
- [ ] 写一段解释为什么点约束分割会让 SSR 的提升大于 RSR。
- [ ] 将失败分析脚本或 notebook 保存到 `paper/analysis_scripts`。

## 任务 7：准备 UR5 或真实图像验证

**截止时间：** 2026-08-09

**输出文件：** `paper/real_validation.md`，以及可用的视频片段

- [ ] 在 2026-07-27 前决定是否能够使用 UR5 硬件。
- [ ] 如果可以使用 UR5，采集 30 次 trial：10 个 easy、10 个 medium、10 个 hard。
- [ ] 对每次 UR5 trial 记录 RGB 图像、深度图、自然语言指令、选择的对象 ID、预测 mask、抓取姿态、执行成功与否、失败原因。
- [ ] 对 UR5 trial 报告四个指标：reasoning success、mask success、grasp execution success、full task success。
- [ ] 如果无法使用 UR5，采集至少 30 个真实 RGB-D 或 RGB 场景，并运行离线对象选择和分割。
- [ ] 对真实图像离线验证必须明确说明：它验证的是感知/推理迁移，而不是完整机械臂执行成功率。
- [ ] 制作一个视频，包含三个成功案例和两个失败案例。
- [ ] 只有在 UR5 实际执行抓取后，才能在论文中声称 real robot success。

## 任务 8：制作图表

**截止时间：** 2026-08-12

**输出目录：** `paper/figures`

- [ ] 用英文重画 Figure 1，风格保持 RA-L 简洁清晰，不出现中文文字。
- [ ] 将 Figure 1 导出为 PDF 和 PNG。
- [ ] 用 LaTeX booktabs 风格创建 Table I，包含 RSR、SSR 和平均值。
- [ ] 用 LaTeX booktabs 风格创建 Table II，包含相对完整方法的消融差值。
- [ ] 创建 Figure 2，展示定性案例和失败标签。
- [ ] 只有当真实机器人或真实图像证据足够强时才创建 Figure 3；否则将真实验证压缩到视频和短段落。
- [ ] 每个图注都必须说明实验设置和图的主要信息，而不只是描述图像内容。
- [ ] 每个表格数值都必须能追溯到 JSON 结果文件。

## 任务 9：撰写英文 RA-L 正文

**截止时间：** 2026-08-16

**输出文件：** `paper/main.tex`（已有）或 `paper/main.docx`

- [ ] 将 v3 中文稿改写为英文 RA-L 稿，而不是逐句直译。
- [ ] 使用最终标题：Protocol-Calibrated Open Vision-Language Reasoning for Free-Form Robotic Grasping。
- [ ] 摘要最后写，必须在表格和图固定后再定稿。
- [ ] 引言末尾写三条贡献，每一条都绑定一个结果或消融证据。
- [ ] 相关工作要压缩，分为 language-conditioned grasping、VLM robot reasoning、mark/point-based grounding 三组。
- [ ] 方法部分按 task formulation、overview、object-ID reasoning、review/repair、point-constrained segmentation、implementation details 组织。
- [ ] 实验部分按 setup、main result、ablation、failure analysis、real validation 组织。
- [ ] 结论必须避免普遍化表述，并明确“相对原论文报告基线”的边界。
- [ ] 全文控制在 8 页以内，包括参考文献。

## 任务 10：引用和主张审计

**截止时间：** 2026-08-20

**输出文件：** `paper/citation_claim_audit.md`

- [ ] 将 v3 参考文献草表中的每条文献转换成 BibTeX 或 IEEE 参考文献格式。
- [ ] 核对 FreeGrasp 的元数据，并准确使用 arXiv/IROS 状态。
- [ ] 核对 MOKA、RoboPoint、VoxPoser、RT-2、Octo、SAM、GroundingDINO、GraspNet、Molmo、Qwen2.5-VL、GraspMolmo、Reasoning Grasping 后再引用。
- [ ] 为每条引用写一句话，说明它支撑正文中的哪个具体主张。
- [ ] 删除只起装饰作用、没有支撑具体主张的引用。
- [ ] 检查全文是否声称“同环境优于 GPT-4o”；如果没有同环境复跑，则删除这类表述。
- [ ] 检查全文是否声称“真实机器人成功”；如果没有 UR5 执行实验，则删除这类表述。

## 任务 11：内部审稿模拟

**截止时间：** 2026-08-23

**输出文件：** `paper/internal_review_report.md`

- [ ] 以严格 RA-L 审稿人的角度审阅稿件。
- [ ] 分别评价 novelty、technical correctness、experimental rigor、reproducibility、clarity、robotics relevance。
- [ ] 列出最可能被审稿人质疑的五个问题。
- [ ] 为每个质疑写一个直接应对方案。
- [ ] 在 48 小时内修复所有可以修复的问题。
- [ ] 对无法修复的问题，在 limitations 段落或投稿说明中保留边界。

## 任务 12：双盲和 RA-L 格式检查

**截止时间：** 2026-08-30

**输出文件：** 可投稿 PDF 和源码包

- [ ] 从评审 PDF 中移除作者姓名、单位、致谢、带个人信息的项目路径、自识别链接。
- [ ] 如果提供仓库链接，必须使用匿名方式。
- [ ] 使用 IEEE 双栏格式。
- [ ] 尽量压到 6 页，绝对不能超过 8 页。
- [ ] 参考文献使用 IEEE 数字引用格式。
- [ ] 检查所有图在双栏缩放后仍然可读。
- [ ] 检查 PDF 字体是否嵌入。
- [ ] 如果提交 multimedia，准备一个视频文件和一个代码/数据 readme 压缩包。
- [ ] 确认 multimedia 中没有用于绕过页数限制的额外正文或额外图表。

## 任务 13：最终投稿包

**截止时间：** 2026-09-03

**输出文件：** PaperCept 可提交 RA-L 投稿包

- [ ] 最终 PDF。
- [ ] 源文件。
- [ ] BibTeX 或参考文献文件。
- [ ] 图文件。
- [ ] 一个 multimedia 视频。
- [ ] 代码/数据 readme 压缩包。
- [ ] 投稿元数据。
- [ ] 尽可能从 RA-L 关键词列表中选择关键词。
- [ ] 准备 ORCID 和 PaperCept 账号信息。
- [ ] 最终核对 RA-L 作者指南。
- [ ] 通过 PaperCept RA-L 系统提交。

---

## 五、每周倒排日程

| 周次 | 日期 | 核心目标 | 交付物 |
|---|---|---|---|
| 第 0 周 | 2026-06-18 至 2026-06-21 | 锁定故事线和期刊约束 | `docs/ral_story_brief.md` |
| 第 1 周 | 2026-06-22 至 2026-06-28 | 冻结大纲和实验协议 | `docs/ral_outline.md`，`docs/experiment_protocol.md` |
| 第 2 周 | 2026-06-29 至 2026-07-05 | 完成主实验复跑 | `data/output/ablation_matrix/EGHC3_v3_qwen35_full/` |
| 第 3 周 | 2026-07-06 至 2026-07-12 | 启动消融实验 | 部分消融日志 |
| 第 4 周 | 2026-07-13 至 2026-07-19 | 完成核心消融 | `paper/ablation_table.md` |
| 第 5 周 | 2026-07-20 至 2026-07-26 | 完成失败分析和统计分析 | `paper/failure_analysis.md` |
| 第 6 周 | 2026-07-27 至 2026-08-02 | 搭建 UR5 或真实图像验证流程 | 验证协议 |
| 第 7 周 | 2026-08-03 至 2026-08-09 | 完成 UR5 或真实图像验证 | `paper/real_validation.md`，视频 |
| 第 8 周 | 2026-08-10 至 2026-08-16 | 完成英文 RA-L 初稿 | `paper/main.tex` |
| 第 9 周 | 2026-08-17 至 2026-08-23 | 完成引用审计和内部审稿 | `paper/citation_claim_audit.md`，`paper/internal_review_report.md` |
| 第 10 周 | 2026-08-24 至 2026-08-30 | 完成格式和双盲检查 | 可投稿 PDF |
| 第 11 周 | 2026-08-31 至 2026-09-05 | 最终核查并提交 | PaperCept 投稿 |

---

## 六、RA-L 正文骨架

```text
Title
Abstract
I. Introduction
II. Related Work
III. Method
    A. Task Formulation
    B. Protocol-Calibrated VLM Reasoning
    C. ID Repair and Review Policies
    D. Point-Constrained Instance Segmentation
IV. Experiments
    A. Setup
    B. Main Results
    C. Ablation Studies
    D. Failure Analysis
V. Real-World or Real-Image Validation
VI. Conclusion
References
```

## 七、最终投稿前检查清单

- [ ] 论文只有一个主张，而不是五个松散主张。
- [ ] 每条贡献都有表格、图、消融或验证结果支撑。
- [ ] 主结果来自 fresh-cache 完整复跑，而不是手工挑选的表格行。
- [ ] 消融实验隔离的是协议组件，而不只是比较模型名字。
- [ ] 论文同时报告 RSR 和 SSR。
- [ ] 论文诚实报告 hard case 失败。
- [ ] 如果没有同环境 GPT-4o 复跑，论文不声称同环境优于 GPT-4o。
- [ ] 如果没有 UR5 执行实验，论文不声称真实机器人抓取成功。
- [ ] 最终 PDF 满足双盲要求。
- [ ] 最终 PDF 不超过 8 页。
- [ ] 视频短、清晰，并且与论文主张一致。
- [ ] 代码/数据 readme 能让审稿人理解每张表来自哪些实验产物。


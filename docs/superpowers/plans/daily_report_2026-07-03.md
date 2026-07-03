# FreeGrasp RA-L 每日进度报告

**日期：** 2026-07-03（周五）
**当前周次：** 第 3 周（06-29 — 07-05）
**本周目标：** 完成主实验复跑 → Go 节点 1

---

## 当前任务：T4 主实验复跑

**截止日期：** 07-05（还剩 2 天）
**Go 节点 1：** 07-05 — 主实验必须跑通并生成 full_protocol_summary.json

### 服务器实查（SSH 直连，07-03）

| 检查项 | 状态 | 详情 |
|--------|------|------|
| full_protocol_summary.json | ✅ 存在 | 4343 bytes, 06-29 03:24 |
| split_0 文件完整性 | ✅ 12 files | 6 out + 6 details |
| split_1 文件完整性 | ✅ 12 files | 6 out + 6 details |
| split_2 文件完整性 | ✅ 12 files | 6 out + 6 details |
| results_main_table.md | ❌ 不存在 | T4 checklist 收尾项 |
| run_log.txt | ❌ 不存在 | T4 checklist 收尾项 |

**实测结果：** RSR 60.89%, SSR 55.22%（900 样本, 3 splits）

---

## 全任务看板（07-03 SSH 实查）

| 任务 | 截止 | 状态 | 服务器验证 |
|------|------|------|------------|
| T1 锁定故事线 | 06-21 | ✅ 完成 | — |
| T2 RA-L大纲 | 06-24 | ✅ 实质完成 | — |
| T3 冻结实验协议 | 06-28 | ✅ 实质冻结 | — |
| T4 主实验复跑 | 07-05 | ✅ 数据完成 | full_protocol_summary.json ✅, split 完整性 ✅；results_main_table.md ❌, run_log.txt ❌ |
| T5 消融实验 | 07-19 | ✅ 已完成 | `docs/experiments/ablation_table.md` 存在（5511 bytes, 07-03）；37+ 变体目录 |
| T6 失败分析 | 07-26 | ❌ 未生成 | `paper/failure_analysis.md` 不存在 |
| T7 UR5/真实验证 | 08-09 | ⬜ 未开始 | `paper/real_validation.md` 不存在 |
| T8 制作图表 | 08-12 | 🟢 初版已生成 | 5 个 PDF 图（06-29），全部存在 |
| T9 英文初稿 | 08-16 | 🟢 结构就位 | main.tex (07-01) + main.pdf (07-03, 221KB) + 5 sections ✅ |
| T10 引用审计 | 08-20 | ⬜ 未开始 | `citation_claim_audit.md` 不存在 |
| T11 内部审稿 | 08-23 | ⬜ 未开始 | `internal_review_report.md` 不存在 |
| T12 双盲格式 | 08-30 | ⬜ 未开始 | — |
| T13 最终投稿 | 09-03 | ⬜ 未开始 | — |

### 辅助产物

| 文件 | 状态 | 详情 |
|------|------|------|
| Bootstrap CI | ✅ | csv + json + md（06-30），EGHC3_v3 vs S0 显著 |
| 消融矩阵 | ✅ | 37+ 变体目录（S0-S7, D1, V1, EGHC 系列, UHS 系列等） |

---

## Go/No-Go 节点倒计时

| 节点 | 日期 | 剩余天数 | 状态 |
|------|------|----------|------|
| **Go 节点 1** | 07-05 | **2 天** | 数据 ✅，收尾项 ❌（results_main_table.md, run_log.txt） |
| Go 节点 2 | 07-19 | 16 天 | ✅ 消融表已完成，可提前锁定 |
| Go 节点 3 | 08-09 | 37 天 | ❌ 尚未启动 |
| Go 节点 4 | 08-20 | 48 天 | 🟢 初稿结构在，需打磨 |
| Go 节点 5 | 08-30 | 58 天 | ⬜ |

---

## Git 状态（07-03 实查）

**分支：** `experiment/routing-v2`

**未提交变更：** 仅 1 个未跟踪文件
- `docs/superpowers/reports/2026-07-03-eghc-ral-ppt-plan.md`

**🟢 好消息：** 07-02 记录的 12 个未提交修改已全部 commit。论文内容安全。

**最近 7 天提交亮点（20+ commits）：**
- `fdeb814` GroundingDINO 兼容性补丁（07-03）
- `604f6a7` EGHC 消融实验文档化 + ablation_table.md（07-01 ~ 07-03）
- `a4c51d0` Call-budget 核算脚本（06-30）
- `2380663` RAL 外部审稿任务收尾（06-30）
- `e3c08fb` RAL 内部审稿包 + bootstrap CI 脚本（06-29）
- `f5ad61c` 论文围绕 EGHC3_v3 重构（06-29）
- `2a1334a` EGHC-v1 实现 + 论文初稿 + 评测管线（06-26）

---

## 风险与警告

### 🟡 T4 收尾项缺失
`results_main_table.md` 和 `run_log.txt` 不存在。虽然主数据完整，但 T4 checklist 未完全打勾。建议补建。

### 🟡 T5 路径不一致
`ablation_table.md` 在 `docs/experiments/` 而非计划中的 `paper/`。不影响数据完整性，但投稿前需统一。

### 🔴 T6 失败分析是当前最大缺口
`failure_analysis.md` 完全不存在。截止 07-26（23 天），但这是 Go 节点 2 之后最重要的论文内容。分层失败模式数据（bootstrap CI、experiments.tex 中的分析）已有，但定性分析和文档化未启动。

### 🟡 T7 决策窗口
07-27 前必须决定 UR5 方案还是真实图像离线验证。还剩 24 天，但当前没有任何验证文件。

---

## 今日优先建议

1. **补建 T4 收尾项：** 将主结果汇总表写入 `paper/results_main_table.md`，保存运行日志到 `data/output/ablation_matrix/EGHC3_v3_qwen35_full/run_log.txt`。这样 Go 节点 1 可以干净通过。

2. **启动 T6 失败分析：** 这是当前最该投入时间的任务。Bootstrap CI 数据已有（06-30），experiments.tex 已有分层失败模式。需要做的是：定性失败案例抽取 + 文档化为 `paper/failure_analysis.md`。

3. **提交最后一个未跟踪文件：**
   ```bash
   cd /home/public/zb/FreeGrasp_code-freegrasp_codex
   git add docs/superpowers/reports/2026-07-03-eghc-ral-ppt-plan.md
   git commit -m "docs: add RAL PPT plan"
   ```

4. **考虑 T5 路径统一：** 把 `docs/experiments/ablation_table.md` 复制或移动到 `paper/ablation_table.md`，与计划路径对齐。

---

*报告生成时间：2026-07-03 | 数据来源：计划文件 + SSH 实查（07-03 直连验证）*

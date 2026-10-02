# RDR-20260930-B1-ADAPTIVE-V5

状态：**已冻结（2026-09-30，Asia/Shanghai）**。冻结后不得修改本目录内的 `worker.py` / `protocol.py` / `score.py` / `prepare.py` 与 `inputs.json`；若发生任何漂移，必须另立实验 ID，不得在本目录续跑。

## 冻结元数据

- experiment_id：`b1_adaptive_20260930_v5`
- artifact_root：`/home/public/zb/freegrasp_unograsp_fusion_20260922_v1/b1_adaptive_20260930_v5`
- 冻结仓（只读，未改动）：`/home/public/zb/FreeGrasp_code-freegrasp_codex`，branch `experiment/routing-v2`，HEAD `346919d1cdbe96bc1923ba8c6a1b0cadfed243ea`（短 `346919d`），dirty 180。
- `order_seed=20260930`，`order_sha256=f4cce4326f86873943efd43fabbd91b060bb41726c7868123f2b6c40f0de7a95`（实测一致）。

冻结时刻文件哈希（sha256）：

| 文件 | sha256 |
| --- | --- |
| worker.py | 6a5979fca9f86f4a464f5975080b44ab19e8fa365564ac88a1a4b56a1e9ea43c（与 v3/v4 逐字节一致） |
| protocol.py | 253a5f446d98b5139834afdd3df946e6797a996d3fc7da41be5709b3092a679c（与 v3/v4 一致） |
| prepare.py | 78493e141d146b9b907741a2e290eecbbf2a50c4cea100e5fc533c9f2e3068fd（与 v3/v4 一致） |
| score.py | 6a64c84836ddfeb69ea15b2bc4283df0f85dc85ad3db9c74a6831a4972a2b2b2（与 v3/v4 一致） |
| harness_check.py | 3e3a36538b7d1f302d1c668fdf3cdf00be3ae0d0527f8acaee951c9ac7ebd69a（与 v3/v4 一致） |
| inputs.json | 81571e924c3550172f93068f5b5bd512d4aa644bbc892e34b360da6f91833da0 |
| score_only.json | 571e6b50e6fc929caac79e6a32b033e540ee33bfa6cee6e52267b228dcbfb7b7 |
| preparation.json | 299897fd634ae250d3376cc9793eef826c1949012d7b4bb09780f418eb338896 |
| replay/seal.json | 996157bbc3046fa0d03ed8cb8f7720d8222d8b98837b42a5d318048976c7136c |
| replay_score.json | 7179d41701886e24d1a20225e32d4e33e22eb4366954ab7df60349a900d13a08（与 v3/v4 逐字节一致） |

> 说明：`inputs.json` / `preparation.json` 内含**本目录绝对路径**，因此 v5 的哈希与 v4 必然不同（v4 为 `0f604ae5…` / `9243c2f1…`）；两者内容（24 行、scene、候选点、图像与 mask 资产哈希、选择规则）完全相同。判据是路径无关的 `replay_score.json`：v5 与 v3/v4 **逐字节一致**（`7179d417…`），`execution_order_sha256` 亦一致（`f4cce432…`）。

## 与前版的关系

- v2（`b1_adaptive_20260929_v2`）：36/72 臂后因执行器门控缺陷停止，已封存。
- v3（`b1_adaptive_20260930_v3`）：replay 24/24 `parity_gate=PASS`；付费批次停在 3/72（HTTP_401，凭证故障），已封存。
- v4（`b1_adaptive_20260930_v4`）：replay 24/24 `parity_gate=PASS`；付费批次自 00:27:05 起，MiMo 首次调用成功（HTTP 200），随后 Qwen 仲裁 HTTP 400，停在 3/72，已封存。
- v5：**代码与 v4 逐字节一致（零协议变更）**，仅再次轮换 Qwen 凭证并另建目录；同一 24 行、同一 seed/顺序哈希、同一三臂与停止门。

## v3 / v4 事故记录与凭证根因链（非代码缺陷）

- 两次停点均在 c002 三臂之后、c015 uniform 臂的 Qwen 仲裁处：
  - v3：登录 shell 依次 source `~/.profile` → `~/.bashrc` → `~/.freegrasp_env`，`.freegrasp_env` 中失效的 35 字符 key **最后覆盖生效**，worker 实际用该失效 key → HTTP 401（`invalid_api_key`）。
  - v4：环境链收敛到一把被 dashscope 判定为欠费/不可用的凭证 → HTTP 400（dashscope `Arrearage`）。
- 对照实验（同一冻结端点）：伪造 key → 401 `invalid_api_key`；真实但欠费账户的 key → 400 `Arrearage`。二者**均为凭证层面失败**，与模型、端点、payload、协议无关。
- 成本：v3 Qwen 0 次、¥0；v4 Qwen 0 次、¥0；两批各 1 次 MiMo（≈5288 tokens，等值估算 ¥0.0054，非账单）。
- 结论：既往"欠费"提示是**环境变量里的凭证问题**，不是账号余额判定错误，也不是模型/端点的选择问题。

## 凭证（v5 相对 v4 的唯一变更）

- 端点、模型、payload、预算、停止门全部不变：`https://dashscope.aliyuncs.com/compatible-mode/v1`，`model=qwen3.6-plus`。
- 凭证轮换为已知可用 key，仅按指纹引用：`sha256[:12]=e4f11b421d06`。`~/.bashrc` 与 `~/.freegrasp_env` 中 `QWEN_API_KEY` / `DASHSCOPE_API_KEY` 现均为该 key（两处指纹实测一致）。
- 付费前 live 探针（本目录冻结协议路径，读环境变量、不回显凭证）：`qwen3.6-plus` 文本调用 HTTP 200、带图调用 HTTP 200；`model_echo=qwen3.6-plus`、`finish_reason=stop`、`prompt_tokens`/`completion_tokens` 均存在、content 为严格 JSON。核心停止门字段全部满足。
- MiMo 凭证（`tp-` 前缀，Token Plan）不变。

## 闸门验收记录（v5，已完成，2026-09-30）

- `prepare.py`：`prepared=24`、`tests=9`、`direct=8`、`diagnostic_classes={simple:5, occlusion:10, identity:6, conflict:3}`；`data_exposure=exposed-retrospective`；源码/资产哈希断言全部通过。
- 24 行零网络 replay：`completed 24/24`、`api_attempts=0`、`status=complete`。
- `score.py replay`：`status=complete`、`parity_gate=PASS`、`n=24`、`ssr=13`、`rsr=15`。
- `replay_score.json` sha256 与 v3/v4 逐字节一致；`order_seed=20260930`、`execution_order_sha256=f4cce432…` 实测一致。

## scientific_question

在固定 B1 预测路由下，按可观测困难选择规划提示，是否优于原提示和统一证据提示？

- claim_to_test：仅限本次暴露样本、冻结路由的回顾性配对结果，不代表完整在线路由或泛化提升。
- falsifier：adaptive 的 SSR 净收益不大于 0，或 RSR 净下降，则不晋级；未优于 uniform 则不支持自适应选择的额外价值。
- baseline：`PATHB_FULL_B1_blk_arb_v25_envcheck_split0` 已保存路由；先重放全部原响应并验证 24/24 最终 ID、RSR、SSR、IoU（容差 .001）一致。
- unique_variable：planner 提示内容。A 原 B1；B 同一组路由证据 + 统一核查要求；C 同一组路由证据 + 按 conflict/identity/occlusion/simple 选择的要求。
- fixed：mimo-v2.5、qwen3.6-plus、原 B1 路由阈值、SAM1、eghc_mask_repair_v1、原重规划机制、输出上限 1024（仲裁 512）。
- data_exposure：exposed-retrospective / C-diagnostic。
- sampling：split0 六子集各 4 行，按 SHA256('20260929|scene|annotation') 排序取前四，与 v2/v3/v4 同一清单；未使用成败筛选。
- cluster_unit：scene-object；24 条固定分母，所有失败/未完成保留；不按中途分数调整方法或扩量。
- primary_metrics：SSR_official-equivalent（须过基线等价门）、RSR_current-map（须过映射门）；配对 recovery/regression、聚类 bootstrap 5000 次。

## API 与计算合同

- MiMo endpoint：`https://token-plan-cn.xiaomimimo.com/v1`；model=mimo-v2.5。只用现有 Token Plan，不购买/升级/切换按量端点。**套餐实际扣额必须从账户记录读取**；公开按量价只作等值估算，不得写成实际账单。
- Qwen endpoint：`https://dashscope.aliyuncs.com/compatible-mode/v1`；model=qwen3.6-plus。计价按输入 2 元/百万、输出 12 元/百万（<=256K）估算并累计，余额费用预算 5 元。思考 token 计入 completion_tokens（实测单次 reasoning ~0.8–1.6K），费用按 usage 实际值累计，仍受 5 元停止门约束。
- 最多 216 次外部请求（24 行 × 3 臂 × 每行每臂最多 2 MiMo + 1 Qwen）；已保存 router 响应不重发。并发 1，每请求超时 120 秒，网络重试 0。
- 发送内容：benchmark 标记 RGB、指令、可见候选、预测证据。不发 GT、难度标签、凭证或本机私密文档。
- 文本 UTF-8 <=32000 bytes、单图 <=2MP；计费预留 text bytes+16384 image tokens，实际 usage 超出预留即停止。
- 凭证仅从登录 shell 进程环境读取（经 `.freegrasp_env` 注入），不写盘、不回显。
- 启动契约：`bash -lc 'cd <artifact_root>; <venv>/bin/python worker.py paid'`（worker 自身设置 `CUDA_VISIBLE_DEVICES=3`、离线 HF、并发 1、无重试）。paid 硬前置：`replay_score.json` 的 `parity_gate=='PASS'` 且 `n==24`，且 `MIMO_API_KEY` 以 `tp-` 开头、`resolve_qwen_api_key()` 可用。

## 停止门（任一触发即停止整批，不自动重发，失败保留在分母内）

- 最终 `parse_status != 'valid_id'`（`FINAL_INVALID_ID`）
- 仲裁 `verifier_error_keep`（`VERIFIER_FAILURE`）
- 每行每臂 MiMo > 2 或 Qwen > 1（`ROW_CALL_BUDGET`）；总调用 > 216（`CALL_BUDGET`）
- 单阶段超时 7200 秒（`TIME_BUDGET`）；单请求超时 120 秒（`API_TRANSPORT_*`）
- HTTP 非 200、响应非 JSON、模型身份不符、usage 缺失、截断、空内容
- Qwen 累计费用 > 5 元或 token 超预留
- 回放队列不一致（`QWEN_REPLAY_MISMATCH` / `UNCONSUMED_REPLAY_OUTPUTS`）
- 源码哈希漂移（`preparation.json` 的 repo_code / scripts 校验）
- 任何写入冻结仓或读取 `score_only.json` / GT（`FROZEN_REPO_WRITE` / `FORBIDDEN_INFERENCE_FILE`）

## 工程阶段与完成条件

1. CPU 单测与输入隔离检查；确认 24 行唯一、六格均衡、来源与资产 hash。（v5 已完成）
2. 一次本地模型加载；24 行零网络 replay，全部通过 parity_gate 才进入付费。（v5 已完成，PASS）
3. 每样本按固定种子顺序轮换 A/B/C 顺序，固定整批协议。工程异常立即停止；不按局部得分调整规则。
4. 完成或停止后封存 raw 输出、离线评分，报告覆盖率、预算、所有负结果与源仓状态。
5. 本批不自动扩展到 300/900，不合入主协议，不提交代码。

paper_impact：diagnostic/negative/limitation；不进入 headline。
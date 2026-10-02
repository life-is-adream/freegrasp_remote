# B1 v6 split0 失败归因（2026-10-02）

## 范围与结论

本次离线复算 `resume8_repaired` 的 A/D/E 各300行，与历史 clean B1、实际执行代码、原始模型响应逐行对照；API=0、GPU=0，未改写实验目录。分析文件位于服务器 `b1_v6_failure_audit_20261002/`。300个案例×3臂不等于full900独立测试。

本轮没有成功提升SSR。D主要因错误预测easy后越过遮挡证据直接抓取而退化；E主要因目标歧义优先级高于遮挡证据，错误改为target_first而退化。回放控制另有不一致，故现有差值不是严格单变量因果估计。E新增router prompt实际未用于推理，本轮不能证明该prompt无效。

## 已复算结果

| 臂 | SSR | RSR | 相对A的SSR gain/loss/net |
|---|---:|---:|---:|
| A |161/300=53.67%|171/300=57.00%|—|
| D |142/300=47.33%|152/300=50.67%|11/30/−19|
| E |159/300=53.00%|172/300=57.33%|4/6/−2|

D−A的SSR场景聚类95%CI为[−10.44,−2.32]pp；E−A为[−2.69,+1.34]pp。区间反映这批输出的配对差异，不能消除执行混杂。

## D：难度分类与路线映射两层问题

`compute_difficulty_features`将候选数量、同标签组数、关系数量、指令词等压成一个加权分数，再按离easy/medium/hard三个质心的距离分类，并非训练好的视觉难度模型。标签主要来自router的target_candidates，其他候选多为unknown；这些关系也不等于独立验证的真实几何。

| 真实难度（仅事后分析） |预测easy|预测medium|预测hard|
|---|---:|---:|---:|
|easy|69|14|17|
|medium|47|19|34|
|hard|33|19|48|

正确136/300=45.33%；medium只有19%正确。真实难度本身也不是最佳路线标签。

`d_artifact.json` 的冻结映射为easy→direct、medium→blocker_first、hard→blocker_first。映射通过历史开发集路线频次取众数得到，未比较三种路线的成功率；实际上根本不会主动选target_first（只有fallback能保留）。因此“猜对难度”不保证“选对路线”。开发来源是历史PATHB_FULL_B1_blk_arb的split1/2，并非经过本轮完整无泄露审计的最优路线标签。

| A→D路线变化 | 行数 | SSR救回 | SSR损失 | 净变化 |
|---|---:|---:|---:|---:|
|blocker_first→direct|33|1|21|−20|
|target_first→direct|8|1|4|−3|
|direct→blocker_first|17|1|0|+1|
|target_first→blocker_first|29|8|3|+5|
|路线未变|213|0|2|−2|

41次改direct全部仍有router遮挡关系；38/41的预测难度与真实难度不符。25/30个SSR损失发生在预测easy后直接抓取。全部30个损失的最终ID都发生变化。分难度净SSR：easy +4、medium −17、hard −6。

这支持的机制是：粗粒度easy判定覆盖了任务级遮挡证据，移除了原有规划/检查路径。正收益支路target_first→blocker_first也存在，因此不能把失败归结为“更复杂路线总有害”。

## E：证据优先级与schema问题

实际run2、resume4–8 worker均读取保存的 `case["router_output"]`，调用 `select_route` 并注入 `frozen_route_assessment`；没有调用 `build_e_router_prompt`。该函数只在准备阶段计算过提示哈希。本轮E是既有router响应上的规则重路由，未检验新的证据提取prompt。

| A→E路线变化 | 行数 | SSR救回 | SSR损失 | 净变化 |
|---|---:|---:|---:|---:|
|direct→target_first|31|2|0|+2|
|blocker_first→target_first|21|2|5|−3|
|target_first→blocker_first|1|0|0|0|
|路线未变|247|0|1|−1|

21次blocker_first降级中，20次原因是候选歧义/缺失，1次是关系schema未识别。`select_e_route`要求无遮挡歧义才允许blocker_first，导致“目标不唯一”覆盖了“目标被挡住”的证据。

六个SSR损失逐项：

| 场景/查询对象 | 变化与证据 |
|---|---|
|1113/1|路线仍为blocker_first，但仲裁重新调用后ID4→3；属于执行控制漂移，不应归因于路由规则。|
|1842/9|原关系使用subject_id=10、object_id=6表示on-top；E只识别blocker_id/object_id及target_id/blocked_id，未得到完整关系，改target_first，最终ID10→6。|
|2030/2|两个lemon候选且存在遮挡关系，因歧义改target_first，ID2→3，SSR由1变0。两侧RSR均0，说明SSR和ID映射成功不等价。|
|4877/4|target ID为字符串red_bowl，解析后缺少合法候选；改target_first。最终ID仍2，但mask_query从white block变light green box，IoU约0.9944→0。|
|2157/8|多个blue cup候选且有遮挡关系，改target_first。最终ID仍4，但mask_query从orange toy gun变blue cup，IoU约0.8218→0.00085。|
|3078/2|三个cylinder候选，因歧义改target_first；第一抓由gray box ID4变成cylinder ID1，IoU约0.9886→0。|

两条同ID损失证明分割文本也是重要变量。不能继续用“SSR就是ID消歧率”作为严格等式。

## A少的一分，以及未改路由也变化的原因

历史clean为SSR162、RSR172；本轮A为161、171。对照发现6行最终ID发生变化，6行历史记录均为 `verifier_error_keep`（仲裁超时保留原计划），本轮重新调用仲裁后改ID。

唯一改变成功计数的是scene1703/object4：历史ID1、SSR/RSR均1、IoU0.970477；本轮ID2、SSR/RSR均0、IoU0.000938。不是分割数值抖动。

run2 worker在回放队列空时直接调用API，未保留历史超时分支；续跑也允许回放缺失时新请求。A共发生20次external_calls。D路线不变的213行有6行ID变化、16次调用，造成2个SSR损失；E路线不变的247行有3行ID变化、16次调用，造成1个SSR损失。

据此修正此前表述：不是所有30/6个损失都由改路由造成。D真正改路由的87行救回11、损失28；E真正改路由的53行救回4、损失5。这只是分层描述，不能事后删掉控制漂移行再宣称新的正式成绩。

## 工程与结论边界

付费worker曾将1848×1848的Molmo图传给分割，官方分割输入是1200×1200 parquet原图。已有repaired是固定reasoning后的离线分割重建。单样本IoU吻合只能验证该样本输入修复，不能证明完整回放等价；上述6行A的ID变化正是反例。

修复脚本复用了含原mask哈希的manifest，又在评分时跳过prediction哈希检查。audit.json保存了本次评分来源哈希，但旧manifest不能证明派生mask完整性。后续正式批次应单独封存派生mask哈希、repair seal、输入图来源和完整基线一致性报告。

## 下一步建议（未启动新实验）

1. 先修对照执行：路线未变则复用同一A最终预测；回放缺少响应应显式报缺失，不自动发新请求。若选择重新生成A，应一次性生成并共享，不分别重算A/D/E控制行。
2. 分割统一使用原图，VLM标注图独立传入；验证整批shape、schema、ID/文本一致性和派生哈希。将历史A最终ID差异全部解释后再验收基线。
3. 统一关系schema，明确subject/object的方向；非法ID记未知。未知/歧义不应自动推导为target_first，保留A或进一步收集证据。
4. 难度预测只能建议路线。改direct应额外满足目标唯一、可见自由、无可信遮挡关系等任务证据；映射应在独立开发集上用同输入多路线结果学习，不能用历史频次充当最优答案。
5. 下一轮先验证E的direct→target_first局部复核及必要的遮挡保护。该方向是本次事后发现，当前split0不能再当未见测试；需要独立验证并控制调用预算。不能把已见收益+2/300当作未来保证。

## 可复查产物

- 服务器：`/home/public/zb/freegrasp_unograsp_fusion_20260922_v1/b1_v6_failure_audit_20261002/audit.json`：36个loss臂记录、gain记录、历史差异及原始reasoning。
- 同目录 `paired_rows.csv`：600条A→D/E逐行比较；`controls.json`：控制漂移、映射覆盖、E prompt调用检查。
- 执行脚本：`audit_failure_20261002.py`、`audit_trace_20261002.py`、`audit_controls_20261002.py`（fusion根目录）。

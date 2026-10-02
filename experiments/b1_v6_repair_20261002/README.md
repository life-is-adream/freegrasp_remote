# B1 路由与执行修复版

本包替换旧续跑执行路径；不要将旧D/E产物续接成新协议。当前为cached-router规则修复，不宣称新增E提示已经在线评测。原冻结仓不改动。

## 修复

- safe_policy.py：关系端点归一；D的direct建议必须通过唯一目标、free_visible、无关系、足够置信度等门；E保留A已有blocker_first，歧义不再将其降级。
- execution.py：共享A最终reasoning及mask，保留历史失败状态，不重新请求仲裁；严格回放按provider/payload hash匹配，缺失报错；原图读取不加载GT/difficulty列；完整分割cache schema与哈希。
- runner.py：300案例零API回归CLI；build_plan和execute_plan共用真实执行边界。
- b1_backend.py：注入仓库get_prediction_result/parse_eghc_assessment的适配器，传入parquet原图及归一后路线，保留B1模型及分割设置。调用端负责明确配置模型客户端、预算和请求账本；本包CLI不会隐式构造付费客户端。
- collect_evidence：缓存模式明确prompt_hit=false；只有显式live_call实际调用新E提示才记录true。改变router证据的实验必须另立协议，不混入cached模式。

## 验证

```powershell
python -m unittest discover -s work/b1_v6_repair -p test_repair.py -v
```

服务器执行：

```bash
/home/public/zb/FreeGrasp_code-freegrasp_codex/.venv/bin/python -B runner.py \
  --source /home/public/zb/freegrasp_unograsp_fusion_20260922_v1/b1_v6_routing_split0_20260930_resume8_repaired \
  --repo /home/public/zb/FreeGrasp_code-freegrasp_codex \
  --output /home/public/zb/freegrasp_unograsp_fusion_20260922_v1/b1_v6_repair_20261002/validation_new
```

输出目录必须全新。validation中的derived_integrity.json涵盖1800个派生文件；它是本次读盘后的完整性快照，不能追溯证明此前未变。

## 运行边界

使用execute_plan(plan,cases,controls,images,backend=B1Backend(predict,parse))接入实际下游。未改路线跳过backend，直接复用A；改路线无backend则报ReplayMissing，不借旧D/E伪造新预测。实际下游需要独立配置有效批次预算/请求账本；本次未启动该阶段。

当前A明确命名为frozen repaired A（161/300、171/300），不冒充历史clean A（162/300、172/300）。历史6个ID差异仍作为已知源产物问题保留；共享控制修复防止它们在各臂重新变化。要恢复历史A，必须另建历史reasoning→原图mask的控制快照并全量验证，不允许直接改旧结果的一行分数。

新规则事后使用split0诊断制定，成功率改善仍需独立样本验证。单元测试和共享控制验证通过不等于科学效果通过。

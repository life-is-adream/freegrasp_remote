# 修复契约

DONE MEANS：关系schema归一、D直接抓取保护、E遮挡保护、共享A输出、严格离线回放、原图分割输入、mask完整性校验均实现，并通过mock及300行历史数据的零API验证；服务器保存版本和检查结果。

AUTHORIZED：用户“修好”（2026-10-02）；本地work/b1_v6_repair、outputs及服务器独立b1_v6_repair_20261002目录；只读既有B1/v6封存产物、冻结仓；CPU离线测试。

NOT AUTHORIZED：本修复不启动新付费批次，不改旧实验/冻结仓，不用split0事后结果宣称泛化收益，不读取v2/v3/v4。

ROUTE：实现→本地测试→服务器300行回归→报告。方法修正是新版本，不能续接旧D/E当作同一协议。

NOT DONE MEANS：只写建议、只测路由不测执行，或将历史baseline差异隐藏。

STOP FOR ME ONLY IF：缺少不可恢复的基线输入或需要超出授权的新付费/资源操作。

## 交付状态

实现完成：safe_policy、execution、runner、B1Backend和测试已保存服务器b1_v6_repair_20261002。11项单元测试本地/远端均通过。

真实数据验证完成：300案例，900个原图尺寸mask，1800个文件哈希，821个共享A控制预测逐字节检查通过，API=0/GPU=0。validation/validation.json保存结论及当时核心代码哈希；后追加B1Backend及测试不改变核心执行/路由代码。

方法验证未完成：修复后的D46/E33个变路线需要新预测；本次未启动。历史A基线不等价（6个ID差异）如实保留，新入口使用显式固定的repaired A作为共享控制，不声称恢复历史A。

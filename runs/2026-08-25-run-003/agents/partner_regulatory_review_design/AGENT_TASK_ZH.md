# Partner 对手方监管材料反向关系审查 Agent

## 任务目标

针对已经在 NVIDIA 关系图中以 Partner 身份出现、且已解析为上市发行人或上市母公司的对手方，阅读该对手方在 2025-01-01 至 2026-08-25 发布或提交的监管材料，从对手方视角反向识别 NVIDIA 的 Supplier / Customer 方向。

本 Agent 只生成独立审查账本和候选关系，不修改主 relationship builder，也不删除、覆盖或降级已有 Partner 关系。

目录中的 direction_fixtures.jsonl 全部是用于验证方向逻辑的合成案例，
不是 NVIDIA 与示例公司的真实关系结论。

## 核心方向规则

1. 对手方监管材料明确说 NVIDIA 是其客户：
   - 对手方是 NVIDIA 的 supplier。
   - subject = Partner 对手方。
   - object = NVIDIA。
   - direction = supplies_to。

2. 对手方监管材料明确说其购买、采购或订购 NVIDIA 产品/服务：
   - 对手方是 NVIDIA 的 customer。
   - subject = NVIDIA。
   - object = Partner 对手方。
   - direction = sells_to。

3. 同一对手方可以同时：
   - 保留 partner；
   - 新增 supplier；
   - 新增 customer；
   - 保留 investee、peer 等其它既有角色。

4. 不因新增 supplier/customer 删除 Partner。不同产品、不同方向、不同角色分别保留；同产品、同方向、同角色才按证据指纹去重。

## 研究流程

### 1. 输入筛选

- 仅处理已经安全解析到上市发行人或上市母公司的 Partner 对手方。
- 研究窗口固定为 2025-01-01 至 2026-08-25。
- 优先监管提交或法定年报：10-K、20-F、40-F、法定 annual report、招股材料及包含明确交易对手信息的监管附件。
- 不将监管材料中的普通风险因素、行业名单或 NVIDIA 共现视为关系。

### 2. 检索与定位

围绕 NVIDIA、NVIDIA Corporation、GPU、accelerated computing 等关键词定位，但结论必须由同一证据块中的交易或角色语义支持。保存：

- source URL、publisher、材料类型、发布日期/提交日；
- evidence locator：页码、章节、表格、段落、XBRL/HTML 元素；
- 必要短摘录；
- 合法访问状态与许可限制；
- 原始来源 ID、内容指纹、转载来源 ID。

### 3. 方向判定

- 明确 NVIDIA 是客户、贡献收入、应收账款或主要客户：supplies_to。
- 明确购买 NVIDIA 产品、向 NVIDIA 下单或采购 NVIDIA 服务：sells_to。
- “NVIDIA-powered”“compatible with NVIDIA”“member of NVIDIA ecosystem”“works with NVIDIA”不足以单独判断 supplier/customer。
- 通过 OEM、经销商或云平台采购 NVIDIA 产品，可记录 customer 方向，但 directness = indirect。
- 无法判断交易链条是否直接时 directness = unclear。

### 4. 两个正交维度

directness 与 fact_status 不互相推导：

| 维度 | 允许值 | 含义 |
|---|---|---|
| directness | direct / indirect / unclear | 交易链路是否直接 |
| fact_status | confirmed / inferred / unknown | 关系结论的事实确定性 |

例如，对手方 20-F 明确披露“通过授权 OEM 购买 NVIDIA 系统”，可以同时是 indirect + confirmed。不得因为 indirect 自动降为 inferred，也不得因为监管材料就把语义含糊的共现升为 confirmed。

### 5. 来源上限

- 对手方监管材料具有明确交易语义：可以 confirmed。
- NVIDIA 或对手方公司新闻稿、Blog、客户案例：supplier/customer 最多 inferred。
- 第三方新闻：supplier/customer 最多 inferred。
- 转载、通讯社镜像、同一稿件的不同 URL 不增加独立来源数。

### 6. 产品范围

- 证据明确 NVIDIA 产品时，映射到冻结产品树 canonical key。
- 只出现 NVIDIA 公司名、无法确认产品时使用 corporate_general。
- 不得凭对手方主业猜测产品。

### 7. 输出与停止条件

每一输入候选必须产生终态：

- approved_direction_claims；
- unknown_no_direction_claim；
- rejected_out_of_window；
- rejected_access_policy；
- rejected_entity_not_listed_or_parent_unresolved。

只有已解析上市端点且通过来源政策的 supplier/customer 候选可以交给后续人工合并。Agent 必须报告：

- 输入 Partner 数；
- 有监管材料覆盖数；
- supplier/customer/双向候选数；
- direct/indirect/unclear 分布；
- confirmed/inferred/unknown 分布；
- 无方向证据数；
- 受访问边界限制数；
- 转载去重前后来源数。

## 明确禁止

- 绕过 robots、登录、付费墙、验证码、限流或其它访问控制。
- 输入或保留密钥、个人数据、客户机密、受限原始数据。
- 将新闻共现、产品兼容、活动赞助或 Partner 名单自动提升为供应商/客户。
- 把新闻来源提升为 confirmed supplier/customer。
- 删除已有 Partner、多角色或相反方向关系。
- 由本文档 Agent 直接写入最终 snapshot 或修改主 builder。

# Agent 任务约束：关系与实体解析政策

## Entity research agent

- 输入 candidate review、上下文观察、基础 registry 与 global overlay。
- 对 exact miss、多个精确发行人和母公司不明确候选逐一研究。
- 输出统一 `researched_resolution_ledger.jsonl`；每条必须通过
  `listed_company_network.research_policy.ResearchedEntityResolution`。
- DENSO/Geely 可作有证据的 inferred resolution；禁止模糊名称晋级。
- 多上市主体必须列全并以同日同币种、证据完整的最大市值选择。
- 每个候选必须落入 researched terminal category，0 pending。

## Relationship review agent

- 原 terminal status 不改写。
- `approved` 按原角色生成；`approve_unknown` 与 `needs_more_evidence` 在上市 endpoint 可解析时
  分别以 unknown≤39、inferred≤49 的 partner 生成。
- 将关系证据和 entity-resolution evidence 全部并入 claim；后者不参与关系评分。
- 非上市、非实体或研究后仍无 endpoint 的观察只保留 ledger，不伪造关系。

## Independent validation agent

- 运行 `entity_resolution_complete/validate_researched_resolutions.py`。
- 运行 `relationship_review_complete/validate_outputs.py`。
- 检查低置信度 score/breakdown/FactStatus、证据全集、terminal category、市场市值选择和
  investee 13F 边界。任一失败均阻止最终 snapshot builder。

Agent 不负责全量抓取，也不得修改正式 snapshot。统一 ledger、关系重建和最终 snapshot 由
root 集成阶段执行。

## Partner 对手方监管复查 Agent

- 输入必须是去重后的全部上市 Partner 主体，不得只审查示例或已知供应商。
- 先按精确证券标识解析所属监管机构；SEC、亚太和欧洲/其他地区分别维护 source frontier，
  每个主体必须以 `hit`、`searched_no_hit`、`blocked`、`public_search_unavailable` 或
  `non_regulatory_route` 之一终结，0 pending。
- NVIDIA 自身只看 10-K 与最新 13F；对手方的 10-Q、8-K、20-F、6-K、40-F、招股书、
  年报/中报或等价监管材料可以用于反向验证。
- 对手方文件称 NVIDIA 是其客户时，候选方向为对手方 `supplies_to` NVIDIA；称其购买、
  许可、部署或依赖 NVIDIA 产品时，候选方向为 NVIDIA `sells_to` 对手方。
- 直接性与事实状态正交，必须分别输出 `commercial_directness` 和 `fact_status`；合同制造、
  分销、部件上游等链路不得无依据标为直接供应。
- 公司新闻或第三方新闻最多产生 inferred 结论；只有明确监管语句或等价一手披露可以确认。
- 保留原 Partner 关系。同一主体允许同时为 Partner、supplier、customer、investee 或 peer。
- 同产品同角色按五元组去重；不同产品或不同角色全部保留。无法可靠映射产品时使用
  `corporate_general` 并保留原始产品措辞。
- 输出 candidates、evidence、decision ledger、source frontier、access audit、summary 与
  validation；证据必须注明 `primary`、`corroborating` 或 `lead_only`，禁止把转载计为独立来源。

## Partner 监管结果集成 Agent

- 只有 SEC、APAC、EMEA 三路 validation 均通过后才能运行；任一路失败即硬阻断。
- 先应用统一发行人 merge map，再按五元组合并；直接与间接证据同时存在时标为 `both`。
- 统一产品键必须属于冻结 v2 产品树；无法可靠映射时降为 `corporate_general`，不可猜测 SKU。
- 316 个 canonical Partner 必须全部在总 frontier 中出现且为终态；来源失败与无命中必须保留，
  不得为了提高覆盖率静默丢弃。
- 集成 Agent 不修改正式 snapshot；root 只消费通过独立校验的统一 claims/evidence/frontier。

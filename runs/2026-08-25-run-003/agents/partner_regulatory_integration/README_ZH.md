# Partner 监管反向关系统一集成

## 结果

本目录统一合并 SEC、APAC 与 EMEA/英国/加拿大三组 Partner 对手方监管材料复查结果，研究窗口为 **2025-01-01 至 2026-08-25**。上游三组验证均通过后，合并器才会写出最终文件。

- 规范 Partner frontier：316 / 316，全部 terminal，pending 0。
- 上游来源 claim：48；按关系五元键合并后：48。
- canonical evidence：271。
- confirmed：22；inferred：26。
- customer：40；supplier：8。
- frontier 终态分布：`{"access_blocked": 7, "direction_claims_found": 44, "public_search_unavailable": 30, "regulatory_hit_no_approved_direction_claim": 99, "route_or_identifier_terminal_no_direction_claim": 2, "searched_no_direction_claim": 134}`。

## 规范化规则

关系按以下五元键合并，重复关系合并证据而不删除 Partner：

```text
subject_entity_id | object_entity_id | direction | relationship_type | product_scope_id
```

- 实体端点通过 `partner_regulatory_entity_normalization/entity_merge_map.jsonl` 统一为 canonical entity ID。
- SEC 读取 `claims.jsonl`；APAC 与 EMEA 读取 `candidates.jsonl` 的 `proposed_claim`。
- directness 的 `explicit` 规范为 `direct`；最终只允许 `direct / indirect / both / unclear`。同时存在直接和间接证据时为 `both`。
- 产品 scope 必须是冻结 `product_tree_v2/canonical_index_v2.jsonl` 中的 key；自由文本映射保留在 `original_product_scopes` 和 `product_scope_mappings`。混合或无法可靠匹配时为 `corporate_general`。
- 新闻、公司公告或第三方材料不能生成 confirmed。只有通过上游验证、且有监管材料支持的 confirmed 才保留。
- inferred supplier/customer 的置信分严格小于 60。
- 转载或相同 URL/日期/locator/短摘录按证据指纹合并，不增加独立来源。
- 独立性按不同 publisher 计算；同一申报中的重复 NVIDIA 上下文、同一 publisher 的多份
  文件或同一新闻转载均不增加 independence 分。重复上下文仍保留为 corroborating 证据。

## 文件

- `claims.jsonl`：统一五元键后的关系 claim。
- `evidence.jsonl`：所有 claim 引用的规范证据；仅保留结构化字段和必要短摘录。
- `source_frontier.jsonl`：316 个 canonical Partner 的组合终态及各工作流终态。
- `decision_ledger.jsonl`：316 个 Partner 的增量关系决策；Partner 角色始终保留。
- `summary.json`：合并统计、上游验证和限制。
- `validation_report.json`：输入门禁与最终一致性检查。
- `build_integration.py`：离线、确定性重建脚本。

## 复现

从本目录执行：

```bash
python3 build_integration.py
jq -e '.pass == true' validation_report.json
jq -s 'length == 316 and (map(.canonical_entity_id) | unique | length == 316)' source_frontier.jsonl
jq -s 'all(.fact_status != "inferred" or .confidence_score < 60)' claims.jsonl
```

## 限制与合法边界

- 本集成器不联网，只读取冻结上游成果；未重新抓取或绕过 robots、登录、付费墙、验证码、限流等访问控制。
- `searched_no_direction_claim` 不证明现实中不存在交易关系。
- `route_or_identifier_terminal_no_direction_claim` 表示上游已给出终态，但没有可合并方向 claim；不应解释为完成了所有可能的当地语言全文检索。
- 本集成器本身不直接修改主 relationship builder 或最终 snapshot；root builder 只在本目录
  validation 通过后消费这些增量 claims。正式快照中的结论仍需提交者最终负责，不构成投资建议。

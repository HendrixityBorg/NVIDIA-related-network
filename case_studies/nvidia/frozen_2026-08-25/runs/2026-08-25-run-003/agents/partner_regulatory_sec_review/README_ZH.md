# Partner 监管文件 NVIDIA 命中上下文方向审查

研究截点：**2026-08-25**。本目录只审查冻结 SEC corpus，不联网、不重新采集，也不修改主 builder 或最终 snapshot。

输入：

- `agents/partner_regulatory_review/filing_documents.jsonl`
- `agents/partner_regulatory_review/mention_contexts.jsonl`
- `agents/partner_regulatory_review/source_frontier.jsonl`
- `agents/partner_regulatory_review/collection_summary.json`
- `agents/partner_regulatory_entity_normalization/entity_merge_map.jsonl`

最终冻结 collection 包含 316 个 canonical Partner 主体，其中 170 个有 CIK；470/470 份文件成功获取，形成 1,973 条 NVIDIA 命中上下文、89 个命中主体。另有 81 个主体完成 SEC 检索但无 NVIDIA 命中，146 个主体需要非 SEC 路由。338 份文档按内容指纹复用；`access_control_bypass=false`。

## 审查政策

- `supplier confirmed`：监管原文必须明确 Partner 向 NVIDIA 提供产品/服务，且 NVIDIA 是客户、付款方或收入来源。方向为 `Partner -> NVIDIA / supplies_to`。
- `customer confirmed`：必须明确 Partner 从 NVIDIA 采购，或明确称 NVIDIA 为其供应商/卖方。方向为 `NVIDIA -> Partner / sells_to`。
- `customer inferred`：只在原文明示 Partner 购买、持有、使用、测试或部署 NVIDIA 产品，但直接卖方/采购对手方不明时生成；`directness=unclear`，置信度 56、上限低于 60。
- 仅风险、竞争、兼容、媒体联系人、技术参考、合作、股权投资或新闻共现不得新增商业方向。

`rules_fixture.json` 是人工审阅后的精确规则：大小写不敏感的 literal phrase 与指定 canonical entity 双重约束，规则按顺序执行，不使用模糊匹配或语义扩展。全部 1,973 条上下文均有终态；未通过方向门的上下文仍保留 excerpt、locator、URL 和拒绝原因。

## 最终结果

逐上下文审查形成 254 个 approved candidates、1,719 个 rejected non-directional decisions、0 pending。按 `canonical entity + relationship type + 单一 product scope` 合并后有 31 条 claim：

| 关系状态 | Claim 数 | 唯一关联主体数 | Directness |
|---|---:|---:|---|
| supplier confirmed | 8 | 7 | explicit |
| customer confirmed | 9 | 9 | explicit |
| customer inferred | 14 | 14 | unclear |

Supplier confirmed 主体为 Coherent、CoreWeave、IREN、Fabrinet、Lumentum、SK hynix、TSMC。CoreWeave 在 `cloud-services` 与 `corporate_general` 两个不同产品 scope 各保留一条 supplier claim，因此 claim 数比唯一主体数多一条。

Customer confirmed 主体为 Bitdeer、CoreWeave、HP、HPE、Ingram Micro、IREN、Nebius、Oracle、Supermicro。Customer inferred 主体为 Akamai、Aurora、Cognizant、DigitalOcean、Infleqtion、Li Auto、Nokia、One Stop Systems、Ouster、Polestar、Pony.ai、QumulusAI、TELUS、WeRide。

关键复核：

- CoreWeave 为双向 confirmed：其向 NVIDIA 提供基础设施/云容量，同时 filing 明确 NVIDIA 向 CoreWeave 供应 GPU；两个方向分别引用各自合同或供应原文。
- IREN 为双向 confirmed：约 34 亿美元五年期 GPU cloud services 合同支持 `IREN -> NVIDIA`，另有将 NVIDIA 列为数据中心设备供应商的原文支持反向关系。
- Fabrinet 的 supplier claim 保留 NVIDIA 占其收入 35.1%（FY2024）、27.6%（FY2025）和 16.3%（FY2026）的量化证据。
- Bitdeer 明确披露从 NVIDIA Corporation 采购约 1,320 万美元 DGX/HGX 设备，因而为 customer confirmed；后续只披露“某些供应商”的订单不会单独升级 directness。
- Corning 的媒体联系人/合作稿、Marvell 的技术合作、CoreWeave 对 NVIDIA 上游供应风险、Arm 平台依赖、Magna 合作和 Applied Digital 股权共现均未产生错误商业方向。

## 输出

- `candidates.jsonl` / `relationship_candidates.jsonl`：内容相同，通过保守方向门的逐上下文候选。
- `claims.jsonl` / `relationship_claims.jsonl`：内容相同，按 canonical entity、关系类型、单一 product scope 合并。
- `evidence.jsonl`：1,973 条 SEC 上下文证据，含 excerpt、locator、URL、publisher、form、filing date、accession、获取时间、访问/再分发说明和内容 SHA-256。
- `decision_ledger.jsonl`：1,973 条终态决策，0 pending。
- `source_frontier.jsonl`：316 个 canonical 主体，保留原 entity IDs、CIK、地区、查询和冻结 collection 状态；分布为 89 reviewed hit、81 searched no hit、146 non-SEC route。
- `summary.json`、`validation_report.json`：精确计数和独立 QA。

## 复现与测试

无需网络或凭据：

```bash
python3 build_review.py
python3 validate.py
python3 -m unittest -v test_review.py
```

构建器先检查 `collection_summary.retrieved_documents > 0`。验证器另有冻结门 `470 documents / 1,973 contexts`，并检查：每条上下文恰有一个终态 decision 和一条 evidence、0 pending、canonical entity/product scope 闭合、claim key 唯一、证据和候选引用闭合、方向/directness/置信度规则、Fabrinet 百分比、CoreWeave/IREN 双向事实、Bitdeer 直接采购，以及媒体/合作/风险误判。11 个单元测试包含 collection 为零时的 fail-closed 边界。

## 限制

- NVIDIA 词项窗口可能让同一监管段落产生多个重叠 context；claim 层合并这些 evidence IDs，不把重复窗口当成独立来源。
- SEC filing 中出现的 8-K 新闻稿仍属于发行人提交材料，但只有精确合同、客户、收入或供应措辞能通过方向门；媒体、免责声明和前瞻陈述本身不能通过。
- “使用 NVIDIA 品牌产品”不能证明直接向 NVIDIA 采购，可能经 OEM、分销商或合作方取得，因此统一保留为 inferred/unclear。
- 146 个 `non_sec_route_required` 主体不在本目录的监管文件方向覆盖内，应由相应司法辖区的官方监管材料路线补充。

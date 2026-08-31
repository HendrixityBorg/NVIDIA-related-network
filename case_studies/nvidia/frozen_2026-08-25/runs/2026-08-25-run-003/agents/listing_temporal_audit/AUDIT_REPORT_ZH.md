# 上市主体时点审计报告（截至 2026-08-25）

## 结论

本轮独立审计以 NPN `reviewed_mappings.json`、全局上市 overlay、2025/2026 NVIDIA 官方文章实体提及为范围，重点检查已退市/被收购发行人、品牌或子公司误作发行人、ticker/exchange 错误，以及“实体已匹配但上市证券字段为空”的伪完成记录。

共形成 19 条机器可读审计决定：13 条修正已由上游任务落盘并经二次复核通过，4 条在最终集成输出中完成 issuer/ticker hydration 验证，2 条高风险映射确认无需修改。`pending_merge=0`，审计状态为 `pass`。

## 已落盘并复核通过

- `EXAION (EDF GROUP)`：已撤销 EDF/EDF.PA active listed parent。EDF 于 2023-06-08 从 Euronext Paris 退市，法国国家持有全部股本和表决权；截至 cutoff 不存在上市母公司端点。
- `NTT DATA` 系列：保留上市母公司 9432，但发行人法定英文名已改为 `NTT, Inc.`。NTT DATA 自身 9613 已退市，不能再作为 active issuer。
- `SCSK Corporation`：9719 于 2026-03-12 退市；active endpoint 已改为母公司 Sumitomo Corporation / TSE 8053。
- `Okaya Electronics Corp.`：已撤销与 Okaya Electric Industries / 6926 的同名误匹配；官网明确其 100% 母公司为 Okaya & Co., Ltd. / Nagoya 7485。
- `Nebius B.V.`：已从 direct issuer 改为 Nebius Group N.V. / Nasdaq NBIS 的运营子公司。
- `Atea A/S`、`Atea AS`：已从 direct issuer 改为 Atea ASA / Oslo ATEA 的国家运营子公司。
- `Tatung System Technologies`：交易所已从 TWSE 改为 Taipei Exchange，ticker 8099 不变，vendor symbol 为 `8099.TWO`。
- `Ingram Micro Inc`、`PC Partner Technology Pte`、`Proact IT Sweden`、`Macnica Inc`、`Ryoyo Ryosan`：均已把 `resolution_kind` 从 direct issuer 改为 `subsidiary_to_parent`，上市 endpoint 本身保留。

## 集成后闭合

- `Altair`：已在 `non_npn_listing_audit/researched_resolution_ledger.jsonl` 的 canonical ledger 中闭合为 `resolved_inferred_parent → siemens_ag`。Siemens 于 2025-03-26 完成收购，ALTR 当日停止交易并申请移除上市；active endpoint 为 Siemens AG / Xetra SIE，ALTR 仅保留 historical inactive security。

二次验收特别检查了 F5、Infosys、Supermicro、Wipro：虽然 seed `reviewed_mappings.json` 仅保存 upstream entity ID，但最终 `resolved_parent_mappings.jsonl` 已分别带出 FFIV、INFY、SMCI、WIT 及 `active_at_cutoff`，因此不属于“表面完成、实际未识别”。

## 高风险映射确认

- `Ansys`：当前 global overlay 正确。Synopsys 于 2025-07-17 完成收购，ANSS 已通过 Nasdaq Form 25-NSE 移除；保持 historical entity，active endpoint 为 Synopsys。
- `VMware Inc`：当前 NPN 映射正确。VMware 已于 2023-11-22 被 Broadcom 收购；应保留 `brand_to_parent → Broadcom / AVGO`。
- `Red Hat`：当前 global overlay 已正确映射到 IBM，不需新增修正。
- `Juniper Networks`：当前官方文章 entity mention 文件未发现目标记录；若后续出现，应按 HPE 2025-07-02 完成收购处理为 HPE / NYSE HPE，不得恢复 JNPR active security。

## 多上市主体与证券选择

本轮没有发现需要在两个不同上市母公司之间按市值重新择大的已落盘目标。Infosys/Wipro 的印度普通股与美国 ADS 属于同一发行人不同证券，并非多个上市母公司；为与现有美国 registry endpoint 一致，overlay 使用 INFY 与 WIT。DENSO、Geely 继续按当前最可能主体计算，未发现时点性退市错误。

## 可直接合并文件

- `entity_registry_overlay.jsonl`：10 条幂等 overlay，均已作为上游落盘或最终集成输出的复核断言。
- `decision_ledger.jsonl`：每个输入名的终态与实体决定。
- `listing_evidence.jsonl`：一手来源、日期与 locator。
- `corrections.jsonl`：完整审计记录，含目标、旧映射、动作、正确实体/证券、来源和原因。
- `validation_report.json`：结构与交叉引用验证结果。

## 剩余风险

- `official_articles_2025/2026/entity_mentions.jsonl` 的原始行仍大量保留 `listing_status=unresolved`；必须由 alias/overlay 消费层完成解析，不能把原始 mention 文件的 `unresolved` 误当最终上市状态。
- Yahoo symbol 只能作为 vendor code，不能单独证明交易所或 active-at-cutoff。最终证券状态应以发行人 IR、交易所或监管披露为准。
- 对后续新增 overlay，应继续执行：先判断输入名是发行人、品牌还是子公司；再核验 cutoff 前的收购/退市；若确有多个不同上市母公司，才按 cutoff 附近市值选择最大者并保留比较证据。

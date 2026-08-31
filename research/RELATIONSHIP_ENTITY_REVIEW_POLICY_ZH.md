# 关系低置信度纳入与实体研究闭环政策

本政策用于最终关系审阅和上市母公司解析，研究截点仍为 2026-08-25。
它不改变原始观察，也不把弱证据包装成已确认事实。

## 1. `approve_unknown` 与 `needs_more_evidence`

两类 terminal decision 都保留原状态，并在主体已解析为截点仍上市的发行人时生成
`partner / partners_with` 关系：

| 原 terminal status | claim `fact_status` | 最高分 | 解释 |
|---|---|---:|---|
| `approve_unknown` | `unknown` | 39 | 仅表示弱共现、Logo、入口、标题或未分类生态联系 |
| `needs_more_evidence` | `inferred` | 49 | 有关系线索，但明确性、方向、主体或交叉验证仍不足 |

精确发行人合并后，同一五元键可能同时包含两类原终态。此时必须保留两类
`origin_terminal_statuses`；若合并语义仍为 unknown 则继续使用 39 上限，若额外的
`needs_more_evidence` 观察使其达到 inferred 则使用 49 上限。不得因简单“取最高分”丢失
任何原始终态或证据。

claim 必须保留 `origin_terminal_statuses`、逐条 `inference_explanations` 和所有关系证据。
同键合并时，不得只保留分数最高的一条信源。身份解析证据也必须物化为
`source_family=entity_resolution` 的 evidence，并进入 claim 的 `evidence_ids`；但身份
证据不能增加关系独立性、关系明确性或关系来源数量。

如果主体经完整研究后属于私营、退市、非实体或仍无法对应任何上市发行人，则不能为了
生成边而虚构 endpoint。该观察仍保留 terminal decision、研究类别和全部证据，但不进入
上市公司关系图。

Logo、anchor、GitHub/商店入口、blocked 文章标题和投资措辞仍受到原语义限制。它们最多
生成上述低置信度 partner；不能自动成为 supplier、customer、investee 或 confirmed
partner。13F 仍是 investee 的唯一来源。

## 2. 上市母公司研究闭环

`exact alias miss` 只是搜索结果，不是完成状态。需要解析上市母公司的候选必须写入统一
`researched_resolution_ledger.jsonl`，并选择以下一个 researched terminal category：

- `resolved_exact`
- `resolved_inferred_parent`
- `resolved_largest_listed_parent`
- `unresolved_after_research`
- `ambiguous_after_research`
- `non_entity`
- `private_or_delisted`

每条记录必须包含研究方法、官方或权威公开证据 URL、publisher、retrieved time、locator、
supports、研究理由，以及被覆盖的 candidate/observation IDs。


如果一个观察可合理对应多个上市主体，必须使用 `resolved_largest_listed_parent`：列全候选、
证券标识、与观察名的关系，并在同一 as-of、同一币种下提供每个候选的市值及各自 evidence。
validator 只接受有证据的最大值主体；缺值、币种不同、日期不同或选择非最大主体均失败。

## 3. 评分和验收

低置信度 claim 的 `confidence_score` 必须等于
`min(ScoreBreakdown 各分项之和, terminal status 上限)`。`approve_unknown` 同时受 unknown
39 分上限约束；`needs_more_evidence` 使用 inferred，但本政策进一步限制为 49 分。
身份推断将 entity-resolution 分项从 15 降为 10。

发布 gate 必须验证：

1. 每个 exact/ambiguous issuer 候选有 researched terminal record；
2. 多上市主体选择满足同日同币种、全候选有市值证据、选择最大主体；
3. 所有可形成上市 endpoint 的两类低置信度 decision 都生成 partner key；
4. 原 terminal status、推断说明、关系证据和身份解析证据全部保留；
5. 身份证据不计入关系独立性或明确性；
6. `reject` 不生成 claim，investee 仍仅来自最新 13F；
7. claim 分数、breakdown、FactStatus 和 39/49 上限一致。

实现入口为 `src/listed_company_network/research_policy.py`、关系 builder/validator，以及
`entity_resolution_complete/validate_researched_resolutions.py`。最终统一 ledger 尚未生成时，
release validator 应 fail-closed，而不是沿用 exact-alias miss 作为“已完成”。
实体 validator 通过后会写出
`entity_resolution_complete/researched_resolution_validation_report.json`，供 root final
builder 作为强制 gate；该报告不存在或 `pass=false` 时不得发布。

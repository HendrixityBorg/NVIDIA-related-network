# 数据契约

## 1. 输入候选 PartnerRegulatoryCandidate

必填字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| candidate_id | string | 稳定候选 ID |
| partner_entity_id | string | 已解析上市发行人/母公司 ID |
| partner_legal_name | string | 法定名称 |
| existing_roles | string[] | 必须保留的既有角色，至少含 partner |
| signals | enum[] | nvidia_is_customer / partner_purchases_nvidia / unclear |
| directness | enum | direct / indirect / unclear |
| product_scope_id | string/null | 缺失时规范为 corporate_general |
| source | object | 单条证据来源 |

source 必填字段：

| 字段 | 说明 |
|---|---|
| source_kind | regulatory_filing / company_news / third_party_news |
| form_type | 监管材料类型；非监管来源可为空 |
| url | canonical source URL |
| publisher | 原始发布者 |
| published_at | ISO 日期/时间，必须落在研究窗口 |
| evidence_locator | 页码、章节、段落、表格或元素定位 |
| evidence_excerpt | 必要短摘录，不保存全文 |
| access_mode | 必须为 public_no_login |
| access_control_bypassed | 必须为 false |
| origin_publication_id | 原始稿件/提交稳定 ID，用于转载去重 |
| origin_content_fingerprint | 可选，原始内容指纹 |

## 2. 输出 ReviewDecision

| 字段 | 类型 | 说明 |
|---|---|---|
| decision_id | string | 稳定审查 ID |
| candidate_id | string | 输入候选 ID |
| review_status | enum | approved_direction_claims / unknown_no_direction_claim 等 |
| partner_entity_id | string | 对手方端点 |
| existing_roles_retained | string[] | 必须包含 partner，不删除其它角色 |
| new_claims | DirectionClaim[] | 0、1 或 2 条方向关系 |
| unknown_reason | string/null | 无新关系时必填 |
| multi_role_policy | string | 明示增量、多方向、多角色策略 |

## 3. DirectionClaim

| 字段 | 类型 | 约束 |
|---|---|---|
| claim_id | string | 对 candidate/signal/product/evidence 稳定散列 |
| subject_entity_id | string | supplier 为 Partner；customer 为 NVIDIA |
| object_entity_id | string | supplier 为 NVIDIA；customer 为 Partner |
| direction | enum | supplies_to / sells_to |
| relationship_type | enum | supplier / customer |
| fact_status | enum | confirmed / inferred / unknown |
| directness | enum | direct / indirect / unclear |
| product_scope_id | string | 缺失产品用 corporate_general |
| source_kind | enum | 来源种类 |
| source_url | URL | 原始或监管来源 |
| publisher | string | 发布者 |
| published_at | ISO date/time | 研究窗口内 |
| evidence_locator | string | 可复核定位 |
| evidence_excerpt | string | 必要短摘录 |
| source_cap_applied | string | 事实状态上限说明 |
| direction_rationale | string | 从对手方视角解释方向 |

## 4. 正交性约束

- directness 只描述交易链：direct、indirect、unclear。
- fact_status 只描述证据确定性：confirmed、inferred、unknown。
- 任意 directness 可与任意 fact_status 组合；是否允许由实际证据决定。
- regulatory_filing + 明确角色语义可以 confirmed。
- company_news 或 third_party_news 无论语气多明确，supplier/customer 均不得超过 inferred。

## 5. 去重与合并键

关系语义去重键：

    subject_entity_id | object_entity_id | direction |
    relationship_type | product_scope_id

证据指纹：

    canonical_url | publisher | published_at | evidence_locator |
    normalized_excerpt_hash

独立来源键优先使用 origin_publication_id，其次
origin_content_fingerprint。转载、镜像、聚合页面共享同一个 origin key，只计
一个独立来源。

同一公司可同时存在：

- partner；
- partner + supplier；
- partner + customer；
- partner + supplier + customer；
- 上述角色再叠加 investee / peer。

不得用公司级去重删除不同产品或不同方向的合法关系。

## 6. 失败响应

实现应提供明确错误码：

| 错误码 | 场景 |
|---|---|
| invalid_input | 缺字段、枚举非法、日期格式非法 |
| out_of_research_window | 不在 2025-01-01..2026-08-25 |
| prohibited_access | 非公开、需登录或发生访问控制绕过 |
| unresolved_listed_endpoint | 对手方没有安全上市端点 |
| insufficient_direction_evidence | 只有共现/生态/兼容表述 |

失败不等于删除 Partner；它只阻止新增 supplier/customer。

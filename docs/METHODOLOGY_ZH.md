# 通用研究方法与数据契约

## 1. 交付对象

研究单元不是摘要，而是 `Entity → Relationship → Evidence → Source` 的可追溯链。`profile` 冻结目标身份和范围；`run` 保存发现、处理、终态及 QA；`snapshot` 只包含通过发布门槛的规范化对象。

最终数据采用五类关系，并明确 source/target、方向、产品节点、事实状态、时间状态、置信度、相关度、证据角色、推断解释、冲突和限制。同一主体在相同关系、方向和产品上合并重复观察，在不同产品或不同关系上分别保留。

## 2. 来源矩阵

| 来源族 | 默认要求 | 作用 | 主要风险 |
|---|---|---|---|
| annual_filing | required | 目标公司最近年报 | 披露集中度但常不点名 |
| portfolio_filing | if_applicable | 目标公司公开上市持仓 | 申报主体或证券范围误解 |
| investor_presentations | required，近两年 | 路演、GTC/大会、架构与 Logo | Logo 不等于商业方向 |
| official_articles | required，近两年 | 新闻、博客、客户案例 | 官方营销表述与过期合作 |
| product_solutions | required | 完整产品/解决方案树和页面生态 | 站点层级与别名重复 |
| ecosystem_directory | optional | partner type、competency、program | 地区主体重复，通常无供需方向 |
| third_party_news | required，近两年 | 独立线索和冲突信息 | 转载、摘要、共现误判 |
| counterparty_regulatory | required | 对全部上市对手方反向验证 | 未披露不代表不存在 |
| peer_research | required | 产品大类自研竞争者 | 把渠道商错当竞争者 |

每个来源族必须提交 `StageReport`。required 默认只能以 `complete` 通过；optional 可为完整、明确检索后未找到或不适用；if_applicable 可为完整或不适用。受阻不能伪装完成，是否允许受阻状态必须在 profile 显式修改。

## 3. 证据接受

来源发现与关系证据是两套判断。搜索结果、标题、Logo、页面共现和合作目录是候选；只有能够定位到关系语义的正文、表格、图片说明或官方标签才可成为 primary/corroborating evidence。Logo 在产品章节且上下文明确时可推断产品关联；只在封面、架构图、赞助区或无标题页面时降为低置信度；与产品无关则 unknown。

监管文件或明确官方公告可支持 confirmed。公司产品页、客户案例和双方公告可在语义明确时确认 partner/customer 等关系。仅公司新闻或第三方原始报道通常只支持 inferred supplier/customer；第三方新闻单独不能产生 confirmed。搜索摘要和转载聚合只作 lead_only。

## 4. 实体解析

实体解析必须说明提及主体、法律实体、上市证券、上市地区、截点上市状态和最终母公司。地区分支、事业部和品牌先聚成集团，再映射上市母公司；原始名称不丢失。若存在多个上市主体，选择与该业务关系匹配的控制主体；仍无法确定时记录歧义，不能只按市值静默猜测。

实体身份的证据与关系语义证据分别保存在 `entity_resolution_evidence_ids` 和 `relationship_evidence_ids`，二者都可在 API 一跳查看，但只有后者影响关系判断。

## 5. 反向监管检查

关系候选完成实体归一后，系统对关系图中每一家上市对手方生成 `CounterpartyReviewTask`。检索其监管数据库、最近年报和 IR，使用目标公司法律名、品牌名、历史别名及相关产品词。每个任务必须以 confirmed、direction unknown、not relationship、no exact mention、filings unavailable、no filings in window、identity ambiguous 或 manual review required 等终态结束。

`no_exact_mention` 不是拒绝已有关系，只表示不能用对手方材料增强它。对手方年报若明确称目标为客户/供应商，可升级关系；对手方公司新闻或媒体报道不足以单独标 confirmed。

## 6. 评分

置信度分解为来源权威性 0–25、语义明确性 0–25、实体解析 0–15、独立性 0–15、时效 0–10、量化信息 0–10、关系类型特异性 0–5，另减冲突惩罚 0–20，最后限制在 0–100。为防止伪精确，状态还有硬上限：inferred 69、unknown 39，inferred supplier/customer 59，保留的低置信度 partner 最高 49/39。

相关度独立回答“该关系对理解目标公司业务是否重要”，由产品核心度、关系规模、战略性、重复观察和可量化占比解释，不应因为来源权威就自动提高。

## 7. 动态验收

validator 不依赖某一家公司的固定数量，而从 profile 和实际实体图生成预期：

- 每个来源族有 profile 允许的终态，且 pending 为 0；
- 目标和对手方实体、来源、证据、关系 ID 唯一且引用闭合；
- 每条关系方向、产品和事实状态符合契约，时间不越过截点；
- semantic evidence 不得全为 lead_only；新闻单独不能确认；
- 最终上市对手方集合与反向任务集合相等，每个任务有终态；
- 任何错误都会使 `release_ready=false`，构建器拒绝输出快照。

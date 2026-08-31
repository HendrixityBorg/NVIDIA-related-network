# 上市公司关联上市合作主体研究Agent

本项目用于在投研过程中梳理目标上市公司的产业链上市合作伙伴，通过构建包括上市公司监管材料、公司投资者文件、公司官网、公司blog/news、公司合作伙伴生态网络以及第三方信息源的完整数据源，完整梳理官方承认的合作方。我们会为每个数据源配备相应的数据抓取和整理agent，收集数据并按照一定的置信度设置最终获得完整且可查的合作伙伴关系网络。本次存档以英伟达为例。

> 本项目不保证覆盖NVIDIA公司的全部商业关系。

## 研究对象、实体与截点

- 研究对象：NVIDIA Corporation
- 上市证券：Nasdaq `NVDA`
- SEC CIK：`0001045810`
- 证券 CUSIP：`67066G104`
- 研究截点：`2026-08-25 23:59:59 +08:00`
- 新闻、文件和网页证据窗口：最早追溯到 `2025-01-01`
- 最新 13F 报告期：`2026-06-30`，申报日 `2026-08-14`
- 冻结快照：[data/snapshot_2026-08-25.json](data/snapshot_2026-08-25.json)
- 完整研究运行：[runs/2026-08-25-run-003](runs/2026-08-25-run-003)


上市地区与发行人注册地分开建模。每条证券记录包含由实际交易所确定的
`listing_region` 和 ISO 两位 `listing_region_code`；实体级 `listing_regions` 汇总该实体
在本快照证券标识中覆盖的全部挂牌地区。ADR、GDR 和 OTC 按证券实际交易市场标注，
不据此推断公司的注册地或总部所在地。

## 覆盖范围与冻结门槛

最终 run 只有在下表全部通过时才可生成 v2 snapshot；

| 数据族 | 冻结范围 | 完成标准 |
|---|---|---|
| 产品与解决方案 | 根据英伟达官网的主要产品站点以及7 个指定行业二级业务站点及边界内产品/solution 章节 | 623 canonical objects、797 observations、0 pending |
| NVIDIA Newsroom | 2025-01-01 至截点全部条目 | 168/168 ledger terminal |
| NVIDIA Blog | 2025-01-01 至截点全部条目 | 597/597 ledger terminal；正文或明确 blocked/recovery 状态 |
| Newsroom + Blog | 两站去重后的官方文章全集 | 765 canonical articles、0 pending |
| NVIDIA Partner Network | 截点公开合作伙伴页面运行时总量 | 最终冻结 23 页、997/997 raw cards、标签无损、997 个唯一 raw observation IDs；同日早先 996 条观测作为已解释的时点漂移保留 |
| Partner 对手方监管复查 | 去重后的 316 家上市 Partner；SEC、APAC、EMEA/英国/加拿大公开监管及发行人材料 | 316/316 frontier terminal、0 pending；48 条方向关系、271 条规范证据；三路及统一集成 validation 全部通过 |
| 投资者关系文件 | 最新 10-K、最新非修订 13F、2025 年 1 月以来的 6 份 GTC 大会演示 | 21/21 source/page gates 通过 |
| 上市实体 | 美国及非美官方上市身份 | exact aliases only、所有候选 terminal |
| Peer | 8 个产品大类 | 每类有 accepted 或明确 0 的决定；21 条 accepted |
| 最终关系 | supplier/customer/partner/investee/peer | 唯一 v2 key、证据引用完整、分数合法、0 pending |

正式 v2 快照包含 **329 个实际关系端点、5,753 个来源、9,458 条证据和 2,016 条关系**。
329 个实体全部实际出现在关系边上，即 NVIDIA 本身加 **328 家关联上市公司**，不再把
“已完成证券解析但没有关系”的 registry-only 候选计入公司总数。关系分布为 supplier 16、
customer 180、partner 1,792、investee 7、peer 21；状态分布为 confirmed 719、inferred 757、
unknown 540。其中 973 条是由原 `approve_unknown` 或 `needs_more_evidence` 决定保守纳入的
低置信度 Partner（unknown 540、inferred 433），均保留原始状态、关系证据与实体解析证据。
Partner 反向复查新增 48 条可追溯商业关系：customer 40、supplier 8；confirmed 22、
inferred 26；直接 22、间接 1、方向路径不明 25。13 个重复上市端点已按精确证券标识合并。
Blog 正文覆盖 558/597，另 39 篇为有完整访问审计的 terminal blocked；其标题或索引共现
最多只能形成 unknown Partner，不能升级为已确认商业关系。所有强制数据族在
[v2 coverage frontier](data/coverage_frontier_2026-08-25.json) 中均为 `pass` 且 `pending=0`。

冻结后的最终统计由 `scripts/validate_snapshot.py` 输出。`completion_gates.json` 是便于
人工阅读的汇总；`scripts/build_snapshot_v2.py` 直接核对各数据族 validation report，
任一强制门槛未通过时会 fail-closed，不会生成“完成版”。
[v2 coverage frontier](data/coverage_frontier_2026-08-25.json) 只汇总这些冻结报告，
不伪造最终 source IDs；正式 builder 会与 snapshot 一起确定性重写它。

## 明确不覆盖

- 私营公司端点和未披露名称的客户；
- 登录、付费墙、验证码、robots 禁止、限流或其它访问控制后的内容；
- 13F 未覆盖的私募、债权、海外非 13F 证券、实时头寸或战略意图；
- 将 Logo 共现、新闻同段出现或 NPN 会员身份自动解释成交易；
- 对每个 SKU 都寻找 peer；peer 只按 8 个产品大类研究；
- 二阶供应链穿透、收入预测、估值和投资建议。

## 数据来源与采集顺序

关系研究按以下优先级展开：投资者关系/监管文件、发行人投资者材料、官方产品/solution 页面、
官方 Newsroom/Blog/customer story、官方 Partner Network、权威独立报道、补充发现报道材料，以及关联方上市公司文件。
来源权威性不会替代关系语义：封面 Logo 仍然弱于明确的 Customers 标题。

核心一手来源示例包括：

- [NVIDIA FY2026 10-K](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm)
- [NVIDIA 2026-06-30 Form 13F information table](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000065/xslForm13F_X02/information_table.xml)
- [NVIDIA Newsroom](https://nvidianews.nvidia.com/)
- [NVIDIA Blog](https://blogs.nvidia.com/)
- [NVIDIA Partner Network Locator](https://marketplace.nvidia.com/en-us/enterprise/partners/)
- [NVIDIA Data Center](https://www.nvidia.com/en-us/data-center/)
- [NVIDIA Robotics](https://www.nvidia.com/en-us/industries/robotics/)
- [NVIDIA Networking](https://www.nvidia.com/en-us/networking/)
- [NVIDIA HPC](https://www.nvidia.com/en-us/high-performance-computing/)
- [NVIDIA AI](https://www.nvidia.com/en-us/solutions/ai/)
- [NVIDIA Autonomous Vehicles](https://www.nvidia.com/en-us/solutions/autonomous-vehicles/)
- [NVIDIA Design and Simulation](https://www.nvidia.com/en-us/solutions/design-and-simulation/)

仓库不复制完整第三方网页、Blog 正文、PDF 或媒体文件。它冻结结构化事实、短摘录、
URL、publisher、发布时间/获取时间、页码或区块 locator、访问限制和 SHA-256。
reviewer 运行 API 或理解结论时不需要重新抓取受限数据。
代码使用 MIT 许可证；第三方来源权利与结构化数据再使用边界见
[DATA_NOTICE.md](DATA_NOTICE.md)，MIT 不会重新许可第三方网页、商标、Logo、PDF 或媒体。

Reviewer 可直接审阅以下冻结产物，无需重新访问原站点：

- [完整产品树](runs/2026-08-25-run-003/product_tree_v2/PRODUCT_TREE_V2.md)及其[验证报告](runs/2026-08-25-run-003/product_tree_v2/validation_report.json)；
- [文章正文恢复说明](runs/2026-08-25-run-003/agents/article_body_recovery/README.md)及其[验证报告](runs/2026-08-25-run-003/agents/article_body_recovery/validation_report.json)；
- [NPN 后处理说明](runs/2026-08-25-run-003/agents/npn_runtime_complete/README.md)、[分页验证报告](runs/2026-08-25-run-003/agents/npn_runtime_complete/validation_report.json)和[集团验证报告](runs/2026-08-25-run-003/agents/npn_runtime_complete/group_validation_report.json)；
- [关系审阅 decision ledger](runs/2026-08-25-run-003/agents/relationship_review_complete/decision_ledger.jsonl)及其[验证报告](runs/2026-08-25-run-003/agents/relationship_review_complete/validation_report.json)。
- [Partner 监管反向复查统一结果](runs/2026-08-25-run-003/agents/partner_regulatory_integration/README_ZH.md)、[316 主体 frontier](runs/2026-08-25-run-003/agents/partner_regulatory_integration/source_frontier.jsonl)及其[验证报告](runs/2026-08-25-run-003/agents/partner_regulatory_integration/validation_report.json)。
- [交付级审计](runs/2026-08-25-run-003/delivery_review/README_ZH.md)、[全部 Supplier 审计账本](runs/2026-08-25-run-003/delivery_review/supplier_audit.jsonl)及其[确定性报告](runs/2026-08-25-run-003/delivery_review/delivery_audit_report.json)。

## 关系、方向与重复处理

| 类型 | 存储方向 | 可证明的最小含义 |
|---|---|---|
| `supplier` | 供应商 `supplies_to` NVIDIA | 对方向 NVIDIA 提供产品、组件或服务 |
| `customer` | NVIDIA `sells_to` 对方 | 对方是明确客户/采用者；仅部署时会写限制 |
| `partner` | NVIDIA `partners_with` 对方 | 联合生态、渠道、集成或项目；不默认买卖方向 |
| `investor_or_investee` | NVIDIA `invests_in` 发行人 | 最新 13F 报告期末持有的上市证券 |
| `peer` | NVIDIA `competes_with` 对方 | 对方在该产品大类有自研直接竞争产品 |

同一公司可同时是 supplier、customer、partner、investee 或 peer。去重键固定为：

```text
subject_entity_id + object_entity_id + direction + relationship_type + product_scope_id
```

一条关系只有一个 `product_scope_id`。同键重复观察合并证据、渠道和观察计数；
不同产品或不同角色全部保留。无法映射产品时使用 `corporate_general`，不猜 SKU。

供应商与客户另有 `commercial_directness`：`direct` 表示证据明确直接商业路径，
`indirect` 表示经子公司、代工、分销或上游部件进入，`both` 表示两种路径均有证据，
`unclear` 表示证据能确认商业方向但不能确认是否直采。该字段与 `fact_status` 正交；
监管文件可以确认间接关系，公司新闻或第三方新闻即使看似直采仍最多形成 inferred。

NPN 的地区/分部卡片始终保留为 raw observations。相同 profile URL、仅法定后缀差异、
或经过审阅的地区后缀才可并为一个 group；AMAX、Accenture 等集团的全部原始卡片 ID
与标签仍可回溯。禁止用模糊相似度静默合并。

## 事实、推断与未知

- `confirmed`：正文、监管行、标题/图注或明确 Partners/Customers/Adopters 分组直接支持；
- `inferred`：产品上下文明确，但方向或关系词需推理；
- `unknown`：封面/赞助 Logo、无关章节、来源引用、新闻共现或信息不足。

Logo 位于架构图、封面、活动赞助区或无标题页面时，只能成为 inference/unknown；
与 NVIDIA 产品无关的章节进入 unknown。可解析到上市主体的 `approve_unknown` 与
`needs_more_evidence` 只形成 Partner，分数分别不超过 39 和 49；API/CLI 默认返回它们，
可使用 `include_unknown=false` 或 `--no-include-unknown` 排除 unknown。

重复 partner 只有同时满足“两种独立 evidence family、对方主业一致、产品一致、
交易/使用/供货措辞、无强反证”才可低置信度推断 supplier/customer，并解释
partner-only 替代含义；该类分数严格小于 60。

## 评分

`confidence_score` 是关系证据可信度，不是股票吸引力。分项为：

| 分项 | 上限 |
|---|---:|
| 来源权威性 | 25 |
| 表达明确性 | 25 |
| 实体解析 | 15 |
| 独立 publisher | 15 |
| 时效 | 10 |
| 可量化信息 | 10 |
| 关系类型特异性 | 5 |
| 冲突扣分 | -20 |

总分先限制在 0–100，再应用状态上限：`confirmed=100`、`inferred=69`、
`unknown=39`；推断 supplier/customer 使用 59 上限。时间因子为 0–90 天 100%、
91–180 天 90%、181–365 天 75%、超过 365 天 55%。

13F 的 shares、value、CUSIP 和在本次已报告上市持仓中的占比提高 quantification，
但不会被解释成战略意图。相同 NVIDIA publisher 的多篇材料增加观察深度，
不增加独立 publisher 数。

SEC 域名仅表示材料由 EDGAR 托管，不自动表示正文属于监管申报。8-K 的公司新闻附件、
业绩稿、电话会稿和保守处理的 6-K 公司公告继续使用 company-news 上限；只有 10-K、10-Q、
招股书、8-K 正式 Item 正文或等价监管材料中的明确方向可以支持 confirmed。每份原始材料
只选择一个最强上下文作为 primary，其余重复 NVIDIA 命中保留为 corroborating。

## 快速开始

需要 Python 3.11+。服务使用冻结 snapshot，不需要真实凭据。

```bash
cd arti
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env  # 可选；只含示例，不提交真实信息
```

```bash
# 校验冻结快照并运行测试
.venv/bin/python -m compileall -q src scripts tests runs/2026-08-25-run-003
.venv/bin/python scripts/validate_snapshot.py --snapshot data/snapshot_2026-08-25.json
.venv/bin/python scripts/audit_delivery.py
.venv/bin/pytest

# 启动 API
.venv/bin/uvicorn arti.api:app --host 127.0.0.1 --port 8000
```

OpenAPI：`http://127.0.0.1:8000/docs`；健康检查：`GET /health`。

## CLI

```bash
# 公司解析
.venv/bin/arti company NVDA

# NVIDIA 的 supplier，按置信度/相关度过滤
.venv/bin/arti relationships --company NVDA --type supplier \
  --commercial-directness direct --min-confidence 60 --min-relevance 60 --limit 20

# 指定方向、产品和时间
.venv/bin/arti relationships --company NVDA --direction partners_with \
  --product networking --as-of 2026-08-25 --limit 50

# 证据查询
.venv/bin/arti evidence --source-family official_article \
  --published-from 2025-01-01 --published-to 2026-08-25 --limit 20

# 一跳关系图
.venv/bin/arti graph --company NVDA --type peer --min-confidence 60 --limit 50
# 使用上一页返回的 next_cursor 获取下一页
.venv/bin/arti graph --company NVDA --type peer --min-confidence 60 \
  --limit 50 --cursor '上一页返回的cursor'
```

CLI 成功退出码为 `0`；语法/枚举/日期/范围坏输入、坏游标、不存在实体或缺文件均返回
结构化 JSON，退出码为 `2`，错误码包括 `not_found`、`invalid_cursor`、
`invalid_input` 和 `file_not_found`。`min-confidence`、`min-relevance` 为 0–100，
`limit` 为 1–100。

## HTTP JSON API

| 入口 | 作用 |
|---|---|
| `GET /health` | 快照版本、截点及对象计数 |
| `GET /v1/meta` | 研究对象、覆盖、不覆盖和免责声明 |
| `GET /v1/companies` | 公司搜索、listed filter、cursor 分页 |
| `GET /v1/companies/{id_or_ticker}` | ID/ticker/法定名/alias 解析 |
| `GET /v1/relationships` | 关系筛选和分页 |
| `GET /v1/relationships/{id}` | 关系、两端实体、证据与来源 |
| `GET /v1/evidence` | 证据筛选和分页 |
| `GET /v1/evidence/{id}` | 单项证据及引用关系 |
| `GET /v1/graph` | 公司一跳 nodes/edges 图 |

关系和图查询支持 `company`、可重复 `relation_type`/`direction`/`status`、
`commercial_directness`、
`min_confidence`/`min_relevance`、`product`、`as_of`、`include_unknown` 和 `limit`；
关系和图查询还支持 `cursor`。图响应在仍有后续结果时返回 `truncated=true` 和
`next_cursor`。证据查询支持 `relationship_id`、`publisher`、
`source_family`、`published_from`/`published_to`、`human_verified`、`limit` 和 `cursor`。
CLI 对应关系类型参数名为 `--type`，证据 relationship ID 是可选位置参数。

```bash
curl -G 'http://127.0.0.1:8000/v1/relationships' \
  --data-urlencode 'company=NVDA' \
  --data-urlencode 'relation_type=partner' \
  --data-urlencode 'product=networking' \
  --data-urlencode 'min_confidence=60' \
  --data-urlencode 'limit=20'
```

HTTP 400 表示坏 cursor，404 表示对象不存在，422 表示参数校验失败。错误具有固定结构：

```json
{"error":{"code":"not_found","message":"company not found: NOTREAL"}}
```

## 更新与复现

运行时 API 不联网。完整复现使用已提交的 manifest、structured observations、
decision ledgers 和 source metadata：

```bash
# 各数据族 validator（示例）
.venv/bin/python runs/2026-08-25-run-003/product_tree_v2/validate_v2.py
.venv/bin/python runs/2026-08-25-run-003/agents/npn_runtime_complete/build_outputs.py

# 所有 gate 通过后才生成最终快照
.venv/bin/python scripts/build_snapshot_v2.py \
  --run-root runs/2026-08-25-run-003 \
  --output data/snapshot_2026-08-25.json \
  --entity-registry-overlay runs/2026-08-25-run-003/agents/non_npn_listing_audit/researched_entity_registry_overlay.jsonl \
  --entity-registry-overlay runs/2026-08-25-run-003/agents/npn_listed_parent_resolution/listed_entity_registry_overlay.jsonl \
  --entity-registry-overlay runs/2026-08-25-run-003/agents/partner_regulatory_entity_normalization/entity_registry_overlay.jsonl \
  --entity-registry-overlay runs/2026-08-25-run-003/agents/partner_regulatory_entity_normalization/sec_cik_entity_registry_overlay.jsonl \
  --entity-merge-map runs/2026-08-25-run-003/agents/partner_regulatory_entity_normalization/entity_merge_map.jsonl

# 上一步同时生成 data/coverage_frontier_2026-08-25.json

.venv/bin/python scripts/validate_snapshot.py --snapshot data/snapshot_2026-08-25.json
.venv/bin/python scripts/audit_delivery.py
.venv/bin/pytest
```

`--skip-gates` 仅供本地开发 schema 检查，禁止用于发布。详细方法见
[research/METHODOLOGY.md](research/METHODOLOGY.md)，更新清单见
[research/UPDATE_RUNBOOK.md](research/UPDATE_RUNBOOK.md)；已完成的人工复核范围、签字状态和
本地交付检查见 [research/DELIVERY_CHECKLIST_ZH.md](research/DELIVERY_CHECKLIST_ZH.md)。

快照 validator 接受 `--snapshot PATH` 或单一位置参数；两者均省略时才读取
`ARTI_DATA_PATH`，再回退到 checked-in 默认路径。因此验证临时构建时必须显式传入
该临时文件，避免误校验旧的默认 snapshot。`make validate SNAPSHOT=path/to/file.json`
提供相同能力。

最终 builder 在进程启动时记录真实 UTC `generated_at`。上游缺失或晚于该时点的
`retrieved_at` 会被截到 build time，并在对应 source 的 `access_policy.notes` 明确标记；
builder 与 snapshot validator 都拒绝任何 `retrieved_at > generated_at` 的发布结果。

## 测试与失败案例

测试覆盖 Pydantic 引用与评分、59/69 状态上限、单产品 key、ticker/alias 解析、
关系/方向/分数/产品/时间筛选、关系/图/证据 cursor 分页、unknown 默认纳入及显式排除、API 400/404/422、
CLI 结构化失败，以及同键重复/不同产品边界。

关键失败路径是 final builder 的 fail-closed gate：缺少任一产品、文章、NPN、实体、
关系或 peer 完成报告时必须失败，不能沿用旧 snapshot 或生成伪完整数据。

失败案例包括：
1. 在获取完整 partner 列表后无法完全核验 partner 是否为上市公司，需要进一步due diligence
2. 在第三方新闻源获取的信息不可用
3. 在复核 partner 与 nvidia 关系身份过程中，对于非美国地区交易所文件获取失败

## AI 与人工责任

AI/Agent 用于 source frontier 枚举、公开页面与 PDF 候选抽取、可见 Logo/卡片识别、
实体 alias 建议、关系初判、代码和测试。AI 输出不是证据；正式结论必须指回公开来源。

确定性代码负责计数、hash、exact join、去重、评分、引用、分页和错误。

人工负责的研究和判断包括：
1. 对英伟达公司和官方材料研究，确定可用的可信数据源，并根据数据源重要程度设计多层agent获取结构。在这部分我设计了 “投资者关系/监管文件-公司分产品线网站-公司分产品线customer stories/blog/news- NVIDIA Partner Network-权威媒体报道-其他信源报道” 的多层信息补充逻辑，尽可能的从可信信息源获取相关上市公司的露出证据。
2. 根据不同数据来源、交叉证据、多种关系的置信度总结推导不同关联上市公司的关系强弱。
3. 总结产品线进行新的竞争 peer 检索。
4. 针对给出的合作伙伴信息，按照Due Diligence的手段设计 Agent ，为已有的合作伙伴证据连接相应正确的上市主体。
5. 最终研究与工程判断、实体消歧、关系方向、状态和评分均由提交者本人负责。

人工复核采用风险分层方法：逐条核阅 Supplier 与本轮新增 confirmed 商业关系；核对最新
10-K、13F、全部 peer、高风险别名和上市母公司合并；并对各类产品页、文章、演示材料、
Logo 视觉推断和 blocked 终态进行抽样。复核范围以关系 ID 排序集合的数量和 SHA-256
绑定在 [人工复核签字清单](research/HUMAN_REVIEW_SIGNOFF.json)，防止后续关系变化仍沿用旧签字。

AI/Agent 只用于来源边界枚举、公开页面和 PDF 候选抽取、Logo/卡片识别、实体 alias 建议、
候选关系初判、代码脚手架与测试；AI 输出不是证据。正式关系必须回指公开 URL、publisher、
日期、locator、短摘录和访问限制，并通过确定性计数、hash、exact join、去重、评分、引用、
分页和错误校验。任何工具均未接收密钥、个人数据、客户机密、付费内容或未授权资料。

工具从未接收密钥、个人数据、客户机密、付费内容或未授权资料；未绕过 robots、登录、
验证码、付费墙、限流或连接挑战。

## 已知盲区与改进方向

- 官方页面只证明截点附近的公开表述，不保证合同仍有效或披露完整；
- first-party marketing 可能夸大关系，非美公司和产品页的 counterparty corroboration 仍可扩大；
- NPN 可见卡片不一定显示 specialization、level、location；未显示字段留空并解释，绝不补猜；
- Blog 正文若 direct/RSS/public replay 均不可用会明确 blocked，标题共现不晋级；
- 13F 是点时且有监管范围限制，不等于 NVIDIA 全部投资；
- Logo、网页和 partner membership 通常不能量化 NVIDIA 收入、采购额或合同独占性；
- 主图是一跳上市公司关系图，未做二阶供应链、风险传播、估值或交易信号。

未来优先改进：扩展当前对手方监管复查中 `public_search_unavailable` 与 `access_blocked`
地区的合法公开覆盖、增加 LEI/FIGI 统一标识、关系终止时间线、来源冲突对象、二阶供应链
穿透和数据质量监控。

## 仓库结构

```text
arti/
├── data/                         # reviewer 直接使用的冻结 snapshot
├── research/                     # 方法、AI 使用与更新清单
├── runs/2026-08-25-run-003/      # 完整 manifest/observations/decisions/gates
├── scripts/                      # fail-closed build 与 validators
├── src/arti/                     # HTTP API、CLI、模型与查询服务
└── tests/                        # 正常与失败/边界测试
```

# Partner 上市主体全球监管来源路由

## 结论

本目录从正式快照 `data/snapshot_2026-08-25.json` 中提取所有 `relation_type=partner` 且 `listing_status=listed` 的实体，为每个发行人建立按上市地区分流的公开监管/交易所披露入口。共覆盖 329 个上市 Partner、23 个上市地区、400 条发行人—来源路由；31 个来源定义中有 30 个截至 2026-08-25 可公开读取，另有 1 个仅用于防误用的未来来源（EU ESAP）。

验证结果为 `status: pass`、`pending_count: 0`。本任务没有修改正式 snapshot。

Partner 范围沿用当前 snapshot，而不是重新判断关系强弱，因此也包括因 `approve_unknown`、`needs_more_evidence` 被保留在 Partners 部分的上市实体。来源路由仅表示“去哪里合法复查监管材料”，不提升关系事实状态，也不证明某一份文件一定存在。

## 文件

- `regulator_registry.jsonl`：31 个监管、OAM 或交易所披露来源。每条包含运营方、官方性质、入口、支持文档类型、检索键优先级、可复现检索步骤、访问限制、失败终态和官方验证页。
- `issuer_source_routes.jsonl`：329 个上市 Partner 的逐发行人路由，保留 snapshot 中的证券、交易所、ticker/CIK/ISIN，并列出主来源和补充来源。
- `access_policy.json`：允许/禁止的访问动作、统一失败终态及 SEC、EDINET、NSE、NewsWeb、ESAP 的特殊约束。
- `validation_report.json`：结构、覆盖、snapshot 哈希、来源引用、HTTPS、失败终态和 ESAP 时点检查。
- `build_registry.py`：确定性生成前三个数据文件，只读取 snapshot，只写本目录。
- `validate_registry.py`：确定性验证并生成验证报告，不发起网络请求。

## 覆盖概览

| 上市地区 | Partner 发行人数 | 主路由 | 补充路由 |
|---|---:|---|---|
| 美国 | 182 | SEC EDGAR | — |
| 台湾 | 31 | MOPS | — |
| 日本 | 22 | EDINET | TDnet/JPX Listed Company Search |
| 韩国 | 13 | DART | — |
| 德国 | 12 | Unternehmensregister | — |
| 中国 | 11 | CNINFO | 按实际交易所选择 SSE 或 SZSE，不交叉误路由 |
| 印度 | 11 | NSE Corporate Filings | BSE Corporate Announcements；需先解析 BSE scrip code |
| 法国 | 10 | AMF BDIF | Euronext Company News Archive |
| 香港 | 10 | HKEXnews | — |
| 加拿大 | 6 | SEDAR+ | 官方 legacy archive（需要时） |
| 瑞典 | 5 | FI Börsinformation | Nasdaq Nordic Company News |
| 英国 | 5 | FCA NSM | FCA historic URL lookup（需要时） |
| 瑞士 | 4 | SIX Official Notices | SIX News & Tools 下的其他法定栏目 |
| 澳洲 | 3 | ASX Market Announcements | — |
| 挪威 | 3 | Oslo Børs NewsWeb OAM | — |
| 新加坡 | 3 | SGXNet | — |
| 芬兰 | 1 | Suomen OAM (`oam.fi`) | Nasdaq Nordic Company News |
| 意大利 | 1 | CONSOB 授权 1INFO | — |
| 卢森堡 | 1 | LuxSE OAM | — |
| 马来西亚 | 1 | Bursa Malaysia Announcements | — |
| 荷兰 | 1 | AFM Financial Reporting Register | AFM Inside Information、Euronext archive |
| 波兰 | 1 | ESPI/EBI public search | — |
| 越南 | 1 | HOSE disclosure portal | — |

地区计数按 listing region 统计；Alibaba、Pegatron、Logitech 等多地上市主体会在多个地区出现，但 `issuer_source_routes.jsonl` 仍只有一条发行人记录。

## 检索优先级

1. 先确认 snapshot 中的上市证券是否处于目标时点，并选对应上市地区。
2. 使用最稳定的监管标识：CIK、LEI、ISIN、监管机构公司代码；缺失时才用 ticker，再以完整法定名称确认。
3. 优先法定申报/OAM，再查交易所及时披露；发行人 IR 只作交叉验证，不能静默替代监管原件。
4. 保存 accession/receipt/message/document ID、提交或发布时间、文档类型、版本/更正状态、原始 URL 和精确 locator。
5. 多证券或多地上市时分别走对应地区；不能把美国 ADS ticker 当作印度/香港/欧洲本地代码。

典型分工：

- 美国：EDGAR 负责 10-K/10-Q/8-K/20-F/6-K/Form 25 等。
- 日本：EDINET 负责法定证券报告，TDnet 负责交易所及时披露。
- 中国：CNINFO 作法定集中入口，再根据 snapshot 的 `Shanghai`/`Shenzhen` 交易所字段复核 SSE/SZSE；生成器不会把上交所发行人送到深交所或反之。
- 荷兰、瑞典、芬兰、挪威、卢森堡等：优先本国 OAM/监管公共库；交易所新闻为补充。
- 印度：NSE symbol 与 BSE scrip code 不是同一标识，BSE 查询不得直接复制 NSE symbol。

## 访问边界与失败终态

所有路由遵循 `access_policy.json` 的 fail-closed 原则：

- 允许普通公开浏览、合规低频请求、使用有合法 key 的文档化 API，以及保存公开监管附件用于研究。
- 禁止绕过登录、付费、CAPTCHA、WAF、浏览器完整性检查、robots 拒绝、API key 或速率限制；禁止轮换身份/IP 规避限制。
- 403/429/5xx、维护页或 JavaScript 静态抓取失败都不能推导“无文件”。应分别记录为 `rate_limited`、`source_unavailable_transient` 或 `js_session_required`。
- 搜索完成但无精确主体、主体存在但目标期间无文档、需要旧档案、主体属于另一 home Member State，必须使用各自终态，不能混成一个 `not_found`。
- HKEXnews、MOPS、DART、NSE、SGX、NewsWeb 等依赖 session/JavaScript 时，只能切换到普通交互式浏览器，不得反向调用私有接口绕过控制。

SEC EDGAR 自动访问必须使用可识别 User-Agent、遵守官方 fair-access 指引并保持不高于其公布的 10 requests/second 上限。EDINET 浏览器检索公开，但 API 需要注册 key。NewsWeb 有数据库版权与再利用限制，不做批量镜像。

## ESAP 时点说明

ESMA 于 2026-07-10 启动 ESAP 第一阶段数据收集，但官方说明平台到 2027 年 7 月才向公众开放。因此 `eu_esap_future` 被显式标记为 `future_not_public`，没有分配给任何发行人，也不能在本 cutoff 作为欧洲统一主路由。欧洲实体继续走各国 OAM/NCA。

## 复现

在本目录运行：

```bash
python3 build_registry.py
python3 validate_registry.py
```

预期验证输出：

```json
{"status":"pass","errors":0,"issuers":329,"sources":31}
```

示例查询：

```bash
# 查看 Alibaba 的香港及美国双路由
jq -c 'select(.issuer_id=="alibaba")' issuer_source_routes.jsonl

# 查看台湾全部发行人的 MOPS 检索键
jq -c 'select(.listing_regions|index("Taiwan")) | {issuer_id,legal_name,routes}' issuer_source_routes.jsonl

# 查看每个来源的访问限制与失败终态
jq -c '{source_id,access,failure_terminals}' regulator_registry.jsonl
```

验证器刻意不做实时网络请求：监管门户的 JavaScript、维护和限流会使在线探测产生不可复现的假阴性。每个来源已记录截至 cutoff 的官方验证页；实际取证时应按路由低频访问，并把实时访问终态另行记账。

## 已知边界

- 路由继承 snapshot 的实体、上市地区与证券字段，不在本任务中重新修正 issuer/ticker。
- `listing_status=listed` 可包含历史已退市证券但仍需查询历史监管材料的实体，例如 ANSYS；路由不把历史证券重新标为 active。
- 欧盟 OAM 适用性通常由 home Member State 决定，而不只是交易地点；若 exact issuer 搜索表明 home state 不同，应使用 `issuer_outside_source_jurisdiction` 并转向正确 OAM。
- 交易所新闻库可能同时含监管与非监管消息，必须保留其分类，不能把普通新闻当作法定披露。
- 原文与英文翻译不一致时，以来源标示的法定语言版本为准。

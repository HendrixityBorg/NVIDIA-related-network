# Partner 对手方监管材料反向复查：EMEA、英国、加拿大

## 结论

本目录对规范 Partner 上市主体中的欧洲、英国、加拿大及其他非亚太、非美国单一上市主体完成了逐主体公开检索。研究窗口为 **2025-01-01 至 2026-08-25**。

- 输入路由主体：329；本工作流实际范围：48。
- 48/48 均有唯一终态，pending 为 0；没有把“已有来源路由”当作“已完成搜索”。
- `regulatory_hit` 10，`searched_no_hit` 38，`access_blocked` 0，`public_search_unavailable` 0。
- 产生 10 条 NVIDIA `sells_to` Partner（Partner 为推定客户）候选：1 条 confirmed、9 条 inferred。
- directness：direct 2、unclear 8；本轮没有发现足以新增 NVIDIA 客户（Partner `supplies_to` NVIDIA）的反向供应商候选。
- Partner 角色全部保留；候选 customer 角色是增量角色。

唯一 confirmed 候选是 Deutsche Telekom：其 2025 年报明确写明 NVIDIA 将交付所需芯片和硬件。其余材料虽能支持“提供、部署或使用”方向，但没有同时确认采购合同或交易链，或者来源是公司正式公告，因此一律不超过 inferred。

## 范围

范围从以下冻结输入计算：

- `partner_regulatory_entity_normalization/canonical_partner_universe.jsonl`
- `partner_regulatory_source_registry/issuer_source_routes.jsonl`

纳入 Germany、France、Canada、UK、Sweden、Switzerland、Norway、Netherlands、Poland、Luxembourg、Italy、Finland 的规范 Partner 主体，也保留以加拿大或瑞士为主要/本地上市地的跨市场主体。

Pegatron 与 Samsung Electronics 只有欧洲 GDR/次级路由，而主要发行人及主要上市地仍属亚太，因此留给亚太工作流，未在本目录重复复查。美国单一上市主体留给 SEC 工作流。

## 检索和判定方法

每个主体均实际执行发行人名称、`NVIDIA`、年份及 `customer / supplier / purchase / revenue / order / GPU` 等方向词组合检索，并检查公开可访问的监管/交易所、发行人 IR、法定年报及正式公告结果。`access_audit.jsonl` 逐主体记录查询、路由、实际查看 URL、访问方式和终态。

判定遵循以下边界：

1. 对手方监管材料明确 NVIDIA 是客户，才新增 Partner `supplies_to` NVIDIA。
2. 对手方监管材料明确购买、订购，或明确 NVIDIA 将向其交付产品，才可 confirmed 为 NVIDIA `sells_to` Partner。
3. 公司正式公告即使方向明确也最多 inferred。
4. “NVIDIA-powered”、兼容、加入生态、奖项、共同研发或一般合作不能单独升级 supplier/customer。
5. “部署/使用 NVIDIA 产品”可以形成低等级客户方向候选，但在采购主体和交易链未知时为 `inferred + unclear`。
6. `fact_status` 与 `directness` 正交；不因 indirect/unclear 自动改变事实状态。
7. 产品不明确时应使用 `corporate_general`；本轮候选均至少能定位到产品大类。

`searched_no_hit` 只表示本次公开官方检索没有找到满足方向门槛的证据，不证明现实中不存在商业关系。

## 候选概览

| Partner | 来源类型 | 方向 | 状态 | directness | 产品大类 |
|---|---|---|---|---|---|
| Deutsche Telekom | 2025 Annual Report | NVIDIA sells_to Partner | confirmed | direct | data center AI infrastructure |
| IONOS | 2025 Financial Statements | NVIDIA sells_to Partner | inferred | unclear | GPU cloud |
| Mercedes-Benz Group | 公司正式页面 | NVIDIA sells_to Partner | inferred | direct | automotive DRIVE |
| Siemens | 公司正式公告 | NVIDIA sells_to Partner | inferred | unclear | industrial AI |
| TELUS | 公司正式公告 | NVIDIA sells_to Partner | inferred | unclear | sovereign AI factory / GPU cloud |
| Volvo Cars | 公司正式公告 | NVIDIA sells_to Partner | inferred | unclear | DRIVE / DGX |
| 2CRSi | 半年度监管材料 | NVIDIA sells_to Partner | inferred | unclear | GPU servers |
| Temenos | Annual Report | NVIDIA sells_to Partner | inferred | unclear | accelerated computing / AI |
| Swisscom | 年度业绩材料 | NVIDIA sells_to Partner | inferred | unclear | DGX SuperPOD |
| Telenor | Annual Report | NVIDIA sells_to Partner | inferred | unclear | AI factory |

完整 URL、publisher、日期、locator、必要短摘录、访问限制和来源指纹见 `evidence.jsonl`。目录没有保留监管材料或第三方页面全文。

## 文件

- `source_frontier.jsonl`：48 个主体的范围、查询、实际搜索标记和终态。
- `candidates.jsonl`：10 个可供后续人工审查的方向候选及 DirectionClaim。
- `evidence.jsonl`：短摘录级证据、URL、publisher、日期、locator、指纹和访问说明。
- `access_audit.jsonl`：48 个主体的合法访问审计。
- `decision_ledger.jsonl`：48/48 唯一终态和增量角色决策。
- `summary.json`：机器可读统计与限制。
- `validation_report.json`：一致性检查结果。
- `build_outputs.py`：使用冻结人工审查结果重建上述 JSON/JSONL；脚本本身不联网。

## 复现与验证

从本目录运行：

```bash
python3 build_outputs.py
jq -e '.pass == true' validation_report.json
jq -s 'length == 48' source_frontier.jsonl
jq -s 'length == 48 and (map(.terminal_status) | all(. == "regulatory_hit" or . == "searched_no_hit" or . == "access_blocked" or . == "public_search_unavailable"))' decision_ledger.jsonl
```

验证器检查：范围恰为 48、逐主体唯一终态、访问审计覆盖、所有行均实际搜索且非 route-only、pending 为 0、Partner 角色保留、confirmed 来源上限、directness 独立字段以及未保留来源全文。

## 合法访问与限制

- 仅使用无需登录的公开搜索和发行人/监管公开页面；未绕过 robots、登录、付费墙、验证码、限流或其他访问控制。
- 未使用真实凭据、密钥、个人数据、客户机密或受限原始数据。
- 公开搜索索引可能遗漏未索引 PDF、当地语言变体或图片式披露；因此 no-hit 是审查终态，不是不存在性证明。
- 本目录不修改主 builder 或最终 snapshot；所有候选仍需在合并前检查产品树映射、端点 ID 和是否存在更直接的订单/采购证据。

# ListedCompany-related-network

这是一个面向任意上市目标公司的、证据可追溯的关系研究框架。输入目标实体、证券标识、官方入口、研究截点和证据窗口，研究 Agent 按统一契约构建 `supplier`、`customer`、`partner`、`investor_or_investee`、`peer` 关系；输出可复核快照、HTTP JSON API、CLI、来源与证据账本及动态验收报告。

仓库同时保留完整的 [NVIDIA 冻结案例](case_studies/nvidia/README.md)。该案例的代码、数据、Agent 中间账本和人工复核结果均位于 `case_studies/nvidia/frozen_2026-08-25/`，未被通用化改写。项目和案例均仅供研究及工程演示，不构成投资建议。

## 研究对象与边界

每次研究由 `profile.yaml` 明确定义：公司法律实体、别名、证券代码/交易所/上市地区、司法辖区、官方域名、研究截点、证据起始日、覆盖项和排除项。最终关系图默认只保留截点时的上市对手方；同一公司可以同时是客户、供应商、合作伙伴、被投对象或 peer，也可在不同产品上保留多条关系。

关系方向统一相对于目标公司：

| 类型 | 规范方向 | 含义 |
|---|---|---|
| supplier | 对手方 `supplies_to` 目标公司 | 对手方向目标公司提供产品或服务 |
| customer | 目标公司 `sells_to` 对手方 | 对手方购买或使用目标公司的商业产品/服务 |
| partner | 目标公司 `partners_with` 对手方 | 无法可靠归入供需，或明确为联合开发/生态合作 |
| investor_or_investee | 目标公司 `invests_in` 对手方 | 默认只研究目标公司的公开上市投资对象 |
| peer | 目标公司 `competes_with` 对手方 | 仅按产品大类纳入具有自研竞争产品的上市公司 |

`confirmed`、`inferred`、`unknown` 严格分层。Logo 若只在封面、架构图、赞助区或无标题页面出现，可保留为低置信度推断；与产品章节无关时标为 unknown。新闻共现、搜索摘要和聚合页只作线索，不能单独确认关系。

## 端到端分析流程

1. **身份与范围冻结**：确认法律实体、证券、上市地区、别名、截点和证据窗口。
2. **通用来源发现**：主动寻找目标公司的监管/年报入口、近两年 IR presentation、newsroom/blog、产品/解决方案/行业二级站点、生态或 partner network，以及权威第三方新闻。发现与证据接受分账记录。
3. **完整枚举**：对官方文章、产品树和生态目录维护分页/节点 frontier；每项必须有 processed、no candidate、access blocked 等终态，不能用“抓到一些”代表完成。
4. **实体归一**：将品牌、地区分部和事业部映射到截点上市母公司；同集团重复主体合并，但保留原始名称、标签和证据。多重上市候选须记录选择理由。
5. **关系裁决**：按公司、关系类型、方向、产品节点合并重复观察；不同产品和不同角色保留。来源冲突、过期信息、主体歧义及推断依据进入关系限制字段。
6. **上市对手方反向复核**：用已识别的每一家上市公司，反查其监管文件、年报及 IR 是否明确提及目标公司及商业方向。全部对手方都要有任务和终态；未命中只说明公开材料未披露，不是否定证据。
7. **评分与 QA**：将来源权威性、表述明确性、实体解析、独立来源、时效、量化信息、关系类型特异性和冲突惩罚连接到 0–100 分。动态 validator 检查来源阶段、引用、截点、方向和反向复核，失败则拒绝生成 release snapshot。

更细的数据契约、来源层级和判定规则见 [研究方法](docs/METHODOLOGY_ZH.md)，实际执行见 [运行手册](docs/RUNBOOK_ZH.md)，Agent 责任边界见 [Agent 工作流](agents/README.md)。

## 数据源、采集、清洗与处理

来源优先级通常为：监管文件/年报与正式 IR 文件 → 官方产品、解决方案、公告及客户案例 → 官方生态/partner network → 对手方监管/IR → 原始报道的权威媒体 → 其他补充来源。目标公司仅强制最近年报及适用的持仓申报；不会无差别抓取全部 10-Q、8-K 或 submissions。对手方监管材料用于反向验证已有实体和关系。

采集由 Agent 执行合法公开检索，并写入 `source_candidates`、`search_queries`、`source_frontier` 与阶段报告。框架不内置绕过访问控制的爬虫；检索工具获得的搜索摘要只是 lead。清洗包括 URL/内容哈希去重、转载聚类、品牌与上市母公司归一、交易所/地区/证券校验、产品节点归一，以及公司+关系+方向+产品语义键去重。处理阶段将证据角色分为 primary、corroborating、lead_only，再进行人工可解释裁决和评分。

每条最终关系必须能一跳定位到已提交的 source 和 evidence。NVIDIA 案例提交了快照、有限证据摘录/视觉说明、证据 locator、运行 manifest、完整 frontier、决定账本、验证报告和人工签字，因此 reviewer 可以离线理解结论；联网只用于独立核对原网页是否仍存在，不是理解或运行交付的必要条件。访问与再分发边界见 [DATA_NOTICE.md](DATA_NOTICE.md)。

## 安装和运行

需要 Python 3.11+：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
listed-company-network verify-case --manifest case_studies/nvidia/case_manifest.json
```

启动冻结 NVIDIA 快照的 HTTP API：

```bash
export LCN_DATA_PATH="$PWD/case_studies/nvidia/frozen_2026-08-25/data/snapshot_2026-08-25.json"
listed-company-network serve
```

API 提供 `/v1/companies`、`/v1/relationships`、`/v1/evidence`、`/v1/graph` 和 `/v1/meta`；关系查询支持公司、类型、方向、事实状态、商业直接性、置信度、相关度、产品和时间筛选，以及游标分页。错误使用稳定 JSON envelope 和明确 HTTP 状态。OpenAPI 位于 `/docs`。

CLI 示例：

```bash
listed-company-network relationships --company NVDA --type supplier --min-confidence 50 --limit 20
listed-company-network graph --company NVDA --type partner --product automotive --limit 100
listed-company-network evidence --publisher NVIDIA --published-from 2025-01-01
```

## 新建研究运行

复制并修改 `profiles/nvidia.yaml`（它只是完整字段示例），然后初始化独立运行目录：

```bash
listed-company-network init-run --profile profiles/target.yaml --run runs/target-YYYY-MM-DD
```

该命令生成来源候选、搜索计划、空白规范化账本和 11 个 Agent 任务契约。Agent 完成来源阶段和实体/关系归一后：

```bash
listed-company-network review-tasks --profile profiles/target.yaml --run runs/target-YYYY-MM-DD
# 完成每个反向复核任务并写入 counterparty_decisions 后
listed-company-network validate-run --profile profiles/target.yaml --run runs/target-YYYY-MM-DD
listed-company-network build-snapshot --profile profiles/target.yaml --run runs/target-YYYY-MM-DD --output data/target-snapshot.json
```

`build-snapshot` 是 fail-closed：required 阶段缺报告、有 pending、证据引用断裂、新闻单独确认关系、截点越界或任何上市对手方未完成反向复核时，都不会生成交付快照。

`schemas/` 提供 profile、来源候选、阶段报告、反向复核、验证报告和最终 snapshot 的 JSON Schema；模型变更后运行 `python scripts/export_schemas.py` 重新生成。

## 复现、更新与 fixture

- `profiles/nvidia.yaml` 固定 NVIDIA 研究范围；冻结案例本身由 `case_manifest.json` 固定提交、关键 SHA-256 和计数。
- `pytest` 使用小型合成 fixture 测试成功路径，以及反向复核缺失、第三方新闻单独确认等失败边界，不需要网络。
- 更新已有公司时应新建带新截点的 run 和 snapshot，不覆盖旧版本；重新执行完整来源 frontier 和全部上市对手方反查，而不是只追加新闻。
- NVIDIA 原始执行细节、数据更新命令和已知盲区仍完整保存在冻结目录 README、`research/` 与 `runs/` 中。

## AI 与人工责任

AI/编码 Agent 用于来源发现、页面/文件枚举、实体候选抽取、去重、监管材料检索、关系候选生成、评分草稿、测试和一致性检查。人工必须验证主体身份、上市状态、原文 locator、关系方向、产品归属、事实/推断/未知等级、来源冲突和最终评分；模型输出不能替代原始证据。本项目的研究与工程判断由提交者本人负责。不得向任何工具输入密钥、个人数据、客户机密或未授权资料。

## 已知限制与改进方向

- 公司通常不会披露完整供应链或客户名单；公开文件未命中具有严重漏报偏差。
- partner network 证明生态身份，但通常不能证明采购方向；低置信度供需推断必须明确说明且受评分上限约束。
- 品牌、子公司、合资公司和多地上市可能在截点发生变化，需要人工核查最终母公司。
- 新闻转载会制造虚假的来源独立性；当前通过 publisher 与 syndication 分组处理，未来可增加更强的内容指纹和事件聚类。
- 通用框架提供数据契约、任务生成与质量门槛，不承诺对任意网站零配置自动抽取；复杂站点需要合法、可审计的站点适配器。

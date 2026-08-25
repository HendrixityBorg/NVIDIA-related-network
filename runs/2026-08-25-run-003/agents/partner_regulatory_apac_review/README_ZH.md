# APAC Partner 监管材料复查

## 结论

本目录完成了 `canonical_partner_universe.jsonl` 中亚太上市地区 Partner 主体的逐主体复查。研究窗口冻结为 **2025-01-01 至 2026-08-25**；104 个规范主体均有且仅有一个终态，`validation_report.json` 为 `status=pass`、`pending_count=0`。未修改主 builder 或最终 snapshot。

复查产生 13 个需判断方向的候选，其中 7 个监管材料明确表达 NVIDIA 向 Partner（或其子公司）供应/Partner 采购 NVIDIA 产品，形成 `NVIDIA --sells_to/customer--> Partner` 的 confirmed 候选；另 6 个只证明分销资格、生态兼容、平台使用或向第三方销售，保持 unknown，不生成方向 claim。

## 覆盖与终态

| 终态 | 数量 | 含义 |
|---|---:|---|
| `regulatory_hit` | 45 | 实际检索的官方材料中出现 NVIDIA 词项；不等于自动形成方向 claim |
| `searched_no_hit` | 19 | 在 `source_frontier.jsonl.searched_scope` 所述边界内完成检索但无命中 |
| `public_search_unavailable` | 33 | 官方入口可访问，但本次无法以公开、可复现、无需 JS/session 规避的方式执行精确正文检索 |
| `access_blocked` | 7 | 官方入口或文件访问被 401/403/429、服务错误或文件提取失败阻断；未绕过 |

地区覆盖：TW 30、JP 22、KR 13、CN 11、IN 11、HK 9、AU 3、SG 3、MY 1、VN 1。逐主体检索入口、实际 query、范围、命中数与失败终态见 `source_frontier.jsonl`；每个 HTTP 尝试见 `access_audit.jsonl`。

检索方法按地区如下：

- 中国：对 CNINFO 正文全局检索 `NVIDIA` 与 `英伟达`，完整翻页后按证券代码精确过滤；命中文件下载并逐页提取。
- 韩国：以 DART 精确法人 CIK 检索 `NVIDIA|엔비디아`，打开完整申报文件 viewer 并提取上下文。
- 台湾：按公司代码从 TWSE/MOPS 官方年度报告文档服务器取得 2025 年年度报告（2026 年提交），搜索所有可提取页面中的 `NVIDIA/輝達/英偉達`。
- 印度：按 NSE 精确 symbol 和日期区间请求公司公告 API，搜索公告元数据；匹配附件下载后全文检索。NSE 上市公司新闻仍受 company-news 上限约束。
- 日本、香港、澳洲、新加坡、马来西亚、越南：对官方披露入口进行了实际公开访问探测；无法在不依赖不可复现的 JS/session 交互或绕过访问控制的情况下完成精确正文检索，因此如实终止为 `public_search_unavailable` 或 `access_blocked`，没有把“入口存在”记为“已搜索”。

`searched_no_hit` 只陈述已记录范围内的结果，不表示相应监管门户的所有文档都可被机器搜索。

## Confirmed 方向候选

| Partner | directness | 监管材料与定位 | 判断 |
|---|---|---|---|
| Compal Electronics | direct | TWSE/MOPS 2025 年报，PDF p.213 | GPU 主要供应来源表明确列 NVIDIA |
| Quanta Computer | direct | TWSE/MOPS 2025 年报，PDF p.123 | CPU/GPU 主要供应商表明确列 NVIDIA |
| Tatung System Technologies | unclear | TWSE/MOPS 2025 年报，PDF p.95 | 主要供应商包含 NVIDIA，但相邻代理/分销措辞不能确定直接开票路径 |
| Leadtek Research | unclear | TWSE/MOPS 2025 年报，PDF p.6 | 明确记载 NVIDIA 工作站显卡持续供应；未说明直接开票主体 |
| Samsung Electronics | direct | DART，2026-08-14，viewer context 2 | Harman 明确从 NVIDIA/WNC 获得 SoC/通信模块 |
| SNet Systems | unclear | DART，2026-08-13，viewer context 5 | NVIDIA 是主要采购来源，但文件同时描述通过国内分销商采购，直接路径不明 |
| Unisplendour | indirect | CNINFO，2026-07-21，PDF p.2 | NVIDIA 厂商授信义务发生于上市公司子公司，故保留 indirect |

上述 7 条均在 `candidates.jsonl.proposed_claim` 中提供 integration 可直接读取的 claim，并用 `source_evidence_ids` 连接到 `evidence.jsonl`。方向统一为 NVIDIA `sells_to` Partner，关系类型为 `customer`；`directness` 与 `fact_status` 独立保存。

## 保持 unknown 的 6 个候选

- EDOM：披露 NVIDIA 分销协议，但未在所选段落中证明窗口内实际采购/订单。
- MDS Tech：International Distributor Agreement/伙伴资格不足以证明实际采购。
- Zero One Technology：授权分销商身份明确，但未证明实际交易流。
- XIILAB：向 Algorix 销售 NVIDIA 标示产品，不能据此把 NVIDIA 认定为 XIILAB 的卖方或客户。
- Orbbec：只证明兼容性/生态合作，没有采购、订单、营收或客户方向。
- TZTEK：官方 Jetson 合作伙伴、平台使用及向其他客户销售，不能确定与 NVIDIA 的交易方向。

公司正式新闻或交易所转发公司公告最多为 inferred；“powered by/uses/compatible with/合作”本身不生成 customer claim。当前 7 条 confirmed 均由监管申报材料中明确方向支持。

## 文件说明

- `source_frontier.jsonl`：104 个主体的实际检索范围、入口、命中数和唯一终态。
- `candidates.jsonl`：13 个方向候选；仅 7 个 confirmed 条目含 `proposed_claim`。
- `evidence.jsonl`：候选证据、短摘录、定位、来源、来源上限与方向理由。
- `access_audit.jsonl`：访问方法、HTTP/处理结果、未绕过访问控制的审计轨迹。
- `decision_ledger.jsonl`：104 个主体的最终决定；保留 Partner 角色，supplier/customer 角色只作增量添加。
- `raw_contexts.jsonl`：578 条检索上下文的辅助审计材料，不是 claim 清单。
- `summary.json`：覆盖、终态和 claim 汇总。
- `validation_report.json`：结构、覆盖、方向、来源上限、证据引用及访问控制检查。
- `collect_apac_review.py`：实际检索与采集脚本；需要 `requests` 与 `pypdf`。
- `repair_dart.py`：对 DART viewer 链接解析修复后重跑韩国切片并合并。
- `build_review_outputs.py`：从原始上下文生成候选、证据、决定与汇总。
- `validate_review.py`：最终 build gate。

## 复现与验证

在隔离环境安装 `requests`、`pypdf` 后，可在本目录运行：

```bash
python3 collect_apac_review.py
python3 build_review_outputs.py
python3 validate_review.py
```

仅验证已有输出时运行后两步。验证器要求 104/104 frontier 与 decision 覆盖、候选和证据一一对应、仅明确方向候选含 `proposed_claim`、confirmed claim 只由监管材料产生、方向固定为 NVIDIA `sells_to` Partner、`directness` 合法、无访问控制绕过。当前结果：`status=pass`，`pending_count=0`。

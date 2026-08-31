from __future__ import annotations

from .contracts import AgentTask, ResearchProfile


LEGAL_RULES = [
    "仅访问无需登录且法律允许访问的公开资料。",
    "遵守 robots、付费墙、验证码、限流及其他访问控制；受阻即记录终态，不绕过。",
    "不得输入或保存密钥、个人数据、客户机密、受限原文或未经授权内容。",
    "保留 URL、publisher、发布时间/获取时间、evidence locator 与访问/许可说明。",
]


def build_agent_tasks(profile: ResearchProfile) -> list[AgentTask]:
    root = "run_root"
    definitions = [
        (
            "source_discovery",
            "通用来源发现",
            "发现并分类官方 IR、新闻/博客、产品/解决方案、生态网络、监管入口和第三方新闻来源。",
            [],
            ["discovery/source_candidates.jsonl", "discovery/search_queries.jsonl"],
            ["每类来源都有入口或带检索记录的未找到/不适用终态", "区分发现与证据接受"],
        ),
        (
            "regulatory_ir",
            "目标公司监管与 IR",
            "处理最近年报、适用的持仓申报和截点前两年投资者演示材料。",
            ["discovery/source_candidates.jsonl"],
            ["stage_reports/annual_filing.json", "stage_reports/investor_presentations.json"],
            ["年报及适用申报逐份终结", "Logo 与正文分开定位并保留推断等级"],
        ),
        (
            "official_articles",
            "官方新闻与博客全量枚举",
            "枚举证据窗口内 newsroom、blog、news release、customer story 的全部文章并提取上市实体。",
            ["discovery/source_candidates.jsonl"],
            ["stage_reports/official_articles.json"],
            ["分页/归档边界有清单", "文章总数、终态数和未处理数可核对"],
        ),
        (
            "product_tree",
            "产品与解决方案树冻结",
            "覆盖全部官方业务二级站点，冻结产品、解决方案、行业和页面关系，并提取关联上市实体。",
            ["discovery/source_candidates.jsonl"],
            ["stage_reports/product_solutions.json", "artifacts/product_tree.jsonl"],
            ["每个发现节点有父节点、URL 与终态", "跨页面别名合并但保留来源"],
        ),
        (
            "ecosystem_network",
            "生态/合作伙伴网络全量处理",
            "完整分页生态目录，保存 partner type、competency、program 等标签并按上市母公司归一。",
            ["discovery/source_candidates.jsonl"],
            ["stage_reports/ecosystem_directory.json"],
            ["分页无缺口或有访问受阻终态", "地区/事业部主体按集团去重，原始名称仍可追溯"],
        ),
        (
            "third_party_news",
            "第三方新闻线索",
            "用独立媒体补充供应商、客户、合作伙伴与并购线索，识别转载与新闻共现误判。",
            ["discovery/search_queries.jsonl"],
            ["stage_reports/third_party_news.json", "discovery/third_party_news.jsonl"],
            ["搜索摘要仅作 lead", "转载合并为同一来源族", "新闻单独不能确认商业方向"],
        ),
        (
            "entity_resolution",
            "上市实体与母公司识别",
            "将提及映射到截点时的上市法律实体、证券标识和上市地区；多重候选时记录选择理由。",
            ["normalized/evidence.jsonl"],
            ["normalized/entities.jsonl"],
            ["实体身份与关系证据分离", "无法确定时不得静默猜测"],
        ),
        (
            "counterparty_regulatory",
            "上市对手方反向监管/IR 复核",
            "对关系图中的每一家上市对手方搜索其监管文件与 IR，核验其是否称目标为客户、供应商或合作伙伴。",
            ["review/counterparty_tasks.jsonl"],
            ["review/counterparty_decisions.jsonl", "stage_reports/counterparty_regulatory.json"],
            ["每个任务都有终态", "未命中不视为否定", "公司公告可确认；公司新闻或媒体通常只支持推断"],
        ),
        (
            "relationship_adjudication",
            "关系裁决、去重与评分",
            "按方向、产品、状态、时效和证据独立性裁决关系；同公司可有多个角色。",
            ["normalized/entities.jsonl", "normalized/evidence.jsonl"],
            ["normalized/relationships.jsonl"],
            ["相同公司+关系+方向+产品去重", "不同产品或角色全部保留", "事实/推断/未知清楚分层"],
        ),
        (
            "peer_research",
            "产品大类可比公司",
            "只按产品大类研究具有自研竞争产品的上市公司。",
            ["artifacts/product_tree.jsonl"],
            ["stage_reports/peer_research.json"],
            ["不得把仅为渠道商或集成商的公司当作 peer", "允许某产品大类无 peer"],
        ),
        (
            "qa_release",
            "独立 QA 与发布门槛",
            "检查引用完整性、来源许可、截点、反向复核、计数与 API/CLI 可运行性。",
            ["normalized/relationships.jsonl", "review/counterparty_decisions.jsonl"],
            ["validation_report.json"],
            ["所有 required 阶段通过", "无 pending", "失败时不得生成 release snapshot"],
        ),
    ]
    tasks = []
    for agent, label, objective, inputs, outputs, requirements in definitions:
        tasks.append(
            AgentTask(
                id=f"{profile.project_slug}_{agent}",
                agent=agent,
                objective=f"{label}：{objective}",
                profile_path=f"{root}/profile.yaml",
                input_paths=[f"{root}/{item}" for item in inputs],
                output_paths=[f"{root}/{item}" for item in outputs],
                completion_requirements=requirements,
                legal_access_rules=LEGAL_RULES,
            )
        )
    return tasks

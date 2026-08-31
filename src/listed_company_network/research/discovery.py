from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from .contracts import (
    DiscoveryDecision,
    Officiality,
    ResearchProfile,
    SearchQueryRecord,
    SourceCandidate,
    SourceFamily,
)
from .io import stable_id


FAMILY_PATH_HINTS: list[tuple[SourceFamily, tuple[str, ...]]] = [
    (SourceFamily.INVESTOR_PRESENTATIONS, ("investor", "presentation", "events")),
    (SourceFamily.OFFICIAL_ARTICLES, ("news", "newsroom", "blog", "press")),
    (SourceFamily.PRODUCT_SOLUTIONS, ("product", "products", "solution", "industries")),
    (SourceFamily.ECOSYSTEM_DIRECTORY, ("partner", "ecosystem", "marketplace")),
]


def classify_official_url(url: str) -> SourceFamily | None:
    path = urlparse(url).path.casefold()
    for family, hints in FAMILY_PATH_HINTS:
        if any(hint in path for hint in hints):
            return family
    return None


def seed_candidates(
    profile: ResearchProfile, *, discovered_at: datetime | None = None
) -> list[SourceCandidate]:
    now = discovered_at or datetime.now(timezone.utc)
    rows: list[SourceCandidate] = []
    for url in profile.target.investor_relations_urls:
        value = str(url)
        rows.append(
            SourceCandidate(
                id=stable_id("source", value),
                family=classify_official_url(value)
                or SourceFamily.INVESTOR_PRESENTATIONS,
                url=value,
                publisher=profile.target.display_name,
                discovered_via="profile_seed",
                officiality=Officiality.FIRST_PARTY,
                decision=DiscoveryDecision.ACCEPTED,
                decision_reason="目标公司配置中的官方投资者关系入口",
                discovered_at=now,
            )
        )
    for domain in profile.target.official_domains:
        value = f"https://{domain.strip('/')}"
        rows.append(
            SourceCandidate(
                id=stable_id("source", value),
                family=SourceFamily.PRODUCT_SOLUTIONS,
                url=value,
                publisher=profile.target.display_name,
                discovered_via="profile_seed",
                officiality=Officiality.FIRST_PARTY,
                decision=DiscoveryDecision.CANDIDATE,
                decision_reason="官方域名入口；需由来源发现 Agent 分类子站和栏目",
                discovered_at=now,
            )
        )
    return list({item.id: item for item in rows}.values())


def plan_search_queries(profile: ResearchProfile) -> list[SearchQueryRecord]:
    name = profile.target.display_name
    aliases = [name, profile.target.legal_name, *profile.target.aliases]
    quoted = " OR ".join(f'"{item}"' for item in dict.fromkeys(aliases))
    definitions: list[tuple[SourceFamily, str, str]] = [
        (SourceFamily.INVESTOR_PRESENTATIONS, f"({quoted}) investor presentation", "发现近两年路演及大会材料"),
        (SourceFamily.OFFICIAL_ARTICLES, f"({quoted}) newsroom OR blog OR press release", "发现公司新闻、博客与客户案例栏目"),
        (SourceFamily.PRODUCT_SOLUTIONS, f"({quoted}) products OR solutions OR industries", "冻结完整产品与解决方案树"),
        (SourceFamily.ECOSYSTEM_DIRECTORY, f"({quoted}) partner network OR ecosystem OR marketplace", "发现生态或合作伙伴目录"),
        (SourceFamily.THIRD_PARTY_NEWS, f"({quoted}) supplier OR customer OR partner", "发现独立第三方关系线索"),
        (SourceFamily.PEER_RESEARCH, f"({quoted}) competitors by product category", "按产品大类发现自研竞争者"),
    ]
    return [
        SearchQueryRecord(
            id=stable_id("query", family.value, query),
            family=family,
            query=query,
            purpose=purpose,
            target_entity_id=profile.target.id,
        )
        for family, query, purpose in definitions
    ]


def is_news_semantic_evidence_eligible(observation: dict) -> bool:
    """News co-occurrence and search snippets are lead-only, never semantic proof."""
    return bool(
        observation.get("access_status") == "accessible"
        and observation.get("locator")
        and not observation.get("cooccurrence_warning", True)
        and observation.get("evidence_eligibility") in {"primary", "corroborating"}
    )

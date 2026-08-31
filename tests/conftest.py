from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from listed_company_network.models import (
    AccessPolicy,
    CommercialDirectness,
    Entity,
    Evidence,
    EvidenceRole,
    FactStatus,
    ListingStatus,
    RelationDirection,
    RelationType,
    Relationship,
    ScoreBreakdown,
    SecurityIdentifier,
    Source,
    TemporalStatus,
)
from listed_company_network.research.contracts import (
    CompletionStatus,
    CounterpartyReviewDecision,
    ResearchProfile,
    ResearchSecurity,
    ReviewTerminal,
    StageReport,
    SubjectIdentity,
)
from listed_company_network.research.counterparty import build_counterparty_tasks
from listed_company_network.research.io import write_document, write_jsonl


NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


@pytest.fixture
def profile() -> ResearchProfile:
    return ResearchProfile(
        project_slug="testco",
        target=SubjectIdentity(
            id="testco",
            legal_name="Test Company, Inc.",
            display_name="TestCo",
            aliases=["Test Company"],
            jurisdiction="United States / Delaware",
            securities=[
                ResearchSecurity(
                    ticker="TEST",
                    exchange="Nasdaq",
                    listing_region="United States",
                    listing_region_code="US",
                    cik="0000000001",
                )
            ],
            official_domains=["test.example"],
            investor_relations_urls=["https://test.example/investors"],
        ),
        cutoff_at=NOW,
        evidence_start_date=date(2025, 1, 1),
        snapshot_version="testco-2026-08-25",
    )


def entity(
    entity_id: str, name: str, ticker: str, *, target: bool = False
) -> Entity:
    return Entity(
        id=entity_id,
        legal_name=name,
        display_name=name,
        listing_status=ListingStatus.LISTED,
        listing_regions=["United States"],
        securities=[
            SecurityIdentifier(
                ticker=ticker,
                exchange="Nasdaq",
                listing_region="United States",
                listing_region_code="US",
                primary=True,
            )
        ],
    )


def write_valid_run(run_root: Path, profile: ResearchProfile) -> None:
    subject = entity(profile.target.id, profile.target.legal_name, "TEST", target=True)
    customer = entity("customerco", "Customer Company", "CUST")
    source = Source(
        id="src_official",
        url="https://customer.example/investors/annual-report",
        publisher="Customer Company",
        title="Annual report",
        source_type="annual_report",
        published_at=date(2026, 3, 1),
        retrieved_at=NOW,
        access_policy=AccessPolicy(
            access="public",
            redistribution="metadata_and_short_excerpt",
            notes="No login or paywall",
        ),
        source_family="counterparty_regulatory",
    )
    evidence = Evidence(
        id="ev_customer",
        source_id=source.id,
        locator="p. 12, Customers",
        excerpt="TestCo supplies the platform used by Customer Company.",
        supports="Customer Company is a TestCo customer",
        human_verified=True,
    )
    breakdown = ScoreBreakdown(
        source_authority=25,
        explicitness=25,
        entity_resolution=15,
        independence=5,
        timeliness=10,
        quantification=0,
        relationship_type_specificity=5,
    )
    relation = Relationship(
        id="rel_customer",
        source_entity_id=profile.target.id,
        target_entity_id=customer.id,
        relation_type=RelationType.CUSTOMER,
        direction=RelationDirection.SELLS_TO,
        direction_explanation="Counterparty filing identifies use of the target platform.",
        commercial_directness=CommercialDirectness.DIRECT,
        product_scope_id="platform",
        fact_status=FactStatus.CONFIRMED,
        temporal_status=TemporalStatus.CURRENT,
        as_of=date(2026, 8, 25),
        confidence_score=85,
        relevance_score=70,
        confidence_breakdown=breakdown,
        relevance_explanation="Named current customer of a core platform.",
        evidence_ids=[evidence.id],
        evidence_roles={evidence.id: EvidenceRole.PRIMARY},
        relationship_evidence_ids=[evidence.id],
    )
    write_jsonl(run_root / "normalized/entities.jsonl", [subject, customer])
    write_jsonl(run_root / "normalized/sources.jsonl", [source])
    write_jsonl(run_root / "normalized/evidence.jsonl", [evidence])
    write_jsonl(run_root / "normalized/relationships.jsonl", [relation])
    tasks = build_counterparty_tasks(profile, [subject, customer], [relation])
    write_jsonl(run_root / "review/counterparty_tasks.jsonl", tasks)
    decision = CounterpartyReviewDecision(
        id="decision_customerco",
        task_id=tasks[0].id,
        counterparty_entity_id=customer.id,
        terminal_status=ReviewTerminal.RELATIONSHIP_CONFIRMED,
        reviewed_at=NOW,
        reviewed_sources=1,
        exact_mentions=1,
        evidence_ids=[evidence.id],
        relationship_ids=[relation.id],
        rationale="Annual report explicitly identifies the target product relationship.",
    )
    write_jsonl(run_root / "review/counterparty_decisions.jsonl", [decision])
    for policy in profile.source_policies:
        report = StageReport(
            stage=policy.family,
            status=CompletionStatus.COMPLETE,
            expected=1,
            processed=1,
            terminal=1,
            pending=0,
            generated_at=NOW,
            checks={"frontier_terminal": True},
        )
        write_document(run_root / f"stage_reports/{policy.family.value}.json", report)

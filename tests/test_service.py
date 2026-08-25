from datetime import date

import pytest

from arti.models import FactStatus, RelationType
from arti.repository import SnapshotRepository
from arti.service import InvalidCursorError, NotFoundError, ResearchService


@pytest.fixture(scope="module")
def service() -> ResearchService:
    return ResearchService(SnapshotRepository())


def test_snapshot_references_and_scoring_validate(service: ResearchService) -> None:
    assert service.repo.snapshot.meta.subject_entity_id == "nvidia"
    assert len(service.repo.relationships) >= 15
    assert all(
        relation.confidence_score <= 100
        for relation in service.repo.relationships.values()
    )


def test_company_resolution_supports_ticker_and_alias(service: ResearchService) -> None:
    assert service.resolve_entity("NVDA").id == "nvidia"
    foxconn = service.resolve_entity("Foxconn")
    assert any(security.ticker == "2317" for security in foxconn.securities)
    with pytest.raises(NotFoundError):
        service.resolve_entity("not-a-real-company")


def test_supplier_direction_is_toward_nvidia(service: ResearchService) -> None:
    page = service.list_relationships(
        company="NVDA", relation_types={RelationType.SUPPLIER}, limit=100
    )
    expected = sum(
        item.relation_type == RelationType.SUPPLIER
        for item in service.repo.relationships.values()
    )
    assert page.total == expected
    assert all(item.target_entity_id == "nvidia" for item in page.items)


def test_point_in_time_13f_filter(service: ResearchService) -> None:
    before = service.list_relationships(
        company="NVDA",
        relation_types={RelationType.INVESTOR_OR_INVESTEE},
        as_of=date(2026, 6, 29),
        limit=100,
    )
    at_period_end = service.list_relationships(
        company="NVDA",
        relation_types={RelationType.INVESTOR_OR_INVESTEE},
        as_of=date(2026, 6, 30),
        limit=100,
    )
    assert before.total == 0
    expected = sum(
        item.relation_type == RelationType.INVESTOR_OR_INVESTEE
        and item.as_of <= date(2026, 6, 30)
        and (item.valid_from is None or item.valid_from <= date(2026, 6, 30))
        and (item.valid_to is None or date(2026, 6, 30) <= item.valid_to)
        for item in service.repo.relationships.values()
    )
    assert at_period_end.total == expected


def test_product_and_score_filters(service: ResearchService) -> None:
    scoped_relationship = next(
        item
        for item in service.repo.relationships.values()
        if item.product_scope_id != "corporate_general"
    )
    result = service.list_relationships(
        company="nvidia",
        product=scoped_relationship.product_scope_id,
        min_relevance=0,
        limit=100,
    )
    assert result.total >= 1
    assert scoped_relationship.id in {item.id for item in result.items}
    assert all(
        scoped_relationship.product_scope_id.casefold()
        in item.product_scope_id.casefold()
        or any(
            scoped_relationship.product_scope_id.casefold() in scope.casefold()
            for scope in item.product_scopes
        )
        for item in result.items
    )


def test_pagination_and_bad_cursor(service: ResearchService) -> None:
    first = service.list_relationships(company="nvidia", limit=2)
    second = service.list_relationships(
        company="nvidia", limit=2, cursor=first.next_cursor
    )
    assert first.next_cursor is not None
    assert {item.id for item in first.items}.isdisjoint(
        {item.id for item in second.items}
    )
    with pytest.raises(InvalidCursorError):
        service.list_relationships(company="nvidia", cursor="bad!cursor", limit=2)


def test_explicit_status_filter(service: ResearchService) -> None:
    result = service.list_relationships(
        company="nvidia", statuses={FactStatus.CONFIRMED}, limit=100
    )
    assert result.total == sum(
        item.fact_status == FactStatus.CONFIRMED
        for item in service.repo.relationships.values()
    )
    assert all(item.fact_status == FactStatus.CONFIRMED for item in result.items)


def test_unknown_partner_is_included_by_default_and_can_be_excluded(
    service: ResearchService,
) -> None:
    unknown_relationships = [
        item
        for item in service.repo.relationships.values()
        if item.fact_status == FactStatus.UNKNOWN
    ]
    company = (
        unknown_relationships[0].source_entity_id
        if unknown_relationships
        else "nvidia"
    )
    default = service.list_relationships(company=company, limit=100)
    without_unknown = service.list_relationships(
        company=company, include_unknown=False, limit=100
    )
    assert all(item.fact_status != FactStatus.UNKNOWN for item in without_unknown.items)
    assert default.total >= without_unknown.total
    if unknown_relationships:
        expected_visible_unknowns = sum(
            item.fact_status == FactStatus.UNKNOWN
            and company in {item.source_entity_id, item.target_entity_id}
            for item in unknown_relationships
        )
        assert default.total == without_unknown.total + expected_visible_unknowns


def test_snapshot_source_evidence_and_entity_references_exist(
    service: ResearchService,
) -> None:
    assert all(
        item.source_id in service.repo.sources
        for item in service.repo.evidence.values()
    )
    assert all(
        item.source_entity_id in service.repo.entities
        and item.target_entity_id in service.repo.entities
        and set(item.evidence_ids) <= set(service.repo.evidence)
        for item in service.repo.relationships.values()
    )

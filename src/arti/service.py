from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence, TypeVar

from .models import (
    CommercialDirectness,
    Entity,
    FactStatus,
    RelationDirection,
    RelationType,
    Relationship,
)
from .repository import SnapshotRepository

T = TypeVar("T")


class NotFoundError(LookupError):
    pass


class InvalidCursorError(ValueError):
    pass


@dataclass(frozen=True)
class Page:
    items: list
    next_cursor: str | None
    total: int
    limit: int


def encode_cursor(offset: int) -> str:
    payload = f"offset:{offset}".encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        prefix, value = raw.split(":", 1)
        if prefix != "offset":
            raise ValueError
        offset = int(value)
        if offset < 0:
            raise ValueError
        return offset
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError("cursor is malformed") from exc


def paginate(items: Sequence[T], limit: int, cursor: str | None) -> Page:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    offset = decode_cursor(cursor)
    if offset > len(items):
        raise InvalidCursorError("cursor is past the end of the result set")
    page_items = list(items[offset : offset + limit])
    next_offset = offset + len(page_items)
    next_cursor = encode_cursor(next_offset) if next_offset < len(items) else None
    return Page(page_items, next_cursor, len(items), limit)


def matches_product(relationship: Relationship, product: str) -> bool:
    """Match a frozen canonical scope ID or a retained human-readable label."""
    needle = product.casefold().strip()
    return needle == relationship.product_scope_id.casefold() or any(
        needle in scope.casefold() for scope in relationship.product_scopes
    )


class ResearchService:
    def __init__(self, repository: SnapshotRepository | None = None) -> None:
        self.repo = repository or SnapshotRepository()

    def resolve_entity(self, value: str) -> Entity:
        key = value.casefold().strip()
        for entity in self.repo.entities.values():
            identifiers = {entity.id, entity.legal_name, entity.display_name, *entity.aliases}
            identifiers.update(security.ticker for security in entity.securities)
            if key in {item.casefold() for item in identifiers}:
                return entity
        raise NotFoundError(f"company not found: {value}")

    def list_entities(
        self,
        *,
        q: str | None = None,
        listed_only: bool = True,
        limit: int = 20,
        cursor: str | None = None,
    ) -> Page:
        entities: Iterable[Entity] = self.repo.entities.values()
        if listed_only:
            entities = (item for item in entities if item.listing_status.value == "listed")
        if q:
            query = q.casefold()
            entities = (
                item
                for item in entities
                if query
                in " ".join(
                    [
                        item.id,
                        item.legal_name,
                        item.display_name,
                        *item.aliases,
                        *(security.ticker for security in item.securities),
                    ]
                ).casefold()
            )
        ordered = sorted(entities, key=lambda item: (item.display_name.casefold(), item.id))
        return paginate(ordered, limit, cursor)

    def list_relationships(
        self,
        *,
        company: str | None = None,
        relation_types: set[RelationType] | None = None,
        directions: set[RelationDirection] | None = None,
        statuses: set[FactStatus] | None = None,
        commercial_directness: set[CommercialDirectness] | None = None,
        min_confidence: int = 0,
        min_relevance: int = 0,
        product: str | None = None,
        as_of: date | None = None,
        include_unknown: bool = True,
        limit: int = 20,
        cursor: str | None = None,
    ) -> Page:
        relations: Iterable[Relationship] = self.repo.relationships.values()
        if company:
            entity = self.resolve_entity(company)
            relations = (
                item
                for item in relations
                if entity.id in {item.source_entity_id, item.target_entity_id}
            )
        if relation_types:
            relations = (item for item in relations if item.relation_type in relation_types)
        if directions:
            relations = (item for item in relations if item.direction in directions)
        if statuses:
            relations = (item for item in relations if item.fact_status in statuses)
        elif not include_unknown:
            relations = (item for item in relations if item.fact_status != FactStatus.UNKNOWN)
        if commercial_directness:
            relations = (
                item
                for item in relations
                if item.commercial_directness in commercial_directness
            )
        relations = (
            item
            for item in relations
            if item.confidence_score >= min_confidence
            and item.relevance_score >= min_relevance
        )
        if product:
            relations = (
                item
                for item in relations
                if matches_product(item, product)
            )
        if as_of:
            relations = (
                item
                for item in relations
                if (item.valid_from is None or item.valid_from <= as_of)
                and (item.valid_to is None or as_of <= item.valid_to)
                and item.as_of <= as_of
            )
        ordered = sorted(
            relations,
            key=lambda item: (-item.relevance_score, -item.confidence_score, item.id),
        )
        return paginate(ordered, limit, cursor)

    def get_relationship(self, relationship_id: str) -> Relationship:
        try:
            return self.repo.relationships[relationship_id]
        except KeyError as exc:
            raise NotFoundError(f"relationship not found: {relationship_id}") from exc

    def relationship_detail(self, relationship_id: str) -> dict:
        relationship = self.get_relationship(relationship_id)
        return {
            "relationship": relationship,
            "source_entity": self.repo.entities[relationship.source_entity_id],
            "target_entity": self.repo.entities[relationship.target_entity_id],
            "evidence": [
                {
                    "evidence": self.repo.evidence[evidence_id],
                    "source": self.repo.sources[
                        self.repo.evidence[evidence_id].source_id
                    ],
                }
                for evidence_id in relationship.evidence_ids
            ],
        }

    def list_evidence(
        self,
        *,
        relationship_id: str | None = None,
        publisher: str | None = None,
        source_family: str | None = None,
        published_from: date | None = None,
        published_to: date | None = None,
        human_verified: bool | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> Page:
        relationship_ids_by_evidence: dict[str, list[str]] = {
            evidence_id: [] for evidence_id in self.repo.evidence
        }
        for relationship in self.repo.relationships.values():
            for evidence_id in relationship.evidence_ids:
                relationship_ids_by_evidence[evidence_id].append(relationship.id)

        allowed_ids: set[str] | None = None
        if relationship_id:
            relationship = self.get_relationship(relationship_id)
            allowed_ids = set(relationship.evidence_ids)

        records: list[dict] = []
        for evidence in self.repo.evidence.values():
            if allowed_ids is not None and evidence.id not in allowed_ids:
                continue
            source = self.repo.sources[evidence.source_id]
            if publisher and publisher.casefold() not in source.publisher.casefold():
                continue
            if source_family and source_family.casefold() != source.source_family.casefold():
                continue
            if published_from and (
                source.published_at is None or source.published_at < published_from
            ):
                continue
            if published_to and (
                source.published_at is None or source.published_at > published_to
            ):
                continue
            if human_verified is not None and evidence.human_verified != human_verified:
                continue
            records.append(
                {
                    "evidence": evidence,
                    "source": source,
                    "relationship_ids": sorted(
                        relationship_ids_by_evidence[evidence.id]
                    ),
                }
            )
        records.sort(key=lambda item: item["evidence"].id)
        return paginate(records, limit, cursor)

    def get_evidence(self, evidence_id: str) -> dict:
        try:
            evidence = self.repo.evidence[evidence_id]
        except KeyError as exc:
            raise NotFoundError(f"evidence not found: {evidence_id}") from exc
        relationship_ids = sorted(
            relationship.id
            for relationship in self.repo.relationships.values()
            if evidence_id in relationship.evidence_ids
        )
        return {
            "evidence": evidence,
            "source": self.repo.sources[evidence.source_id],
            "relationship_ids": relationship_ids,
        }

    def graph(
        self,
        *,
        company: str,
        relation_types: set[RelationType] | None = None,
        directions: set[RelationDirection] | None = None,
        statuses: set[FactStatus] | None = None,
        commercial_directness: set[CommercialDirectness] | None = None,
        min_confidence: int = 0,
        min_relevance: int = 0,
        product: str | None = None,
        as_of: date | None = None,
        include_unknown: bool = True,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict:
        page = self.list_relationships(
            company=company,
            relation_types=relation_types,
            directions=directions,
            statuses=statuses,
            commercial_directness=commercial_directness,
            min_confidence=min_confidence,
            min_relevance=min_relevance,
            product=product,
            as_of=as_of,
            include_unknown=include_unknown,
            limit=limit,
            cursor=cursor,
        )
        relations = page.items
        entity_ids = {
            entity_id
            for relation in relations
            for entity_id in (relation.source_entity_id, relation.target_entity_id)
        }
        return {
            "as_of": self.repo.snapshot.meta.cutoff_at,
            "nodes": [self.repo.entities[item] for item in sorted(entity_ids)],
            "edges": relations,
            "truncated": page.next_cursor is not None,
            "next_cursor": page.next_cursor,
        }

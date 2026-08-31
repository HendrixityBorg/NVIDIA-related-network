from __future__ import annotations

from collections import defaultdict

from ..models import Entity, ListingStatus, Relationship
from .contracts import CounterpartyReviewTask, ResearchProfile
from .io import stable_id


def build_counterparty_tasks(
    profile: ResearchProfile,
    entities: list[Entity],
    relationships: list[Relationship],
) -> list[CounterpartyReviewTask]:
    entity_map = {item.id: item for item in entities}
    relation_ids: dict[str, list[str]] = defaultdict(list)
    for relation in relationships:
        for entity_id in (relation.source_entity_id, relation.target_entity_id):
            if entity_id != profile.target.id:
                relation_ids[entity_id].append(relation.id)

    tasks: list[CounterpartyReviewTask] = []
    target_terms = list(
        dict.fromkeys(
            [profile.target.display_name, profile.target.legal_name, *profile.target.aliases]
        )
    )
    for entity_id, ids in sorted(relation_ids.items()):
        entity = entity_map.get(entity_id)
        if entity is None or entity.listing_status != ListingStatus.LISTED:
            continue
        names = list(dict.fromkeys([entity.display_name, entity.legal_name, *entity.aliases]))
        securities = [
            f"{security.exchange}:{security.ticker}" for security in entity.securities
        ]
        tasks.append(
            CounterpartyReviewTask(
                id=stable_id("counterparty-review", profile.project_slug, entity_id),
                subject_entity_id=profile.target.id,
                counterparty=entity,
                observed_names=names,
                search_terms=[
                    f'"{name}" "{target}"'
                    for name in names[:3]
                    for target in target_terms[:3]
                ],
                jurisdictions=list(dict.fromkeys([*entity.listing_regions, *securities])),
                filing_forms=["annual report", "10-K", "20-F", "40-F", "local equivalent"],
                source_relationship_ids=sorted(set(ids)),
            )
        )
    return tasks

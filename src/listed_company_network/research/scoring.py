from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..models import FactStatus, RelationType, ScoreBreakdown


SOURCE_AUTHORITY = {
    "regulator_filing": 25,
    "company_filing": 25,
    "official_ir": 23,
    "official_product": 21,
    "official_news": 20,
    "counterparty_official": 20,
    "independent_tier1_news": 17,
    "independent_news": 13,
    "ecosystem_directory": 12,
    "aggregator": 6,
    "unknown": 3,
}


@dataclass(frozen=True)
class ScoreInputs:
    source_class: str
    explicitness: float
    entity_resolution: float
    independent_publishers: int
    newest_evidence_date: date | None
    cutoff_date: date
    quantified: bool
    relationship_type_specificity: float
    conflict_penalty: float = 0


def timeliness_points(newest: date | None, cutoff: date) -> float:
    if newest is None:
        return 2
    age = (cutoff - newest).days
    if age < 0:
        return 0
    if age <= 180:
        return 10
    if age <= 365:
        return 8
    if age <= 730:
        return 5
    return 2


def build_breakdown(inputs: ScoreInputs) -> ScoreBreakdown:
    return ScoreBreakdown(
        source_authority=SOURCE_AUTHORITY.get(inputs.source_class, 3),
        explicitness=max(0, min(25, inputs.explicitness)),
        entity_resolution=max(0, min(15, inputs.entity_resolution)),
        independence=max(0, min(15, inputs.independent_publishers * 5)),
        timeliness=timeliness_points(inputs.newest_evidence_date, inputs.cutoff_date),
        quantification=10 if inputs.quantified else 0,
        relationship_type_specificity=max(
            0, min(5, inputs.relationship_type_specificity)
        ),
        conflict_penalty=max(0, min(20, inputs.conflict_penalty)),
    )


def confidence_score(
    breakdown: ScoreBreakdown,
    status: FactStatus,
    relation_type: RelationType,
    *,
    low_confidence_partner: bool = False,
) -> int:
    cap = {FactStatus.CONFIRMED: 100, FactStatus.INFERRED: 69, FactStatus.UNKNOWN: 39}[
        status
    ]
    if status == FactStatus.INFERRED and relation_type in {
        RelationType.SUPPLIER,
        RelationType.CUSTOMER,
    }:
        cap = 59
    if low_confidence_partner:
        cap = 49 if status == FactStatus.INFERRED else 39
    return min(breakdown.raw_total, cap)

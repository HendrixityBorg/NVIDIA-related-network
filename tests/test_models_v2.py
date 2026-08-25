from datetime import date

import pytest
from pydantic import ValidationError

from arti.models import (
    FactStatus,
    RelationDirection,
    Relationship,
    RelationType,
    ScoreBreakdown,
    TemporalStatus,
)
from arti.service import matches_product


def relationship_payload(**overrides):
    payload = {
        "id": "rel-test",
        "source_entity_id": "counterparty",
        "target_entity_id": "nvidia",
        "relation_type": RelationType.SUPPLIER,
        "direction": RelationDirection.SUPPLIES_TO,
        "direction_explanation": "Counterparty is inferred to supply NVIDIA.",
        "product_scope_id": "accelerated-computing",
        "fact_status": FactStatus.INFERRED,
        "temporal_status": TemporalStatus.CURRENT,
        "as_of": date(2026, 8, 25),
        "confidence_score": 59,
        "relevance_score": 59,
        "confidence_breakdown": ScoreBreakdown(
            source_authority=25,
            explicitness=25,
            entity_resolution=15,
            independence=15,
            timeliness=10,
            quantification=10,
            relationship_type_specificity=5,
        ),
        "relevance_explanation": "Evidence-based confidence is used as relevance.",
        "evidence_ids": ["ev-test"],
    }
    payload.update(overrides)
    return payload


def test_inferred_supplier_is_capped_below_60():
    relationship = Relationship.model_validate(relationship_payload())
    assert relationship.confidence_score == 59
    assert relationship.product_scope_id == "accelerated-computing"


def test_product_filter_accepts_exact_frozen_canonical_scope_id():
    relationship = Relationship.model_validate(relationship_payload())
    assert matches_product(relationship, "accelerated-computing")
    assert not matches_product(relationship, "networking")


def test_inferred_supplier_rejects_score_above_cap():
    with pytest.raises(ValidationError, match="confidence_score must be 59"):
        Relationship.model_validate(relationship_payload(confidence_score=60))


def test_legacy_multi_scope_does_not_create_v2_multi_product_key():
    payload = relationship_payload(
        product_scope_id=None,
        product_scopes=["scope-a", "scope-b"],
    )
    relationship = Relationship.model_validate(payload)
    assert relationship.product_scope_id == "corporate_general"


def test_unknown_review_observation_is_exposed_only_as_capped_partner():
    breakdown = ScoreBreakdown(
        source_authority=20,
        explicitness=2,
        entity_resolution=10,
        independence=0,
        timeliness=5,
        quantification=0,
        relationship_type_specificity=2,
    )
    relationship = Relationship.model_validate(
        relationship_payload(
            source_entity_id="nvidia",
            target_entity_id="counterparty",
            relation_type=RelationType.PARTNER,
            direction=RelationDirection.PARTNERS_WITH,
            fact_status=FactStatus.UNKNOWN,
            confidence_score=39,
            relevance_score=39,
            confidence_breakdown=breakdown,
            origin_terminal_statuses=["approve_unknown"],
            inference_explanations=["Logo co-context only; no transaction is asserted."],
            low_confidence_partner_inclusion=True,
            evidence_ids=["ev-relation", "ev-parent"],
            relationship_evidence_ids=["ev-relation"],
            entity_resolution_evidence_ids=["ev-parent"],
        )
    )
    assert relationship.confidence_score == 39


def test_needs_more_partner_uses_49_cap_not_generic_inferred_cap():
    breakdown = ScoreBreakdown(
        source_authority=20,
        explicitness=5,
        entity_resolution=15,
        independence=0,
        timeliness=7,
        quantification=0,
        relationship_type_specificity=2,
    )
    relationship = Relationship.model_validate(
        relationship_payload(
            source_entity_id="nvidia",
            target_entity_id="counterparty",
            relation_type=RelationType.PARTNER,
            direction=RelationDirection.PARTNERS_WITH,
            fact_status=FactStatus.INFERRED,
            confidence_score=49,
            relevance_score=49,
            confidence_breakdown=breakdown,
            origin_terminal_statuses=["needs_more_evidence"],
            inference_explanations=["Relationship direction remains unproven."],
            low_confidence_partner_inclusion=True,
            evidence_ids=["ev-relation"],
            relationship_evidence_ids=["ev-relation"],
        )
    )
    assert relationship.confidence_score == 49


def test_merged_low_confidence_classes_use_inferred_partner_cap():
    breakdown = ScoreBreakdown(
        source_authority=20,
        explicitness=5,
        entity_resolution=15,
        independence=0,
        timeliness=7,
        quantification=0,
        relationship_type_specificity=2,
    )
    relationship = Relationship.model_validate(
        relationship_payload(
            source_entity_id="nvidia",
            target_entity_id="counterparty",
            relation_type=RelationType.PARTNER,
            direction=RelationDirection.PARTNERS_WITH,
            fact_status=FactStatus.INFERRED,
            confidence_score=49,
            relevance_score=49,
            confidence_breakdown=breakdown,
            origin_terminal_statuses=["approve_unknown", "needs_more_evidence"],
            inference_explanations=["Two low-confidence terminal observations were merged."],
            low_confidence_partner_inclusion=True,
            evidence_ids=["ev-relation"],
            relationship_evidence_ids=["ev-relation"],
        )
    )
    assert relationship.confidence_score == 49


def test_merged_low_confidence_classes_can_remain_unknown():
    breakdown = ScoreBreakdown(
        source_authority=20,
        explicitness=2,
        entity_resolution=10,
        independence=0,
        timeliness=5,
        quantification=0,
        relationship_type_specificity=2,
    )
    relationship = Relationship.model_validate(
        relationship_payload(
            source_entity_id="nvidia",
            target_entity_id="counterparty",
            relation_type=RelationType.PARTNER,
            direction=RelationDirection.PARTNERS_WITH,
            fact_status=FactStatus.UNKNOWN,
            confidence_score=39,
            relevance_score=39,
            confidence_breakdown=breakdown,
            origin_terminal_statuses=["approve_unknown", "needs_more_evidence"],
            inference_explanations=["The merged evidence remains unknown."],
            low_confidence_partner_inclusion=True,
            evidence_ids=["ev-relation"],
            relationship_evidence_ids=["ev-relation"],
        )
    )
    assert relationship.confidence_score == 39

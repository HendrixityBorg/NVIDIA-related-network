from datetime import date

import pytest
from pydantic import ValidationError

from arti.research_policy import (
    ResearchedEntityResolution,
    low_confidence_partner_profile,
    low_confidence_partner_score_is_valid,
    missing_researched_candidate_ids,
)


def evidence(evidence_id: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "url": f"https://example.com/{evidence_id}",
        "publisher": "Official Exchange",
        "retrieved_at": "2026-08-25T12:00:00Z",
        "locator": "issuer header",
        "supports": "Issuer identity and comparable market capitalization.",
    }


def base_resolution(**overrides) -> dict:
    row = {
        "resolution_id": "resolution-geely",
        "candidate_name": "Geely",
        "candidate_review_ids": ["candidate-geely"],
        "observation_ids": ["obs-geely"],
        "research_status": "researched_terminal",
        "terminal_category": "resolved_inferred_parent",
        "selected_entity_id": "geely_auto",
        "resolution_confidence": 60,
        "inferred_entity_resolution": True,
        "exact_alias_search_outcome": "ambiguous",
        "research_methods": ["official issuer and parent ownership research"],
        "research_evidence": [evidence("ev-parent")],
        "listed_entity_options": [],
        "rationale": "Source context most likely denotes the listed automotive issuer, with ambiguity retained.",
    }
    row.update(overrides)
    return row


def test_low_confidence_terminal_statuses_become_partner_claim_profiles():
    assert low_confidence_partner_profile("approve_unknown") == {
        "relationship_type": "partner",
        "direction": "partners_with",
        "fact_status": "unknown",
        "confidence_cap": 39,
    }
    assert low_confidence_partner_profile("needs_more_evidence")["confidence_cap"] == 49
    with pytest.raises(ValueError):
        low_confidence_partner_profile("reject")


def test_low_confidence_claim_score_matches_breakdown_cap_and_fact_status():
    claim = {
        "relationship_type": "partner",
        "direction": "partners_with",
        "fact_status": "unknown",
        "confidence_score": 39,
        "confidence_breakdown": {
            "source_authority": 20,
            "explicitness": 5,
            "entity_resolution": 15,
            "independence": 0,
            "timeliness": 8,
            "quantification": 0,
            "relationship_type_specificity": 2,
            "conflict_penalty": 0,
        },
        "origin_terminal_statuses": ["approve_unknown"],
        "low_confidence_partner_inclusion": True,
    }
    assert low_confidence_partner_score_is_valid(claim)
    claim["fact_status"] = "inferred"
    assert not low_confidence_partner_score_is_valid(claim)


def test_inferred_entity_resolution_is_allowed_but_capped():
    row = ResearchedEntityResolution.model_validate(base_resolution())
    assert row.selected_entity_id == "geely_auto"
    with pytest.raises(ValidationError, match="capped at 69"):
        ResearchedEntityResolution.model_validate(
            base_resolution(resolution_confidence=70)
        )


def test_exact_alias_miss_alone_is_not_a_terminal_research_category():
    with pytest.raises(ValidationError, match="exact-alias miss is not terminal"):
        ResearchedEntityResolution.model_validate(
            base_resolution(
                terminal_category="unresolved_after_research",
                selected_entity_id=None,
                resolution_confidence=0,
                inferred_entity_resolution=False,
                exact_alias_search_outcome="miss",
                research_methods=["exact alias search"],
            )
        )


def test_largest_listed_parent_requires_comparable_evidenced_market_caps():
    options = [
        {
            "entity_id": "issuer-large",
            "security_id": "XHKG:0001",
            "relationship_to_observed_name": "listed parent candidate",
            "market_cap": 200,
            "market_cap_currency": "USD",
            "market_cap_as_of": date(2026, 8, 25),
            "market_cap_evidence_ids": ["ev-large"],
        },
        {
            "entity_id": "issuer-small",
            "security_id": "XTKS:0002",
            "relationship_to_observed_name": "listed affiliate candidate",
            "market_cap": 100,
            "market_cap_currency": "USD",
            "market_cap_as_of": date(2026, 8, 25),
            "market_cap_evidence_ids": ["ev-small"],
        },
    ]
    row = ResearchedEntityResolution.model_validate(
        base_resolution(
            terminal_category="resolved_largest_listed_parent",
            selected_entity_id="issuer-large",
            exact_alias_search_outcome="ambiguous",
            research_evidence=[evidence("ev-large"), evidence("ev-small")],
            listed_entity_options=options,
        )
    )
    assert row.selected_entity_id == "issuer-large"

    with pytest.raises(ValidationError, match="largest evidenced market cap"):
        ResearchedEntityResolution.model_validate(
            base_resolution(
                terminal_category="resolved_largest_listed_parent",
                selected_entity_id="issuer-small",
                exact_alias_search_outcome="ambiguous",
                research_evidence=[evidence("ev-large"), evidence("ev-small")],
                listed_entity_options=options,
            )
        )
    tied_options = [dict(item, market_cap=200) for item in options]
    with pytest.raises(ValidationError, match="ties remain ambiguous"):
        ResearchedEntityResolution.model_validate(
            base_resolution(
                terminal_category="resolved_largest_listed_parent",
                selected_entity_id="issuer-large",
                exact_alias_search_outcome="ambiguous",
                research_evidence=[evidence("ev-large"), evidence("ev-small")],
                listed_entity_options=tied_options,
            )
        )


def test_exact_alias_miss_candidate_requires_researched_terminal_coverage():
    candidates = [
        {
            "candidate_id": "candidate-geely",
            "candidate_name": "Geely",
            "resolution_status": "unresolved_no_safe_exact_listed_match",
            "observations": [{"observation_id": "obs-geely"}],
        }
    ]
    assert missing_researched_candidate_ids(candidates, []) == ["candidate-geely"]
    researched = [ResearchedEntityResolution.model_validate(base_resolution())]
    assert missing_researched_candidate_ids(candidates, researched) == []

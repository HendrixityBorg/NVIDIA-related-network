import json
from pathlib import Path

import pytest

from direction_policy import (
    PolicyError,
    independent_origin_count,
    review_candidate,
    validate_candidate,
    validate_decision,
)


HERE = Path(__file__).resolve().parent


def fixtures():
    return [
        json.loads(line)
        for line in (HERE / "direction_fixtures.jsonl").read_text().splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize("candidate", fixtures())
def test_direction_fixtures(candidate):
    decision = review_candidate(candidate)
    validate_decision(decision)
    assert "partner" in decision["existing_roles_retained"]
    if "expected_claim_count" in candidate:
        assert len(decision["new_claims"]) == candidate["expected_claim_count"]
    else:
        assert len(decision["new_claims"]) == 1
        claim = decision["new_claims"][0]
        for key, expected in candidate["expected"].items():
            assert claim[key] == expected


def test_directness_and_fact_status_are_orthogonal():
    indirect = next(x for x in fixtures() if x["candidate_id"] == "fixture-reg-indirect")
    claim = review_candidate(indirect)["new_claims"][0]
    assert claim["directness"] == "indirect"
    assert claim["fact_status"] == "confirmed"


def test_news_can_never_confirm_supplier_or_customer():
    for candidate in fixtures():
        if candidate["source"]["source_kind"] in {"company_news", "third_party_news"}:
            assert all(
                claim["fact_status"] == "inferred"
                for claim in review_candidate(candidate)["new_claims"]
            )


def test_partner_and_other_roles_are_never_deleted():
    dual = next(x for x in fixtures() if x["candidate_id"] == "fixture-dual-role")
    decision = review_candidate(dual)
    assert set(decision["existing_roles_retained"]) == {"partner", "investee"}
    assert {x["relationship_type"] for x in decision["new_claims"]} == {"supplier", "customer"}


def test_unknown_product_defaults_to_corporate_general():
    indirect = next(x for x in fixtures() if x["candidate_id"] == "fixture-reg-indirect")
    assert review_candidate(indirect)["new_claims"][0]["product_scope_id"] == "corporate_general"


def test_reposts_do_not_increase_independence():
    sources = [
        {"publisher": "Wire A", "published_at": "2026-01-01", "evidence_excerpt": "x", "origin_publication_id": "origin-1"},
        {"publisher": "Portal B", "published_at": "2026-01-02", "evidence_excerpt": "x", "origin_publication_id": "origin-1"},
        {"publisher": "Newspaper C", "published_at": "2026-01-03", "evidence_excerpt": "independent", "origin_publication_id": "origin-2"},
    ]
    assert independent_origin_count(sources) == 2


def test_out_of_window_rejected():
    candidate = dict(fixtures()[0])
    candidate["source"] = dict(candidate["source"], published_at="2024-12-31")
    with pytest.raises(PolicyError, match="outside"):
        validate_candidate(candidate)


def test_access_control_bypass_rejected():
    candidate = dict(fixtures()[0])
    candidate["source"] = dict(candidate["source"], access_control_bypassed=True)
    with pytest.raises(PolicyError, match="bypass"):
        validate_candidate(candidate)


def test_non_public_source_rejected():
    candidate = dict(fixtures()[0])
    candidate["source"] = dict(candidate["source"], access_mode="login_required")
    with pytest.raises(PolicyError, match="public"):
        validate_candidate(candidate)


def test_input_must_retain_existing_partner_role():
    candidate = dict(fixtures()[0], existing_roles=["peer"])
    with pytest.raises(PolicyError, match="Partner"):
        validate_candidate(candidate)


def test_research_window_boundaries_are_inclusive():
    candidate = dict(fixtures()[0])
    candidate["source"] = dict(candidate["source"], published_at="2025-01-01")
    validate_candidate(candidate)
    candidate["source"] = dict(candidate["source"], published_at="2026-08-25")
    validate_candidate(candidate)

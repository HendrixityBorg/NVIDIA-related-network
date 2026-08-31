"""Release policy for low-confidence relationships and researched entity resolution."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


LOW_CONFIDENCE_PARTNER_CAPS = {
    "approve_unknown": 39,
    "needs_more_evidence": 49,
}


class ResearchedTerminalCategory(StrEnum):
    RESOLVED_EXACT = "resolved_exact"
    RESOLVED_INFERRED_PARENT = "resolved_inferred_parent"
    RESOLVED_LARGEST_LISTED_PARENT = "resolved_largest_listed_parent"
    UNRESOLVED_AFTER_RESEARCH = "unresolved_after_research"
    AMBIGUOUS_AFTER_RESEARCH = "ambiguous_after_research"
    NON_ENTITY = "non_entity"
    PRIVATE_OR_DELISTED = "private_or_delisted"


class ResearchEvidence(BaseModel):
    evidence_id: str
    url: HttpUrl
    publisher: str
    retrieved_at: datetime
    locator: str
    supports: str


class ListedEntityOption(BaseModel):
    entity_id: str
    security_id: str
    relationship_to_observed_name: str
    market_cap: float | None = Field(default=None, gt=0)
    market_cap_currency: str | None = None
    market_cap_as_of: date | None = None
    market_cap_evidence_ids: list[str] = Field(default_factory=list)


class ResearchedEntityResolution(BaseModel):
    resolution_id: str
    candidate_name: str
    candidate_review_ids: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(min_length=1)
    research_status: Literal["researched_terminal"]
    terminal_category: ResearchedTerminalCategory
    selected_entity_id: str | None = None
    resolution_confidence: int = Field(ge=0, le=100)
    inferred_entity_resolution: bool
    exact_alias_search_outcome: Literal["match", "miss", "ambiguous"]
    research_methods: list[str] = Field(min_length=1)
    research_evidence: list[ResearchEvidence] = Field(min_length=1)
    listed_entity_options: list[ListedEntityOption] = Field(default_factory=list)
    rationale: str = Field(min_length=20)

    @model_validator(mode="after")
    def validate_terminal_research(self) -> "ResearchedEntityResolution":
        resolved = {
            ResearchedTerminalCategory.RESOLVED_EXACT,
            ResearchedTerminalCategory.RESOLVED_INFERRED_PARENT,
            ResearchedTerminalCategory.RESOLVED_LARGEST_LISTED_PARENT,
        }
        if self.terminal_category in resolved and not self.selected_entity_id:
            raise ValueError("resolved terminal category requires selected_entity_id")
        if self.terminal_category not in resolved and self.selected_entity_id:
            raise ValueError("unresolved/rejected terminal category cannot select an entity")

        method_text = " ".join(self.research_methods).casefold()
        if self.exact_alias_search_outcome == "miss" and not any(
            token in method_text for token in ("issuer", "exchange", "parent", "ownership")
        ):
            raise ValueError(
                "exact-alias miss is not terminal without issuer/exchange/parent research"
            )

        inferred_categories = {
            ResearchedTerminalCategory.RESOLVED_INFERRED_PARENT,
            ResearchedTerminalCategory.RESOLVED_LARGEST_LISTED_PARENT,
        }
        if self.terminal_category in inferred_categories:
            if not self.inferred_entity_resolution:
                raise ValueError("inferred terminal category must retain inferred status")
            if self.resolution_confidence > 69:
                raise ValueError("inferred entity resolution confidence is capped at 69")
        elif self.inferred_entity_resolution:
            raise ValueError("inferred_entity_resolution is only valid for inferred categories")

        if self.terminal_category == ResearchedTerminalCategory.RESOLVED_EXACT:
            if self.exact_alias_search_outcome != "match":
                raise ValueError("resolved_exact requires an exact alias match")

        if self.terminal_category == ResearchedTerminalCategory.RESOLVED_LARGEST_LISTED_PARENT:
            if len(self.listed_entity_options) < 2:
                raise ValueError("largest-listed-parent selection requires at least two options")
            evidence_ids = {item.evidence_id for item in self.research_evidence}
            currencies = {item.market_cap_currency for item in self.listed_entity_options}
            dates = {item.market_cap_as_of for item in self.listed_entity_options}
            if None in currencies or len(currencies) != 1 or None in dates or len(dates) != 1:
                raise ValueError("market-cap comparison requires one currency and one as-of date")
            if any(item.market_cap is None for item in self.listed_entity_options):
                raise ValueError("every listed option requires market cap")
            if any(
                not item.market_cap_evidence_ids
                or not set(item.market_cap_evidence_ids).issubset(evidence_ids)
                for item in self.listed_entity_options
            ):
                raise ValueError("every market cap requires cited research evidence")
            largest = max(self.listed_entity_options, key=lambda item: item.market_cap or 0)
            if sum(
                item.market_cap == largest.market_cap
                for item in self.listed_entity_options
            ) != 1:
                raise ValueError("largest market cap must be unique; ties remain ambiguous")
            if largest.entity_id != self.selected_entity_id:
                raise ValueError("selected entity must have the largest evidenced market cap")
        return self


def low_confidence_partner_profile(origin_terminal_status: str) -> dict[str, object]:
    """Map retained terminal review status to a conservative partner claim profile."""
    if origin_terminal_status not in LOW_CONFIDENCE_PARTNER_CAPS:
        raise ValueError(f"not a low-confidence partner status: {origin_terminal_status}")
    return {
        "relationship_type": "partner",
        "direction": "partners_with",
        "fact_status": (
            "unknown" if origin_terminal_status == "approve_unknown" else "inferred"
        ),
        "confidence_cap": LOW_CONFIDENCE_PARTNER_CAPS[origin_terminal_status],
    }


def low_confidence_partner_score_is_valid(claim: dict) -> bool:
    if not claim.get("low_confidence_partner_inclusion"):
        return True
    statuses = claim.get("origin_terminal_statuses") or []
    low_statuses = [status for status in statuses if status in LOW_CONFIDENCE_PARTNER_CAPS]
    if not low_statuses:
        return False
    expected_profile = low_confidence_partner_profile(
        "approve_unknown" if "approve_unknown" in low_statuses else "needs_more_evidence"
    )
    cap = min(LOW_CONFIDENCE_PARTNER_CAPS[status] for status in low_statuses)
    breakdown = claim.get("confidence_breakdown") or {}
    raw_total = sum(float(value or 0) for value in breakdown.values())
    expected_score = min(cap, int(round(raw_total)))
    return bool(
        claim.get("relationship_type") == expected_profile["relationship_type"]
        and claim.get("direction") == expected_profile["direction"]
        and claim.get("fact_status") == expected_profile["fact_status"]
        and claim.get("confidence_score") == expected_score
        and claim.get("confidence_score") <= cap
    )


RESEARCH_REQUIRED_RESOLUTION_STATUSES = {
    "unresolved_no_safe_exact_listed_match",
    "ambiguous_multiple_sec_issuers",
    "ambiguous_existing_exact_alias",
    "identity_resolved_listing_not_revalidated",
}


def missing_researched_candidate_ids(
    candidate_rows: list[dict],
    researched_rows: list[ResearchedEntityResolution],
) -> list[str]:
    """Return exact/ambiguous issuer candidates lacking a researched terminal row."""
    covered_candidate_ids = {
        candidate_id
        for row in researched_rows
        for candidate_id in row.candidate_review_ids
    }
    covered_observation_ids = {
        observation_id
        for row in researched_rows
        for observation_id in row.observation_ids
    }
    missing: list[str] = []
    for candidate in candidate_rows:
        if candidate.get("resolution_status") not in RESEARCH_REQUIRED_RESOLUTION_STATUSES:
            continue
        candidate_id = candidate.get("candidate_id") or ""
        observation_ids = {
            item.get("observation_id")
            for item in candidate.get("observations", [])
            if item.get("observation_id")
        }
        if candidate_id in covered_candidate_ids:
            continue
        if observation_ids and observation_ids.issubset(covered_observation_ids):
            continue
        missing.append(candidate_id or candidate.get("candidate_name") or "<unnamed>")
    return sorted(missing)

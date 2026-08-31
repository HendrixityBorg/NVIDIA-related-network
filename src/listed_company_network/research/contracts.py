from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from ..models import Entity, RelationDirection, RelationType


class SourceFamily(StrEnum):
    ANNUAL_FILING = "annual_filing"
    PORTFOLIO_FILING = "portfolio_filing"
    INVESTOR_PRESENTATIONS = "investor_presentations"
    OFFICIAL_ARTICLES = "official_articles"
    PRODUCT_SOLUTIONS = "product_solutions"
    ECOSYSTEM_DIRECTORY = "ecosystem_directory"
    THIRD_PARTY_NEWS = "third_party_news"
    COUNTERPARTY_REGULATORY = "counterparty_regulatory"
    PEER_RESEARCH = "peer_research"


class Requirement(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    IF_APPLICABLE = "if_applicable"


class CompletionStatus(StrEnum):
    COMPLETE = "complete"
    NOT_FOUND = "not_found_after_documented_search"
    NOT_APPLICABLE = "not_applicable"
    ACCESS_BLOCKED = "access_blocked"
    INCOMPLETE = "incomplete"
    ADAPTER_REQUIRED = "adapter_required"


class DiscoveryDecision(StrEnum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Officiality(StrEnum):
    FIRST_PARTY = "first_party"
    REGULATOR_OR_EXCHANGE = "regulator_or_exchange"
    INDEPENDENT_MEDIA = "independent_media"
    SYNDICATED_OR_AGGREGATED = "syndicated_or_aggregated"
    UNKNOWN = "unknown"


class FrontierState(StrEnum):
    PROCESSED = "processed"
    PROCESSED_NO_CANDIDATE = "processed_no_candidate"
    REDIRECTED = "redirected"
    ACCESS_BLOCKED = "access_blocked"
    EXCLUDED = "excluded"
    FAILED = "failed"


class ReviewTerminal(StrEnum):
    RELATIONSHIP_CONFIRMED = "relationship_confirmed"
    MENTION_DIRECTION_UNKNOWN = "mention_found_but_direction_unknown"
    MENTION_NOT_RELATIONSHIP = "mention_found_not_relationship"
    NO_EXACT_MENTION = "no_exact_mention"
    FILINGS_UNAVAILABLE = "filings_not_publicly_accessible"
    NO_FILINGS_IN_WINDOW = "no_filings_in_window"
    IDENTITY_AMBIGUOUS = "issuer_identity_ambiguous"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class EvidenceEligibility(StrEnum):
    PRIMARY = "primary"
    CORROBORATING = "corroborating"
    LEAD_ONLY = "lead_only"


class ResearchSecurity(BaseModel):
    ticker: str
    exchange: str
    listing_region: str
    listing_region_code: str = Field(min_length=2, max_length=2)
    cik: str | None = None
    isin: str | None = None
    cusip: str | None = None
    mic: str | None = None
    primary: bool = True
    status_at_cutoff: str = "listed"
    security_type: str = "common_equity"


class SubjectIdentity(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    legal_name: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    country: str | None = None
    jurisdiction: str
    securities: list[ResearchSecurity] = Field(min_length=1)
    official_domains: list[str] = Field(default_factory=list)
    investor_relations_urls: list[HttpUrl] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_securities(self) -> "SubjectIdentity":
        keys = [(item.exchange.casefold(), item.ticker.casefold()) for item in self.securities]
        if len(keys) != len(set(keys)):
            raise ValueError("subject securities must have unique exchange+ticker pairs")
        return self


class SourcePolicy(BaseModel):
    family: SourceFamily
    requirement: Requirement
    lookback_years: int | None = Field(default=None, ge=1, le=20)
    forms: list[str] = Field(default_factory=list)
    discovery_terms: list[str] = Field(default_factory=list)
    accepted_terminal_states: list[CompletionStatus] = Field(default_factory=list)

    @model_validator(mode="after")
    def default_terminals(self) -> "SourcePolicy":
        if not self.accepted_terminal_states:
            if self.requirement == Requirement.REQUIRED:
                self.accepted_terminal_states = [CompletionStatus.COMPLETE]
            elif self.requirement == Requirement.IF_APPLICABLE:
                self.accepted_terminal_states = [
                    CompletionStatus.COMPLETE,
                    CompletionStatus.NOT_APPLICABLE,
                ]
            else:
                self.accepted_terminal_states = [
                    CompletionStatus.COMPLETE,
                    CompletionStatus.NOT_FOUND,
                    CompletionStatus.NOT_APPLICABLE,
                ]
        return self


def default_source_policies() -> list[SourcePolicy]:
    return [
        SourcePolicy(
            family=SourceFamily.ANNUAL_FILING,
            requirement=Requirement.REQUIRED,
            forms=["10-K", "20-F", "40-F", "annual_report", "local_equivalent"],
        ),
        SourcePolicy(
            family=SourceFamily.PORTFOLIO_FILING,
            requirement=Requirement.IF_APPLICABLE,
            forms=["13F-HR", "13F-HR/A", "local_equivalent"],
        ),
        SourcePolicy(
            family=SourceFamily.INVESTOR_PRESENTATIONS,
            requirement=Requirement.REQUIRED,
            lookback_years=2,
        ),
        SourcePolicy(
            family=SourceFamily.OFFICIAL_ARTICLES,
            requirement=Requirement.REQUIRED,
            lookback_years=2,
        ),
        SourcePolicy(
            family=SourceFamily.PRODUCT_SOLUTIONS,
            requirement=Requirement.REQUIRED,
        ),
        SourcePolicy(
            family=SourceFamily.ECOSYSTEM_DIRECTORY,
            requirement=Requirement.IF_APPLICABLE,
            accepted_terminal_states=[
                CompletionStatus.COMPLETE,
                CompletionStatus.NOT_FOUND,
                CompletionStatus.NOT_APPLICABLE,
            ],
        ),
        SourcePolicy(
            family=SourceFamily.THIRD_PARTY_NEWS,
            requirement=Requirement.REQUIRED,
            lookback_years=2,
        ),
        SourcePolicy(
            family=SourceFamily.COUNTERPARTY_REGULATORY,
            requirement=Requirement.REQUIRED,
            lookback_years=2,
        ),
        SourcePolicy(
            family=SourceFamily.PEER_RESEARCH,
            requirement=Requirement.REQUIRED,
        ),
    ]


class ResearchProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    project_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    target: SubjectIdentity
    cutoff_at: datetime
    evidence_start_date: date
    snapshot_version: str
    languages: list[str] = Field(default_factory=lambda: ["en"])
    listed_counterparties_only: bool = True
    peer_granularity: str = "top_level_product_category"
    investment_scope: str = "subject_investments_only"
    source_policies: list[SourcePolicy] = Field(default_factory=default_source_policies)
    coverage: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    disclaimer: str = "Research output only; not investment advice."

    @model_validator(mode="after")
    def validate_profile(self) -> "ResearchProfile":
        families = [item.family for item in self.source_policies]
        if len(families) != len(set(families)):
            raise ValueError("source policy families must be unique")
        if self.evidence_start_date > self.cutoff_at.date():
            raise ValueError("evidence_start_date must not be after cutoff_at")
        return self

    def source_policy(self, family: SourceFamily) -> SourcePolicy:
        for policy in self.source_policies:
            if policy.family == family:
                return policy
        raise KeyError(f"missing source policy: {family}")


class SourceCandidate(BaseModel):
    id: str
    family: SourceFamily
    url: HttpUrl
    publisher: str | None = None
    title: str | None = None
    discovered_via: str
    discovery_query: str | None = None
    officiality: Officiality
    decision: DiscoveryDecision = DiscoveryDecision.CANDIDATE
    decision_reason: str
    adapter: str | None = None
    discovered_at: datetime
    robots_url: HttpUrl | None = None
    access_notes: str | None = None


class SearchQueryRecord(BaseModel):
    id: str
    family: SourceFamily
    query: str
    purpose: str
    target_entity_id: str
    provider: str = "agent_web_search"
    status: str = "planned"
    executed_at: datetime | None = None
    result_count: int | None = Field(default=None, ge=0)
    notes: str | None = None


class FrontierRecord(BaseModel):
    id: str
    family: SourceFamily
    url: HttpUrl
    publisher: str
    state: FrontierState
    retrieved_at: datetime | None = None
    published_at: date | None = None
    evidence_locator: str
    access_notes: str
    content_sha256: str | None = None
    local_snapshot_path: str | None = None
    terminal_reason: str | None = None


class StageReport(BaseModel):
    stage: SourceFamily
    status: CompletionStatus
    expected: int | None = Field(default=None, ge=0)
    processed: int = Field(default=0, ge=0)
    terminal: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)
    generated_at: datetime
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self) -> "StageReport":
        if self.status == CompletionStatus.COMPLETE and self.pending:
            raise ValueError("complete stage cannot have pending rows")
        if self.expected is not None and self.terminal > self.expected:
            raise ValueError("terminal count cannot exceed expected count")
        return self


class ThirdPartyNewsObservation(BaseModel):
    id: str
    source_url: HttpUrl
    original_publisher: str
    published_at: date | None = None
    retrieved_at: datetime
    discovery_query_id: str
    syndication_group_id: str | None = None
    is_original_reporting: bool
    access_status: str
    evidence_eligibility: EvidenceEligibility
    entity_names_raw: list[str] = Field(default_factory=list)
    relationship_hints: list[RelationType] = Field(default_factory=list)
    direction_hint: RelationDirection = RelationDirection.UNKNOWN
    product_context: list[str] = Field(default_factory=list)
    locator: str
    excerpt: str | None = None
    cooccurrence_warning: bool = True
    notes: str | None = None


class CounterpartyReviewTask(BaseModel):
    id: str
    subject_entity_id: str
    counterparty: Entity
    observed_names: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    filing_forms: list[str] = Field(default_factory=list)
    source_relationship_ids: list[str] = Field(default_factory=list)
    required_outputs: list[str] = Field(
        default_factory=lambda: ["source_frontier", "evidence", "decision"]
    )


class CounterpartyReviewDecision(BaseModel):
    id: str
    task_id: str
    counterparty_entity_id: str
    terminal_status: ReviewTerminal
    reviewed_at: datetime
    reviewed_sources: int = Field(ge=0)
    exact_mentions: int = Field(ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    rationale: str


class AgentTask(BaseModel):
    id: str
    agent: str
    objective: str
    profile_path: str
    input_paths: list[str]
    output_paths: list[str]
    completion_requirements: list[str]
    legal_access_rules: list[str]
    depends_on: list[str] = Field(default_factory=list)
    status: str = "planned"


class ValidationReport(BaseModel):
    pass_: bool = Field(alias="pass")
    release_ready: bool
    generated_at: datetime
    errors: list[str]
    warnings: list[str]
    counts: dict[str, int]
    stage_statuses: dict[str, str]
    checks: dict[str, bool]
    limitations: list[str] = Field(default_factory=list)


class CaseManifest(BaseModel):
    case_id: str
    frozen_source_commit: str
    frozen_tree_id: str
    expected_tracked_files: int
    legacy_root: str
    subject_entity_id: str
    cutoff_at: datetime
    snapshot_path: str
    expected_counts: dict[str, int]
    expected_relation_counts: dict[str, int]
    key_artifact_sha256: dict[str, str]
    regulatory_reverse_review: dict[str, Any]
    disclaimer: str

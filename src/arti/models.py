from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class RelationType(StrEnum):
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    PARTNER = "partner"
    INVESTOR_OR_INVESTEE = "investor_or_investee"
    PEER = "peer"


class RelationDirection(StrEnum):
    SUPPLIES_TO = "supplies_to"
    SELLS_TO = "sells_to"
    BUYS_FROM = "buys_from"
    USES_OR_BUYS_FROM = "uses_or_buys_from"
    PARTNERS_WITH = "partners_with"
    INVESTS_IN = "invests_in"
    COMPETES_WITH = "competes_with"
    UNKNOWN = "unknown"


class FactStatus(StrEnum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class CommercialDirectness(StrEnum):
    """Whether the commercial flow is direct, indirect, both, or unresolved."""

    DIRECT = "direct"
    INDIRECT = "indirect"
    BOTH = "both"
    UNCLEAR = "unclear"
    NOT_APPLICABLE = "not_applicable"


class EvidenceRole(StrEnum):
    PRIMARY = "primary"
    CORROBORATING = "corroborating"
    LEAD_ONLY = "lead_only"


class TemporalStatus(StrEnum):
    CURRENT = "current"
    POINT_IN_TIME = "point_in_time"
    HISTORICAL = "historical"
    PLANNED = "planned"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class ListingStatus(StrEnum):
    LISTED = "listed"
    PRIVATE = "private"
    DELISTED = "delisted"
    UNKNOWN = "unknown"


class SecurityIdentifier(BaseModel):
    ticker: str
    exchange: str
    listing_region: str
    listing_region_code: str = Field(min_length=2, max_length=2)
    cik: str | None = None
    cusip: str | None = None
    isin: str | None = None
    mic: str | None = None
    primary: bool | None = None
    status_at_cutoff: str | None = None
    security_type: str = "common_equity"


class Entity(BaseModel):
    id: str
    legal_name: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    country: str | None = None
    listing_status: ListingStatus
    listing_regions: list[str] = Field(min_length=1)
    securities: list[SecurityIdentifier] = Field(default_factory=list)
    ultimate_parent_id: str | None = None
    notes: str | None = None


class AccessPolicy(BaseModel):
    access: str
    login_required: bool = False
    paywall: bool = False
    robots_checked_at: datetime | None = None
    redistribution: str
    notes: str | None = None


class Source(BaseModel):
    id: str
    url: HttpUrl
    publisher: str
    title: str
    source_type: str
    published_at: date | None = None
    retrieved_at: datetime
    access_policy: AccessPolicy
    content_sha256: str | None = None
    source_family: str


class Evidence(BaseModel):
    id: str
    source_id: str
    locator: str
    excerpt: str | None = None
    visual_description: str | None = None
    supports: str
    inference_basis: list[str] = Field(default_factory=list)
    human_verified: bool
    notes: str | None = None


class ScoreBreakdown(BaseModel):
    source_authority: float = Field(ge=0, le=25)
    explicitness: float = Field(ge=0, le=25)
    entity_resolution: float = Field(ge=0, le=15)
    independence: float = Field(ge=0, le=15)
    timeliness: float = Field(ge=0, le=10)
    quantification: float = Field(ge=0, le=10)
    relationship_type_specificity: float = Field(default=0, ge=0, le=5)
    conflict_penalty: float = Field(default=0, ge=0, le=20)

    @property
    def raw_total(self) -> int:
        return round(
            min(
                100,
                max(
                    0,
                    self.source_authority
                    + self.explicitness
                    + self.entity_resolution
                    + self.independence
                    + self.timeliness
                    + self.quantification
                    + self.relationship_type_specificity
                    - self.conflict_penalty,
                ),
            )
        )


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: RelationType
    direction: RelationDirection = RelationDirection.UNKNOWN
    direction_explanation: str
    commercial_directness: CommercialDirectness = CommercialDirectness.NOT_APPLICABLE
    relation_subtype: str | None = None
    product_scope_id: str = "corporate_general"
    # Read compatibility for the v1 fixture. The v2 snapshot builder emits an
    # empty list and the v2 validator rejects non-empty legacy scopes.
    product_scopes: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    fact_status: FactStatus
    temporal_status: TemporalStatus
    as_of: date
    valid_from: date | None = None
    valid_to: date | None = None
    confidence_score: int = Field(ge=0, le=100)
    relevance_score: int = Field(ge=0, le=100)
    confidence_breakdown: ScoreBreakdown
    relevance_explanation: str
    evidence_ids: list[str] = Field(min_length=1)
    evidence_roles: dict[str, EvidenceRole] = Field(default_factory=dict)
    # v2.1 keeps relationship-semantic evidence separate from issuer/parent
    # identity evidence.  Both remain in evidence_ids for one-hop API review,
    # while only relationship_evidence_ids may affect relationship scoring.
    relationship_evidence_ids: list[str] = Field(default_factory=list)
    entity_resolution_evidence_ids: list[str] = Field(default_factory=list)
    origin_terminal_statuses: list[str] = Field(default_factory=list)
    inference_explanations: list[str] = Field(default_factory=list)
    low_confidence_partner_inclusion: bool = False
    entity_resolution_inferred: bool = False
    entity_resolution_research_ids: list[str] = Field(default_factory=list)
    observation_count: int = Field(default=1, ge=1)
    independent_source_count: int = Field(default=1, ge=1)
    quantitative: dict[str, Any] = Field(default_factory=dict)
    asserted_by: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def map_legacy_product_scope(cls, value: Any) -> Any:
        if isinstance(value, dict) and not value.get("product_scope_id"):
            scopes = value.get("product_scopes") or []
            value = dict(value)
            value["product_scope_id"] = scopes[0] if len(scopes) == 1 else "corporate_general"
        return value

    @model_validator(mode="after")
    def validate_confidence(self) -> "Relationship":
        caps = {
            FactStatus.CONFIRMED: 100,
            FactStatus.INFERRED: 69,
            FactStatus.UNKNOWN: 39,
        }
        cap = caps[self.fact_status]
        if (
            self.fact_status == FactStatus.INFERRED
            and self.relation_type in {RelationType.SUPPLIER, RelationType.CUSTOMER}
        ):
            cap = 59
        if self.low_confidence_partner_inclusion:
            if self.relation_type != RelationType.PARTNER:
                raise ValueError("low-confidence review observations may only be partner edges")
            low_statuses = set(self.origin_terminal_statuses) & {
                "approve_unknown",
                "needs_more_evidence",
            }
            if not low_statuses:
                raise ValueError("low-confidence partner must retain its original terminal status")
            # Same-key observations can include both terminal classes after
            # exact issuer canonicalization. Preserve every origin, then apply
            # the cap corresponding to the merged semantic status.
            if self.fact_status == FactStatus.INFERRED:
                if "needs_more_evidence" not in low_statuses:
                    raise ValueError("inferred low-confidence partner requires needs_more_evidence")
                cap = 49
            elif self.fact_status == FactStatus.UNKNOWN:
                if "approve_unknown" not in low_statuses:
                    raise ValueError("unknown low-confidence partner requires approve_unknown")
                cap = 39
            else:
                raise ValueError("low-confidence partner must remain inferred or unknown")
            if not self.inference_explanations:
                raise ValueError("low-confidence partner must explain the retained inference")
        expected = min(self.confidence_breakdown.raw_total, cap)
        if self.confidence_score != expected:
            raise ValueError(
                f"confidence_score must be {expected} from breakdown/status, "
                f"got {self.confidence_score}"
            )
        all_evidence = set(self.evidence_ids)
        if not set(self.relationship_evidence_ids).issubset(all_evidence):
            raise ValueError("relationship_evidence_ids must be included in evidence_ids")
        if not set(self.entity_resolution_evidence_ids).issubset(all_evidence):
            raise ValueError("entity_resolution_evidence_ids must be included in evidence_ids")
        if not set(self.evidence_roles).issubset(all_evidence):
            raise ValueError("evidence_roles keys must be included in evidence_ids")
        if self.relation_type not in {RelationType.SUPPLIER, RelationType.CUSTOMER}:
            if self.commercial_directness != CommercialDirectness.NOT_APPLICABLE:
                raise ValueError(
                    "commercial_directness only applies to supplier/customer relationships"
                )
        elif self.commercial_directness == CommercialDirectness.NOT_APPLICABLE:
            # Backward-compatible snapshots may omit the field, but newly built
            # supplier/customer rows must make the uncertainty explicit.
            self.commercial_directness = CommercialDirectness.UNCLEAR
        if self.low_confidence_partner_inclusion and not self.relationship_evidence_ids:
            raise ValueError("low-confidence partner requires relationship-context evidence")
        return self


class ResearchMeta(BaseModel):
    subject_entity_id: str
    cutoff_at: datetime
    evidence_start_date: date
    snapshot_version: str
    generated_at: datetime
    disclaimer: str
    coverage: list[str]
    exclusions: list[str]


class Snapshot(BaseModel):
    meta: ResearchMeta
    entities: list[Entity]
    sources: list[Source]
    evidence: list[Evidence]
    relationships: list[Relationship]

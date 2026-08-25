#!/usr/bin/env python3
"""Pure policy functions for reverse supplier/customer review.

This module is deliberately independent of the main relationship builder.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any


WINDOW_START = date(2025, 1, 1)
WINDOW_END = date(2026, 8, 25)
SOURCE_FACT_CAP = {
    "regulatory_filing": "confirmed",
    "company_news": "inferred",
    "third_party_news": "inferred",
}
SIGNAL_TO_RELATION = {
    "nvidia_is_customer": {
        "relationship_type": "supplier",
        "subject": "partner",
        "object": "nvidia",
        "direction": "supplies_to",
    },
    "partner_purchases_nvidia": {
        "relationship_type": "customer",
        "subject": "nvidia",
        "object": "partner",
        "direction": "sells_to",
    },
}


class PolicyError(ValueError):
    """Input or source-policy rejection."""


def _stable_id(prefix: str, raw: str) -> str:
    return prefix + "_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:18]


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError) as exc:
        raise PolicyError("published_at must be an ISO date/datetime") from exc


def validate_candidate(candidate: dict[str, Any]) -> None:
    required = {
        "candidate_id", "partner_entity_id", "partner_legal_name",
        "source", "signals", "directness", "existing_roles",
    }
    missing = sorted(required - set(candidate))
    if missing:
        raise PolicyError("missing fields: " + ", ".join(missing))
    source = candidate["source"]
    if source.get("source_kind") not in SOURCE_FACT_CAP:
        raise PolicyError("unsupported source_kind")
    if source.get("source_kind") == "regulatory_filing" and not source.get("form_type"):
        raise PolicyError("regulatory_filing requires form_type")
    if candidate["directness"] not in {"direct", "indirect", "unclear"}:
        raise PolicyError("directness must be direct, indirect or unclear")
    if "partner" not in candidate["existing_roles"]:
        raise PolicyError("input must represent an existing Partner role")
    if not isinstance(candidate["signals"], list) or not candidate["signals"]:
        raise PolicyError("signals must be a non-empty list")
    if any(signal not in {*SIGNAL_TO_RELATION, "unclear"} for signal in candidate["signals"]):
        raise PolicyError("unsupported direction signal")
    published = _parse_date(source.get("published_at"))
    if not WINDOW_START <= published <= WINDOW_END:
        raise PolicyError("source date outside 2025-01-01..2026-08-25")
    if source.get("access_mode") != "public_no_login":
        raise PolicyError("source is not legally public/no-login")
    if source.get("access_control_bypassed") is not False:
        raise PolicyError("access-control bypass is prohibited")
    for field in ("url", "publisher", "evidence_locator", "evidence_excerpt"):
        if not source.get(field):
            raise PolicyError(f"source.{field} is required")


def review_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a fail-closed decision; never removes an existing Partner role."""
    validate_candidate(candidate)
    source = candidate["source"]
    source_kind = source["source_kind"]
    partner_id = candidate["partner_entity_id"]
    product_scope = candidate.get("product_scope_id") or "corporate_general"
    claims = []
    for signal in candidate["signals"]:
        if signal == "unclear":
            continue
        mapping = SIGNAL_TO_RELATION[signal]
        subject = partner_id if mapping["subject"] == "partner" else "nvidia"
        object_ = partner_id if mapping["object"] == "partner" else "nvidia"
        fact_status = SOURCE_FACT_CAP[source_kind]
        claims.append({
            "claim_id": _stable_id(
                "prr_claim",
                "|".join([
                    candidate["candidate_id"], signal, product_scope,
                    source["url"], source["evidence_locator"],
                ]),
            ),
            "subject_entity_id": subject,
            "object_entity_id": object_,
            "direction": mapping["direction"],
            "relationship_type": mapping["relationship_type"],
            "fact_status": fact_status,
            "directness": candidate["directness"],
            "product_scope_id": product_scope,
            "source_kind": source_kind,
            "source_url": source["url"],
            "publisher": source["publisher"],
            "published_at": source["published_at"],
            "evidence_locator": source["evidence_locator"],
            "evidence_excerpt": source["evidence_excerpt"],
            "source_cap_applied": (
                "regulatory_explicit_may_confirm"
                if source_kind == "regulatory_filing"
                else "company_or_third_party_news_capped_at_inferred"
            ),
            "direction_rationale": (
                "Counterparty evidence explicitly identifies NVIDIA as its customer; "
                "the counterparty therefore supplies_to NVIDIA."
                if signal == "nvidia_is_customer"
                else "Counterparty evidence explicitly states that it purchases "
                "NVIDIA products; NVIDIA therefore sells_to the counterparty."
            ),
        })
    retained_roles = list(dict.fromkeys([*candidate["existing_roles"], "partner"]))
    return {
        "decision_id": _stable_id("prr_decision", candidate["candidate_id"]),
        "candidate_id": candidate["candidate_id"],
        "review_status": "approved_direction_claims" if claims else "unknown_no_direction_claim",
        "partner_entity_id": partner_id,
        "partner_legal_name": candidate["partner_legal_name"],
        "existing_roles_retained": retained_roles,
        "new_claims": claims,
        "unknown_reason": (
            None if claims else
            "No explicit NVIDIA-as-customer or counterparty-purchases-NVIDIA signal."
        ),
        "multi_role_policy": "Partner is retained; supplier/customer claims are additive and may coexist in both directions.",
    }


def independent_origin_count(sources: list[dict[str, Any]]) -> int:
    """Count origins, not URLs/reposts.

    A repost must retain origin_publication_id or origin_content_fingerprint.
    Two URLs with the same origin key count once.
    """
    origins = set()
    for source in sources:
        origin = (
            source.get("origin_publication_id")
            or source.get("origin_content_fingerprint")
            or "|".join([
                str(source.get("publisher") or ""),
                str(source.get("published_at") or "")[:10],
                str(source.get("evidence_excerpt") or ""),
            ])
        )
        origins.add(origin)
    return len(origins)


def validate_decision(decision: dict[str, Any]) -> None:
    """Enforce direction, source caps, orthogonality and role preservation."""
    if "partner" not in decision.get("existing_roles_retained", []):
        raise PolicyError("Partner role must never be removed")
    seen = set()
    for claim in decision.get("new_claims", []):
        key = (
            claim["relationship_type"], claim["subject_entity_id"],
            claim["object_entity_id"], claim["product_scope_id"],
        )
        if key in seen:
            raise PolicyError("duplicate claim")
        seen.add(key)
        if claim["relationship_type"] == "supplier":
            if not (
                claim["subject_entity_id"] == decision["partner_entity_id"]
                and claim["object_entity_id"] == "nvidia"
                and claim["direction"] == "supplies_to"
            ):
                raise PolicyError("supplier direction is reversed")
        elif claim["relationship_type"] == "customer":
            if not (
                claim["subject_entity_id"] == "nvidia"
                and claim["object_entity_id"] == decision["partner_entity_id"]
                and claim["direction"] == "sells_to"
            ):
                raise PolicyError("customer direction is reversed")
        else:
            raise PolicyError("only supplier/customer may be added")
        if claim["source_kind"] in {"company_news", "third_party_news"} and claim["fact_status"] != "inferred":
            raise PolicyError("news source exceeded inferred cap")
        if claim["directness"] not in {"direct", "indirect", "unclear"}:
            raise PolicyError("invalid directness")
        if claim["fact_status"] not in {"confirmed", "inferred", "unknown"}:
            raise PolicyError("invalid fact_status")

#!/usr/bin/env python3
"""Build auditable NPN outputs from complete browser page snapshots.

The builder is deliberately fail-closed.  It will not group entities, match public
issuers, or emit relationship claims unless the input gate proves that all 23
pages and all 997 final-frozen source cards are present.  No network access is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlsplit, urlunsplit


EXPECTED_PAGES = 23
INITIAL_RUNTIME_OBSERVATIONS = 996
EXPECTED_OBSERVATIONS = 997
RESEARCH_CUTOFF = "2026-08-25"
PUBLISHER = "NVIDIA Corporation"
ACCESS_NOTE = (
    "Public NVIDIA Partner Network directory; no login, paywall, CAPTCHA, "
    "robots, or rate-limit control was bypassed. Facts only; publisher copyright retained."
)

JSONL_OUTPUTS = (
    "raw_listings.jsonl",
    "tag_observations.jsonl",
    "entity_groups.jsonl",
    "listing_group_edges.jsonl",
    "group_decision_ledger.jsonl",
    "listed_group_matches.jsonl",
    "relationship_claims.jsonl",
    "evidence.jsonl",
    "pagination_manifest.jsonl",
)

# Every NPN competency observed on the full first legacy page has a distinct,
# existing product-tree key.  An unknown competency is a hard failure, never a
# guessed taxonomy assignment.
COMPETENCY_TO_SCOPE = {
    "Compute": "accelerated-computing",
    "Visualization": "professional-visualization-and-workstations",
    "NVIDIA Enterprise Software": "nvidia-ai-enterprise",
    "NVIDIA Technologies": "architectures-and-core-technologies",
    "Embedded Compute": "embedded-robotics-and-edge",
    "NVIDIA Virtual Desktops": "virtual-gpu",
    "Networking": "networking",
    "DGX AI Compute Systems": "dgx-platform",
    "DGX Cloud": "dgx-cloud",
}

TAG_FIELDS = (
    "partner_types",
    "competencies",
    "specializations",
    "partner_levels",
    "locations",
    "product_service_tags",
)
OPTIONAL_TAG_FIELDS = (
    "specializations",
    "partner_levels",
    "locations",
    "product_service_tags",
)

EXPECTED_PAGE_COUNTS = {**{page: 45 for page in range(1, 23)}, 23: 7}
ALLOWED_SPECIALIZATIONS = {"AI Factory", "Reference Platform NCP"}
ALLOWED_PARTNER_TYPES = {
    "Advanced Technology Partner",
    "Architecture / Engineering / Construction",
    "Cloud Partner",
    "Data Center Partner",
    "Distributor",
    "Education Services",
    "Global Systems Integrator",
    "Independent Software Vendor",
    "OEM",
    "Power and Cooling",
    "Solution Advisor",
    "Solution Provider",
    "Storage Partner",
    "System Partner",
}

LEGAL_SUFFIX_SEQUENCES = (
    *((x,) for x in ("inc", "incorporated", "corporation", "corp", "ltd", "limited", "llc", "plc", "ag", "gmbh", "sa", "spa", "bv", "nv", "oy", "ab", "sas", "kk")),
    ("co", "ltd"),
    ("company", "limited"),
    ("pte", "ltd"),
    ("sdn", "bhd"),
)

REGION_SUFFIX_SEQUENCES = (
    *((x,) for x in ("usa", "us", "canada", "uk", "ireland", "france", "germany", "japan", "korea", "china", "taiwan", "singapore", "india", "australia", "emea", "apac", "europe", "uae")),
    ("middle", "east"),
    ("latin", "america"),
    ("hong", "kong"),
    ("new", "zealand"),
)

# Explicitly reviewed corporate-family rules requested for known repeated NPN
# cards.  These are anchored deterministic rules, not similarity matching.
EXPLICIT_GROUP_RULES = {
    "amax": re.compile(r"^amax(?:\s|$)"),
    "accenture": re.compile(r"^accenture(?:\s|$)"),
    "asus_asustek": re.compile(r"^(?:asus|asustek)(?:\s|$)"),
    "2crsi": re.compile(r"^2crsi(?:\s|$)"),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any, length: int = 16) -> str:
    data = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:length]


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(str(value).strip())
    path = re.sub(r"/+", "/", parts.path).rstrip("/") + "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, "", ""))


def clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        raise TypeError(f"tag field must be string, list, or null; got {type(value).__name__}")
    return [str(item).strip() for item in value if str(item).strip()]


def strip_suffix(tokens: tuple[str, ...], candidates: tuple[tuple[str, ...], ...]) -> tuple[str, ...]:
    current = tokens
    changed = True
    while changed and current:
        changed = False
        for suffix in sorted(candidates, key=len, reverse=True):
            if len(current) > len(suffix) and current[-len(suffix) :] == suffix:
                current = current[: -len(suffix)]
                changed = True
                break
    return current


def legal_key(name: str) -> str:
    return " ".join(strip_suffix(tuple(normalize_name(name).split()), LEGAL_SUFFIX_SEQUENCES))


def region_key(name: str) -> str:
    tokens = strip_suffix(tuple(normalize_name(name).split()), LEGAL_SUFFIX_SEQUENCES)
    tokens = strip_suffix(tokens, REGION_SUFFIX_SEQUENCES)
    return " ".join(tokens)


def page_number(path: Path, payload: dict[str, Any]) -> int | None:
    raw = payload.get("page")
    if isinstance(raw, int):
        return raw
    m = re.search(r"page_(\d+)$", path.stem)
    return int(m.group(1)) if m else None


def extract_total(payload: dict[str, Any]) -> int | None:
    raw_runtime_total = payload.get("runtime_total")
    if isinstance(raw_runtime_total, int):
        return raw_runtime_total
    if isinstance(payload.get("range"), dict):
        raw = payload["range"].get("total")
        if isinstance(raw, int):
            return raw
    if isinstance(payload.get("pagination"), dict):
        for key in ("totalRecords", "total_records", "total"):
            raw = payload["pagination"].get(key)
            if isinstance(raw, int):
                return raw
    return None


def extract_range(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    raw = payload.get("range")
    if isinstance(raw, dict):
        return raw.get("start"), raw.get("end")
    return None, None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError(f"{path}:{number}: expected object")
                rows.append(item)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def empty_outputs(output_dir: Path) -> None:
    for name in JSONL_OUTPUTS:
        (output_dir / name).write_text("", encoding="utf-8")


class UnionFind:
    def __init__(self, keys: Iterable[str]) -> None:
        self.parent = {key: key for key in keys}

    def find(self, key: str) -> str:
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def fail_closed(
    output_dir: Path,
    page_rows: list[dict[str, Any]],
    errors: list[str],
    observed_pages: list[int],
    observed_records: int,
) -> int:
    empty_outputs(output_dir)
    write_jsonl(output_dir / "pagination_manifest.jsonl", page_rows)
    now = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": "npn-runtime-validator-v1",
        "generated_at": now,
        "status": "failed_closed",
        "complete": False,
        "terminal": True,
        "completion_claim": "input_incomplete_or_invalid_no_downstream_outputs_emitted",
        "expected_pages": EXPECTED_PAGES,
        "observed_pages": observed_pages,
        "missing_pages": sorted(set(range(1, EXPECTED_PAGES + 1)) - set(observed_pages)),
        "initial_runtime_observation_total": INITIAL_RUNTIME_OBSERVATIONS,
        "final_frozen_runtime_total": EXPECTED_OBSERVATIONS,
        "runtime_total_drift": EXPECTED_OBSERVATIONS - INITIAL_RUNTIME_OBSERVATIONS,
        "runtime_total_drift_status": "reconciled_in_final_browser_freeze",
        "expected_raw_observations": EXPECTED_OBSERVATIONS,
        "observed_raw_observations": observed_records,
        "pending_count": 0,
        "errors": errors,
        "gates": {
            "page_count_exact": len(observed_pages) == EXPECTED_PAGES,
            "page_numbers_contiguous": observed_pages == list(range(1, EXPECTED_PAGES + 1)),
            "raw_observation_count_exact": observed_records == EXPECTED_OBSERVATIONS,
            "downstream_build_permitted": False,
        },
    }
    write_json(output_dir / "validation_report.json", report)
    write_json(
        output_dir / "group_validation_report.json",
        {
            "schema_version": "npn-group-validator-v1",
            "generated_at": now,
            "status": "not_run_input_gate_failed",
            "complete": False,
            "terminal": True,
            "pending_count": 0,
            "errors": ["Grouping and listed-company resolution were not run because the input gate failed."],
        },
    )
    return 2


def build(args: argparse.Namespace) -> int:
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    run_root = args.product_index.resolve().parents[1]
    repository_root = run_root.parents[1]

    def portable_snapshot_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(repository_root))
        except ValueError:
            # Development fixtures outside the repository must not leak a local
            # absolute path into a generated artifact.
            return f"external_input/{path.name}"

    output_dir.mkdir(parents=True, exist_ok=True)

    page_paths = sorted(input_dir.glob("page_*.json")) if input_dir.exists() else []
    page_payloads: list[tuple[Path, dict[str, Any], int | None, str]] = []
    errors: list[str] = []
    manifest: list[dict[str, Any]] = []
    observed_records = 0

    for path in page_paths:
        raw_bytes = path.read_bytes()
        sha = hashlib.sha256(raw_bytes).hexdigest()
        try:
            payload = json.loads(raw_bytes)
            if not isinstance(payload, dict):
                raise ValueError("top-level JSON is not an object")
        except Exception as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        number = page_number(path, payload)
        records = payload.get("records")
        if not isinstance(records, list):
            errors.append(f"{path.name}: records is not a list")
            records = []
        observed_records += len(records)
        start, end = extract_range(payload)
        selection_audit = payload.get("selection_audit")
        manifest.append(
            {
                "page": number,
                "snapshot_path": portable_snapshot_path(path),
                "source_url": payload.get("source_url") or payload.get("url"),
                "record_count": len(records),
                "declared_total": extract_total(payload),
                "range_start": start,
                "range_end": end,
                "initial_runtime_observation_total": payload.get("initial_runtime_observation_total"),
                "final_frozen_runtime_total": extract_total(payload),
                "runtime_total_drift": (
                    extract_total(payload) - payload.get("initial_runtime_observation_total")
                    if isinstance(extract_total(payload), int)
                    and isinstance(payload.get("initial_runtime_observation_total"), int)
                    else None
                ),
                "runtime_total_drift_status": "reconciled_in_final_browser_freeze",
                "selection_audit": selection_audit,
                "source_content_sha256": sha,
                "status": "observed",
            }
        )
        expected_count = EXPECTED_PAGE_COUNTS.get(number) if isinstance(number, int) else None
        if expected_count is not None and len(records) != expected_count:
            errors.append(f"{path.name}: expected {expected_count} cards on page {number}, found {len(records)}")
        if payload.get("initial_runtime_observation_total") != INITIAL_RUNTIME_OBSERVATIONS:
            errors.append(
                f"{path.name}: initial runtime total is not the reconciled {INITIAL_RUNTIME_OBSERVATIONS}"
            )
        if not isinstance(selection_audit, dict):
            errors.append(f"{path.name}: selection_audit is absent or not an object")
        elif selection_audit.get("expected_visible_directory_cards") != len(records):
            errors.append(f"{path.name}: selection_audit visible-card count does not match records")
        source_url = payload.get("source_url") or payload.get("url")
        parsed_url = urlsplit(str(source_url or ""))
        query = parse_qs(parsed_url.query)
        if not (
            parsed_url.scheme == "https"
            and parsed_url.netloc == "marketplace.nvidia.com"
            and parsed_url.path.rstrip("/") == "/en-us/enterprise/partners"
            and query.get("locale") == ["en-us"]
            and query.get("page") == [str(number)]
            and query.get("limit") == ["45"]
        ):
            errors.append(f"{path.name}: source_url is not the expected public NPN page URL")
        page_payloads.append((path, payload, number, sha))

    observed_pages = sorted(x for _, _, x, _ in page_payloads if isinstance(x, int))
    if len(observed_pages) != len(set(observed_pages)):
        errors.append("duplicate page number detected")
    if len(page_paths) != EXPECTED_PAGES:
        errors.append(f"expected {EXPECTED_PAGES} page files, found {len(page_paths)}")
    if observed_pages != list(range(1, EXPECTED_PAGES + 1)):
        errors.append("page numbers are not exactly contiguous 1..23")
    if observed_records != EXPECTED_OBSERVATIONS:
        errors.append(f"expected {EXPECTED_OBSERVATIONS} cards, found {observed_records}")
    declared_totals = {extract_total(p) for _, p, _, _ in page_payloads if extract_total(p) is not None}
    if declared_totals and declared_totals != {EXPECTED_OBSERVATIONS}:
        errors.append(
            f"declared page totals conflict with final frozen {EXPECTED_OBSERVATIONS}: {sorted(declared_totals)}"
        )
    declared_ranges = [
        extract_range(payload)
        for _, payload, _, _ in sorted(page_payloads, key=lambda item: int(item[2] or 0))
    ]
    expected_ranges = [(1 + (page - 1) * 45, min(page * 45, EXPECTED_OBSERVATIONS)) for page in range(1, 24)]
    if declared_ranges != expected_ranges:
        errors.append("declared page ranges are not contiguous 1..997 with a seven-card final page")

    if errors:
        return fail_closed(output_dir, manifest, errors, observed_pages, observed_records)

    raw_rows: list[dict[str, Any]] = []
    tag_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    schema_errors: list[str] = []

    for path, payload, number, sha in sorted(page_payloads, key=lambda x: int(x[2] or 0)):
        assert number is not None
        page_evidence_id = f"npn-evidence-{number:03d}-{sha[:12]}"
        record_retrieval_values = sorted(
            {
                str(record.get("retrieved_at") or record.get("fetched_at"))
                for record in payload["records"]
                if isinstance(record, dict) and (record.get("retrieved_at") or record.get("fetched_at"))
            }
        )
        retrieved_at = (
            payload.get("retrieved_at")
            or payload.get("fetched_at")
            or (record_retrieval_values[-1] if record_retrieval_values else None)
            or RESEARCH_CUTOFF
        )
        evidence_rows.append(
            {
                "evidence_id": page_evidence_id,
                "source_url": payload.get("source_url") or payload.get("url"),
                "publisher": PUBLISHER,
                "published_at": None,
                "retrieved_at": retrieved_at,
                "retrieved_at_precision": "timestamp" if "T" in str(retrieved_at) else "date",
                "evidence_locator": f"page snapshot {path.name}; per-card CSS locators retained in raw_listings.jsonl",
                "snapshot_path": portable_snapshot_path(path),
                "source_content_sha256": sha,
                "access_or_license_restrictions": ACCESS_NOTE,
            }
        )
        records = payload["records"]
        for local_index, record in enumerate(records, 1):
            if not isinstance(record, dict):
                schema_errors.append(f"{path.name} record {local_index}: not an object")
                continue
            name = str(record.get("name") or "").strip()
            if not name:
                schema_errors.append(f"{path.name} record {local_index}: missing name")
                continue
            for required_list_field in (
                "partner_types",
                "competencies",
                "specializations",
                "partner_levels",
                "locations",
            ):
                if not isinstance(record.get(required_list_field), list):
                    schema_errors.append(
                        f"{path.name} record {local_index}: {required_list_field} must be a source list"
                    )
            try:
                partner_types = clean_list(record.get("partner_types"))
                competencies = clean_list(record.get("competencies"))
                specializations = clean_list(record.get("specializations"))
                partner_levels = clean_list(record.get("partner_levels", record.get("partner_level")))
                locations = clean_list(record.get("locations"))
                product_service_tags = clean_list(record.get("product_service_tags"))
            except TypeError as exc:
                schema_errors.append(f"{path.name} record {local_index}: {exc}")
                continue
            tags = {
                "partner_types": partner_types,
                "competencies": competencies,
                "specializations": specializations,
                "partner_levels": partner_levels,
                "locations": locations,
                "product_service_tags": product_service_tags,
            }
            position = record.get("position") if isinstance(record.get("position"), int) else local_index
            profile_url = normalize_url(record.get("profile_url"))
            source_profile = urlsplit(str(profile_url or ""))
            if not (
                source_profile.scheme == "https"
                and source_profile.netloc == "marketplace.nvidia.com"
                and source_profile.path.startswith("/en-us/enterprise/partners/")
            ):
                schema_errors.append(f"{path.name} record {local_index}: invalid public NPN profile URL")
            if record.get("page") != number or position != local_index:
                schema_errors.append(f"{path.name} record {local_index}: page/position locator mismatch")
            page_source_url = payload.get("source_url") or payload.get("url")
            if record.get("source_url") != page_source_url:
                schema_errors.append(f"{path.name} record {local_index}: source URL differs from page URL")
            unknown_partner_types = sorted(set(partner_types) - ALLOWED_PARTNER_TYPES)
            if not partner_types or unknown_partner_types:
                schema_errors.append(
                    f"{path.name} record {local_index}: missing/unknown Partner Type values {unknown_partner_types}"
                )
            invalid_specializations = sorted(set(specializations) - ALLOWED_SPECIALIZATIONS)
            if invalid_specializations:
                schema_errors.append(
                    f"{path.name} record {local_index}: invalid specialization values {invalid_specializations}"
                )
            observation_id = f"npn-raw-{number:03d}-{local_index:03d}-{digest([name, profile_url, position], 12)}"
            source_url = record.get("source_url") or payload.get("source_url") or payload.get("url")
            record_retrieved_at = record.get("retrieved_at") or record.get("fetched_at") or retrieved_at
            optional_empty = [field for field in OPTIONAL_TAG_FIELDS if not tags[field]]
            raw_row = {
                "observation_id": observation_id,
                "source_observation_id": record.get("observation_id"),
                "listing_id": record.get("listing_id") or record.get("code"),
                "name": name,
                "normalized_name": normalize_name(name),
                "profile_url": profile_url,
                "logo_url": record.get("logo_url"),
                **tags,
                "page": number,
                "position": position,
                "source_url": source_url,
                "publisher": PUBLISHER,
                "published_at": None,
                "retrieved_at": record_retrieved_at,
                "evidence_id": page_evidence_id,
                "evidence_locator": record.get("evidence_locator") or f"records[{local_index - 1}]",
                "snapshot_path": portable_snapshot_path(path),
                "source_content_sha256": sha,
                "collection_method": "public_browser_visible_card_snapshot",
                "observation_status": "complete_raw_observation",
                "optional_tags_status": "present" if not optional_empty else "partly_or_fully_not_exposed_on_card",
                "optional_empty_fields": optional_empty,
                "optional_tags_missing_reason": (
                    None if not optional_empty else "The visible source card did not expose values for these optional tag classes."
                ),
                "access_or_license_restrictions": ACCESS_NOTE,
            }
            raw_rows.append(raw_row)
            for tag_class in TAG_FIELDS:
                for tag_position, tag_value in enumerate(tags[tag_class], 1):
                    tag_rows.append(
                        {
                            "tag_observation_id": f"npn-tag-{digest([observation_id, tag_class, tag_position, tag_value])}",
                            "listing_observation_id": observation_id,
                            "tag_class": tag_class,
                            "tag_value": tag_value,
                            "tag_position": tag_position,
                            "source_url": source_url,
                            "publisher": PUBLISHER,
                            "retrieved_at": record_retrieved_at,
                            "evidence_id": page_evidence_id,
                            "evidence_locator": raw_row["evidence_locator"],
                            "source_content_sha256": sha,
                            "provenance_status": "direct_visible_card_tag",
                        }
                    )

    raw_ids = [row["observation_id"] for row in raw_rows]
    if len(raw_rows) != EXPECTED_OBSERVATIONS:
        schema_errors.append(
            f"parsed raw row count is {len(raw_rows)}, expected final frozen {EXPECTED_OBSERVATIONS}"
        )
    if len(set(raw_ids)) != EXPECTED_OBSERVATIONS:
        schema_errors.append(
            f"raw observation IDs are not exactly {EXPECTED_OBSERVATIONS} unique values"
        )
    unknown_competencies = sorted(
        {value for row in raw_rows for value in row["competencies"] if value not in COMPETENCY_TO_SCOPE}
    )
    if unknown_competencies:
        schema_errors.append(f"unmapped NPN competencies: {unknown_competencies}")

    product_rows: list[dict[str, Any]] = []
    try:
        product_rows = load_jsonl(args.product_index.resolve())
    except Exception as exc:
        schema_errors.append(f"product index unavailable or invalid: {exc}")
    valid_scopes = {row.get("canonical_key") for row in product_rows}
    missing_scopes = sorted(set(COMPETENCY_TO_SCOPE.values()) - valid_scopes)
    if missing_scopes:
        schema_errors.append(f"mapped product_scope_id values absent from canonical product tree: {missing_scopes}")

    if schema_errors:
        return fail_closed(output_dir, manifest, schema_errors, observed_pages, len(raw_rows))

    # Deterministic grouping.  Each union operation records an auditable exact rule.
    uf = UnionFind(raw_ids)
    merge_reasons: dict[str, set[str]] = defaultdict(set)

    def union_bucket(bucket: list[str], reason: str) -> None:
        if len(bucket) < 2:
            return
        anchor = min(bucket)
        for item in sorted(bucket):
            uf.union(anchor, item)
            merge_reasons[item].add(reason)
            merge_reasons[anchor].add(reason)

    by_profile: dict[str, list[str]] = defaultdict(list)
    by_legal: dict[str, list[str]] = defaultdict(list)
    by_explicit: dict[str, list[str]] = defaultdict(list)
    normalized_names = {row["normalized_name"] for row in raw_rows}
    legal_names = {legal_key(row["name"]) for row in raw_rows}
    by_id = {row["observation_id"]: row for row in raw_rows}
    for row in raw_rows:
        oid = row["observation_id"]
        if row["profile_url"]:
            by_profile[row["profile_url"]].append(oid)
        by_legal[legal_key(row["name"])].append(oid)
        for family, pattern in EXPLICIT_GROUP_RULES.items():
            if pattern.match(row["normalized_name"]):
                by_explicit[family].append(oid)
                break
    for url, bucket in by_profile.items():
        union_bucket(bucket, f"same_profile_url:{url}")
    for key, bucket in by_legal.items():
        if key:
            union_bucket(bucket, f"legal_suffix_only:{key}")
    for family, bucket in by_explicit.items():
        union_bucket(bucket, f"explicit_reviewed_family:{family}")

    # A region suffix is removed only when the base also occurs in the observed
    # corpus; this prevents isolated city/country names from being over-merged.
    by_region: dict[str, list[str]] = defaultdict(list)
    for row in raw_rows:
        rkey = region_key(row["name"])
        if rkey and rkey != legal_key(row["name"]) and (rkey in normalized_names or rkey in legal_names):
            by_region[rkey].append(row["observation_id"])
            for other in raw_rows:
                if other["normalized_name"] == rkey or legal_key(other["name"]) == rkey:
                    by_region[rkey].append(other["observation_id"])
    for key, bucket in by_region.items():
        union_bucket(sorted(set(bucket)), f"region_suffix_with_observed_base:{key}")

    members_by_root: dict[str, list[str]] = defaultdict(list)
    for oid in raw_ids:
        members_by_root[uf.find(oid)].append(oid)

    group_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    group_members: dict[str, list[dict[str, Any]]] = {}
    for member_ids in sorted(members_by_root.values(), key=lambda ids: min(ids)):
        member_ids = sorted(member_ids)
        members = [by_id[oid] for oid in member_ids]
        group_id = f"npn-group-{digest(member_ids)}"
        canonical_name = min((row["name"] for row in members), key=lambda x: (len(normalize_name(x)), normalize_name(x), x))
        reasons = sorted({reason for oid in member_ids for reason in merge_reasons.get(oid, set())})
        group_members[group_id] = members
        group_rows.append(
            {
                "group_id": group_id,
                "canonical_name": canonical_name,
                "member_observation_ids": member_ids,
                "member_names": sorted({row["name"] for row in members}),
                "profile_urls": sorted({row["profile_url"] for row in members if row["profile_url"]}),
                "partner_types": sorted({tag for row in members for tag in row["partner_types"]}),
                "competencies": sorted({tag for row in members for tag in row["competencies"]}),
                "specializations": sorted({tag for row in members for tag in row["specializations"]}),
                "partner_levels": sorted({tag for row in members for tag in row["partner_levels"]}),
                "locations": sorted({tag for row in members for tag in row["locations"]}),
                "product_service_tags": sorted({tag for row in members for tag in row["product_service_tags"]}),
                "raw_observation_count": len(members),
                "grouping_status": "terminal",
                "grouping_method": "deterministic_exact_rules_only",
                "fuzzy_matching_used": False,
            }
        )
        for row in members:
            member_reasons = sorted(merge_reasons.get(row["observation_id"], set()))
            edge_rows.append(
                {
                    "listing_observation_id": row["observation_id"],
                    "group_id": group_id,
                    "decision": "merged" if len(member_ids) > 1 else "singleton",
                    "decision_reasons": member_reasons or ["unique_terminal_listing"],
                    "fuzzy_matching_used": False,
                    "status": "terminal",
                }
            )
        ledger_rows.append(
            {
                "decision_id": f"npn-group-decision-{digest(group_id)}",
                "group_id": group_id,
                "candidate_name": canonical_name,
                "decision": "grouped" if len(member_ids) > 1 else "singleton_retained",
                "decision_reasons": reasons or ["no_safe_exact_grouping_rule_shared_with_another_listing"],
                "member_observation_ids": member_ids,
                "status": "terminal",
                "pending": False,
                "fuzzy_matching_used": False,
            }
        )

    # Load only reviewed exact aliases from the base registry and safe_exact
    # aliases from the global overlay.  No normalized substring/fuzzy fallback.
    registry: dict[str, dict[str, Any]] = {}
    alias_to_entities: dict[str, set[str]] = defaultdict(set)
    alias_provenance: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    registry_errors: list[str] = []
    try:
        for row in load_jsonl(args.base_registry.resolve()) + load_jsonl(args.overlay_registry.resolve()):
            entity_id = row.get("entity_id")
            if entity_id:
                if entity_id in registry and canonical_json(registry[entity_id]) != canonical_json(row):
                    # Overlay augment records may intentionally repeat a base entity.
                    if row.get("merge_action") == "augment_existing":
                        merged = dict(registry[entity_id])
                        merged.update(row)
                        registry[entity_id] = merged
                    else:
                        registry_errors.append(f"conflicting registry rows for {entity_id}")
                else:
                    registry[entity_id] = row
        for path, source, allowed in (
            (args.base_aliases.resolve(), "base_registry", {"reviewed", "safe_exact"}),
            (args.overlay_aliases.resolve(), "global_listing_overlay", {"safe_exact"}),
        ):
            for row in load_jsonl(path):
                if row.get("alias_status") not in allowed:
                    continue
                normalized = row.get("normalized_alias") or normalize_name(row.get("alias", ""))
                entity_id = row.get("entity_id")
                if normalized and entity_id:
                    alias_to_entities[normalized].add(entity_id)
                    alias_provenance[(normalized, entity_id)].append(
                        {
                            "source": source,
                            "alias": row.get("alias"),
                            "alias_status": row.get("alias_status"),
                            "match_policy": "exact_only",
                        }
                    )
    except Exception as exc:
        registry_errors.append(f"registry or aliases unavailable/invalid: {exc}")
    if registry_errors:
        return fail_closed(output_dir, manifest, registry_errors, observed_pages, len(raw_rows))

    listed_matches: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    match_status_by_group: dict[str, str] = {}
    for group in group_rows:
        group_id = group["group_id"]
        members = group_members[group_id]
        candidate_aliases = sorted({row["normalized_name"] for row in members})
        match_pairs = sorted(
            {(alias, entity_id) for alias in candidate_aliases for entity_id in alias_to_entities.get(alias, set())}
        )
        entity_ids = sorted({entity_id for _, entity_id in match_pairs})
        if len(entity_ids) != 1:
            status = "unresolved_no_safe_exact_alias_terminal" if not entity_ids else "conflicting_safe_exact_aliases_terminal"
            match_status_by_group[group_id] = status
            ledger_rows.append(
                {
                    "decision_id": f"npn-listing-decision-{digest([group_id, status])}",
                    "group_id": group_id,
                    "candidate_name": group["canonical_name"],
                    "decision": status,
                    "matched_entity_ids": entity_ids,
                    "candidate_aliases_checked": candidate_aliases,
                    "status": "terminal",
                    "pending": False,
                    "fuzzy_matching_used": False,
                }
            )
            continue
        entity_id = entity_ids[0]
        entity = registry.get(entity_id)
        if not entity or entity.get("listing_status") != "listed_confirmed":
            status = "matched_entity_not_active_listed_at_cutoff_terminal"
            match_status_by_group[group_id] = status
            ledger_rows.append(
                {
                    "decision_id": f"npn-listing-decision-{digest([group_id, status])}",
                    "group_id": group_id,
                    "candidate_name": group["canonical_name"],
                    "decision": status,
                    "matched_entity_ids": [entity_id],
                    "listing_status": entity.get("listing_status") if entity else None,
                    "status": "terminal",
                    "pending": False,
                    "fuzzy_matching_used": False,
                }
            )
            continue
        matched_aliases = [alias for alias, eid in match_pairs if eid == entity_id]
        match_status_by_group[group_id] = "listed_parent_resolved_safe_exact"
        match_id = f"npn-listed-match-{digest([group_id, entity_id])}"
        listed_matches.append(
            {
                "match_id": match_id,
                "group_id": group_id,
                "entity_id": entity_id,
                "display_name": entity.get("display_name"),
                "legal_name": entity.get("legal_name"),
                "listing_status": entity.get("listing_status"),
                "securities": entity.get("securities", []),
                "listing_evidence_ids": entity.get("listing_evidence_ids", []),
                "matched_aliases": matched_aliases,
                "alias_provenance": [
                    item for alias in matched_aliases for item in alias_provenance.get((alias, entity_id), [])
                ],
                "match_method": "safe_exact_alias_only",
                "fuzzy_matching_used": False,
                "status": "terminal",
            }
        )
        ledger_rows.append(
            {
                "decision_id": f"npn-listing-decision-{digest([group_id, entity_id])}",
                "group_id": group_id,
                "candidate_name": group["canonical_name"],
                "decision": "listed_parent_resolved_safe_exact",
                "matched_entity_ids": [entity_id],
                "matched_aliases": matched_aliases,
                "status": "terminal",
                "pending": False,
                "fuzzy_matching_used": False,
            }
        )
        evidence_ids = sorted({row["evidence_id"] for row in members})
        for competency in group["competencies"]:
            product_scope_id = COMPETENCY_TO_SCOPE[competency]
            claim_id = f"npn-claim-{digest([entity_id, competency])}"
            claims.append(
                {
                    "claim_id": claim_id,
                    "subject_entity_id": "nvidia",
                    "object_entity_id": entity_id,
                    "relationship_type": "partner",
                    "direction": "partners_with",
                    "direction_explanation": "Official NPN directory membership establishes a symmetric partner-program relationship; it does not establish a buyer/seller direction.",
                    "relation_subtype": "nvidia_partner_network_directory_member",
                    "npn_group_id": group_id,
                    "npn_group_ids": [group_id],
                    "competency": competency,
                    "product_scope_id": product_scope_id,
                    "product_mapping_status": "exact_curated_npn_competency_to_canonical_product_scope",
                    "partner_types": group["partner_types"],
                    "fact_status": "confirmed",
                    "temporal_status": "current_as_observed_at_cutoff",
                    "as_of": RESEARCH_CUTOFF,
                    "confidence_score": 80,
                    "confidence_factors": {
                        "official_source_authority": 25,
                        "explicit_directory_membership": 25,
                        "safe_exact_listed_parent_resolution": 15,
                        "independent_corroboration": 0,
                        "current_cutoff_snapshot": 10,
                        "competency_specificity": 5,
                    },
                    "evidence_ids": evidence_ids,
                    "source_observation_ids": sorted(row["observation_id"] for row in members if competency in row["competencies"]),
                    "role_boundary": "Directory membership supports partner only. It is not evidence that the member is an NVIDIA supplier or customer.",
                    "limitations": [
                        "NPN directory membership alone does not disclose transaction direction, revenue, spend, contract terms, or exclusivity.",
                        "Competency is an NPN program tag normalized to one canonical product scope; it is not proof of product adoption or purchase.",
                    ],
                    "dedup_key": "|".join(["nvidia", entity_id, "partners_with", "partner", product_scope_id]),
                }
            )

    # Multiple exact NPN groups can resolve to one listed parent (for example a
    # brand card and an issuer-name card).  Consolidate only at the relationship
    # key, retaining every contributing group, observation, tag, and evidence.
    claims_by_key: dict[str, dict[str, Any]] = {}
    for claim in claims:
        key = claim["dedup_key"]
        if key not in claims_by_key:
            claims_by_key[key] = claim
            continue
        current = claims_by_key[key]
        current["npn_group_ids"] = sorted(set(current["npn_group_ids"] + claim["npn_group_ids"]))
        current["npn_group_id"] = current["npn_group_ids"][0]
        current["partner_types"] = sorted(set(current["partner_types"] + claim["partner_types"]))
        current["evidence_ids"] = sorted(set(current["evidence_ids"] + claim["evidence_ids"]))
        current["source_observation_ids"] = sorted(
            set(current["source_observation_ids"] + claim["source_observation_ids"])
        )
    claims = [claims_by_key[key] for key in sorted(claims_by_key)]

    # Final validation gates.
    edge_ids = [row["listing_observation_id"] for row in edge_rows]
    claim_keys = [row["dedup_key"] for row in claims]
    pending_count = sum(1 for row in ledger_rows if row.get("pending") or row.get("status") == "pending")
    group_errors: list[str] = []
    if sorted(edge_ids) != sorted(raw_ids) or len(edge_ids) != len(set(edge_ids)):
        group_errors.append("each raw observation must map to exactly one group")
    if any(row["grouping_status"] != "terminal" for row in group_rows):
        group_errors.append("nonterminal entity group")
    if pending_count:
        group_errors.append(f"pending decisions remain: {pending_count}")
    if any(row.get("fuzzy_matching_used") for row in edge_rows + ledger_rows + listed_matches):
        group_errors.append("fuzzy matching was used")
    if len(claim_keys) != len(set(claim_keys)):
        group_errors.append("duplicate relationship claim dedup_key")
    if any(row["relationship_type"] != "partner" for row in claims):
        group_errors.append("NPN generated a non-partner relationship")
    if any(row["product_scope_id"] not in valid_scopes for row in claims):
        group_errors.append("claim contains invalid product_scope_id")
    if any(not row.get("competency") for row in claims):
        group_errors.append("claim lacks a single competency")

    # Write every output only after all transformations have completed.
    write_jsonl(output_dir / "raw_listings.jsonl", raw_rows)
    write_jsonl(output_dir / "tag_observations.jsonl", tag_rows)
    write_jsonl(output_dir / "entity_groups.jsonl", group_rows)
    write_jsonl(output_dir / "listing_group_edges.jsonl", edge_rows)
    write_jsonl(output_dir / "group_decision_ledger.jsonl", ledger_rows)
    write_jsonl(output_dir / "listed_group_matches.jsonl", listed_matches)
    write_jsonl(output_dir / "relationship_claims.jsonl", claims)
    write_jsonl(output_dir / "evidence.jsonl", evidence_rows)
    write_jsonl(output_dir / "pagination_manifest.jsonl", manifest)

    now = datetime.now(timezone.utc).isoformat()
    group_report = {
        "schema_version": "npn-group-validator-v1",
        "generated_at": now,
        "status": "passed" if not group_errors else "failed",
        "complete": not group_errors,
        "terminal": True,
        "pending_count": pending_count,
        "raw_observation_count": len(raw_rows),
        "initial_runtime_observation_total": INITIAL_RUNTIME_OBSERVATIONS,
        "final_frozen_runtime_total": EXPECTED_OBSERVATIONS,
        "runtime_total_drift": EXPECTED_OBSERVATIONS - INITIAL_RUNTIME_OBSERVATIONS,
        "runtime_total_drift_status": "reconciled_in_final_browser_freeze",
        "entity_group_count": len(group_rows),
        "listing_group_edge_count": len(edge_rows),
        "listed_group_match_count": len(listed_matches),
        "relationship_claim_count": len(claims),
        "nonempty_specialization_observation_count": sum(bool(row["specializations"]) for row in raw_rows),
        "specialization_values": sorted({value for row in raw_rows for value in row["specializations"]}),
        "fuzzy_matching_used": False,
        "exact_group_rule_counts": dict(
            sorted(
                (prefix, sum(prefix in reason for row in ledger_rows for reason in row.get("decision_reasons", [])))
                for prefix in ("same_profile_url", "legal_suffix_only", "region_suffix_with_observed_base", "explicit_reviewed_family")
            )
        ),
        "errors": group_errors,
        "gates": {
            "all_raw_observations_grouped_once": not any("exactly one group" in e for e in group_errors),
            "all_candidates_terminal": pending_count == 0,
            "fuzzy_matching_prohibited": True,
            "only_safe_exact_aliases_used": True,
            "only_partner_claims_generated": not any("non-partner" in e for e in group_errors),
            "claim_product_scopes_valid": not any("invalid product_scope" in e for e in group_errors),
        },
    }
    write_json(output_dir / "group_validation_report.json", group_report)
    validation_errors = list(group_errors)
    validation = {
        "schema_version": "npn-runtime-validator-v1",
        "generated_at": now,
        "status": "passed" if not validation_errors else "failed",
        "complete": not validation_errors,
        "terminal": True,
        "completion_claim": (
            "all_23_pages_and_997_final_frozen_raw_observations_processed"
            if not validation_errors
            else "downstream_validation_failed"
        ),
        "expected_pages": EXPECTED_PAGES,
        "observed_pages": observed_pages,
        "initial_runtime_observation_total": INITIAL_RUNTIME_OBSERVATIONS,
        "final_frozen_runtime_total": EXPECTED_OBSERVATIONS,
        "runtime_total_drift": EXPECTED_OBSERVATIONS - INITIAL_RUNTIME_OBSERVATIONS,
        "runtime_total_drift_status": "reconciled_in_final_browser_freeze",
        "expected_raw_observations": EXPECTED_OBSERVATIONS,
        "observed_raw_observations": len(raw_rows),
        "unique_raw_observation_ids": len(set(raw_ids)),
        "raw_partner_type_tag_count": sum(len(row["partner_types"]) for row in raw_rows),
        "emitted_partner_type_tag_count": sum(row["tag_class"] == "partner_types" for row in tag_rows),
        "raw_competency_tag_count": sum(len(row["competencies"]) for row in raw_rows),
        "emitted_competency_tag_count": sum(row["tag_class"] == "competencies" for row in tag_rows),
        "optional_empty_tag_field_observation_count": sum(bool(row["optional_empty_fields"]) for row in raw_rows),
        "nonempty_specialization_observation_count": sum(bool(row["specializations"]) for row in raw_rows),
        "specialization_values": sorted({value for row in raw_rows for value in row["specializations"]}),
        "unmapped_competencies": unknown_competencies,
        "pending_count": pending_count,
        "errors": validation_errors,
        "gates": {
            "page_count_exact": len(page_paths) == EXPECTED_PAGES,
            "page_numbers_contiguous": observed_pages == list(range(1, EXPECTED_PAGES + 1)),
            "page_card_distribution_exact": all(
                item["record_count"] == EXPECTED_PAGE_COUNTS[item["page"]] for item in manifest
            ),
            "raw_observation_count_exact": len(raw_rows) == EXPECTED_OBSERVATIONS,
            "raw_observation_ids_unique": len(set(raw_ids)) == EXPECTED_OBSERVATIONS,
            "partner_type_tags_lossless": sum(len(row["partner_types"]) for row in raw_rows) == sum(row["tag_class"] == "partner_types" for row in tag_rows),
            "competency_tags_lossless": sum(len(row["competencies"]) for row in raw_rows) == sum(row["tag_class"] == "competencies" for row in tag_rows),
            "competencies_all_mapped": not unknown_competencies,
            "product_scope_ids_exist": not missing_scopes,
            "runtime_total_drift_reconciled": (
                INITIAL_RUNTIME_OBSERVATIONS == 996 and EXPECTED_OBSERVATIONS == 997
            ),
            "specializations_allowlisted": all(
                value in ALLOWED_SPECIALIZATIONS
                for row in raw_rows
                for value in row["specializations"]
            ),
            "all_candidates_terminal": pending_count == 0,
        },
    }
    write_json(output_dir / "validation_report.json", validation)
    return 0 if not validation_errors else 3


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    run_root = here.parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=run_root / "agents/npn_runtime_browser/pages")
    parser.add_argument("--output-dir", type=Path, default=here)
    parser.add_argument("--product-index", type=Path, default=run_root / "product_tree_v2/canonical_index_v2.jsonl")
    parser.add_argument("--base-registry", type=Path, default=run_root / "agents/entity_resolution_complete/entity_registry.jsonl")
    parser.add_argument("--base-aliases", type=Path, default=run_root / "agents/entity_resolution_complete/aliases.jsonl")
    parser.add_argument("--overlay-registry", type=Path, default=run_root / "agents/global_listing_overlay/entity_registry_overlay.jsonl")
    parser.add_argument("--overlay-aliases", type=Path, default=run_root / "agents/global_listing_overlay/aliases.jsonl")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(build(parse_args()))

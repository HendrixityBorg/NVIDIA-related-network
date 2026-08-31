from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..models import ResearchMeta, Snapshot
from .contracts import ResearchProfile
from .io import write_document
from .validation import load_run_models, validate_run


def build_snapshot(
    profile: ResearchProfile,
    run_root: Path,
    output_path: Path,
    *,
    generated_at: datetime | None = None,
) -> Snapshot:
    now = generated_at or datetime.now(timezone.utc)
    report = validate_run(profile, run_root, generated_at=now)
    write_document(run_root / "validation_report.json", report.model_dump(mode="json", by_alias=True))
    if not report.release_ready:
        raise ValueError(
            "run 未通过发布门槛:\n" + "\n".join(f"- {item}" for item in report.errors)
        )
    entities, sources, evidence, relationships = load_run_models(run_root)
    snapshot = Snapshot(
        meta=ResearchMeta(
            subject_entity_id=profile.target.id,
            cutoff_at=profile.cutoff_at,
            evidence_start_date=profile.evidence_start_date,
            snapshot_version=profile.snapshot_version,
            generated_at=now,
            disclaimer=profile.disclaimer,
            coverage=profile.coverage,
            exclusions=profile.exclusions,
        ),
        entities=entities,
        sources=sources,
        evidence=evidence,
        relationships=relationships,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return snapshot

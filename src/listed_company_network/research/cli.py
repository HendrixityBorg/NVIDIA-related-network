from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .build import build_snapshot
from .case import verify_case
from .contracts import ResearchProfile
from .counterparty import build_counterparty_tasks
from .io import load_document, write_document, write_jsonl
from .project import initialise_run
from .validation import load_run_models, validate_run


def load_profile(path: str | Path) -> ResearchProfile:
    return ResearchProfile.model_validate(load_document(Path(path)))


def execute(args: Any) -> dict:
    if args.command == "init-run":
        profile = load_profile(args.profile)
        initialise_run(profile, Path(args.run), overwrite=args.overwrite)
        return {"status": "created", "run": str(Path(args.run).resolve())}
    if args.command == "review-tasks":
        profile = load_profile(args.profile)
        run_root = Path(args.run)
        entities, _, _, relationships = load_run_models(run_root)
        tasks = build_counterparty_tasks(profile, entities, relationships)
        target = run_root / "review/counterparty_tasks.jsonl"
        write_jsonl(target, [item.model_dump(mode="json") for item in tasks])
        return {"status": "written", "path": str(target), "count": len(tasks)}
    if args.command == "validate-run":
        profile = load_profile(args.profile)
        run_root = Path(args.run)
        report = validate_run(profile, run_root)
        write_document(
            run_root / "validation_report.json",
            report.model_dump(mode="json", by_alias=True),
        )
        return report.model_dump(mode="json", by_alias=True)
    if args.command == "build-snapshot":
        profile = load_profile(args.profile)
        snapshot = build_snapshot(profile, Path(args.run), Path(args.output))
        return {
            "status": "built",
            "output": str(Path(args.output).resolve()),
            "counts": {
                "entities": len(snapshot.entities),
                "sources": len(snapshot.sources),
                "evidence": len(snapshot.evidence),
                "relationships": len(snapshot.relationships),
            },
        }
    if args.command == "verify-case":
        return verify_case(Path(args.manifest))
    raise ValueError(f"unknown research command: {args.command}")

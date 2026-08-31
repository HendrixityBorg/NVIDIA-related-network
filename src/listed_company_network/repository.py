from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Snapshot


def default_data_path() -> Path:
    configured = os.getenv("LCN_DATA_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "snapshot_2026-08-25.json"


class SnapshotRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_data_path()
        if not self.path.is_file():
            raise FileNotFoundError(f"snapshot not found: {self.path}")
        with self.path.open(encoding="utf-8") as handle:
            self.snapshot = Snapshot.model_validate(json.load(handle))

        self.entities = {item.id: item for item in self.snapshot.entities}
        self.sources = {item.id: item for item in self.snapshot.sources}
        self.evidence = {item.id: item for item in self.snapshot.evidence}
        self.relationships = {item.id: item for item in self.snapshot.relationships}
        self._validate_references()

    def _validate_references(self) -> None:
        errors: list[str] = []
        for entity in self.entities.values():
            if entity.ultimate_parent_id and entity.ultimate_parent_id not in self.entities:
                errors.append(
                    f"entity {entity.id} references missing parent {entity.ultimate_parent_id}"
                )
        for evidence in self.evidence.values():
            if evidence.source_id not in self.sources:
                errors.append(
                    f"evidence {evidence.id} references missing source {evidence.source_id}"
                )
        for relation in self.relationships.values():
            for entity_id in (relation.source_entity_id, relation.target_entity_id):
                if entity_id not in self.entities:
                    errors.append(
                        f"relationship {relation.id} references missing entity {entity_id}"
                    )
            for evidence_id in relation.evidence_ids:
                if evidence_id not in self.evidence:
                    errors.append(
                        f"relationship {relation.id} references missing evidence {evidence_id}"
                    )
        if errors:
            raise ValueError("invalid snapshot references:\n" + "\n".join(errors))

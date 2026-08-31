from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, TypeVar

import yaml
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def load_document(path: str | Path) -> Any:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if target.suffix.casefold() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def write_document(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if target.suffix.casefold() in {".yaml", ".yml"}:
        rendered = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    else:
        rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    target.write_text(rendered, encoding="utf-8")


def read_jsonl(path: str | Path, model: type[T] | None = None) -> list[T] | list[dict[str, Any]]:
    target = Path(path)
    if not target.is_file():
        return []
    rows: list[Any] = []
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{target}:{line_number}: invalid JSON") from exc
        rows.append(model.model_validate(raw) if model else raw)
    return rows


def write_jsonl(path: str | Path, rows: Iterable[Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered: list[str] = []
    for row in rows:
        if isinstance(row, BaseModel):
            row = row.model_dump(mode="json")
        rendered.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    target.write_text("\n".join(rendered) + ("\n" if rendered else ""), encoding="utf-8")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_id(prefix: str, *values: object) -> str:
    raw = "|".join(str(value) for value in values)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"

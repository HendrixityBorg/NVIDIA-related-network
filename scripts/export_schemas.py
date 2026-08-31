from __future__ import annotations

import json
from pathlib import Path

from listed_company_network.models import Snapshot
from listed_company_network.research.contracts import (
    CounterpartyReviewDecision,
    CounterpartyReviewTask,
    ResearchProfile,
    SourceCandidate,
    StageReport,
    ValidationReport,
)


SCHEMAS = {
    "research_profile": ResearchProfile,
    "source_candidate": SourceCandidate,
    "stage_report": StageReport,
    "counterparty_review_task": CounterpartyReviewTask,
    "counterparty_review_decision": CounterpartyReviewDecision,
    "validation_report": ValidationReport,
    "snapshot": Snapshot,
}


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "schemas"
    output.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMAS.items():
        (output / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(by_alias=True), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()

import importlib.util
from pathlib import Path

from arti.research_policy import ResearchedEntityResolution


BUILDER_PATH = (
    Path(__file__).resolve().parents[1]
    / "runs/2026-08-25-run-003/agents/relationship_review_complete/build_relationship_review.py"
)
SPEC = importlib.util.spec_from_file_location("relationship_review_policy_builder", BUILDER_PATH)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def test_entity_resolution_evidence_is_materialized_without_relationship_credit():
    researched = ResearchedEntityResolution.model_validate(
        {
            "resolution_id": "resolution-denso",
            "candidate_name": "DENSO",
            "candidate_review_ids": ["candidate-denso"],
            "observation_ids": ["obs-denso"],
            "research_status": "researched_terminal",
            "terminal_category": "resolved_inferred_parent",
            "selected_entity_id": "denso",
            "resolution_confidence": 60,
            "inferred_entity_resolution": True,
            "exact_alias_search_outcome": "ambiguous",
            "research_methods": ["official issuer and ownership research"],
            "research_evidence": [
                {
                    "evidence_id": "issuer-evidence-denso",
                    "url": "https://example.com/denso",
                    "publisher": "DENSO Corporation",
                    "retrieved_at": "2026-08-25T12:00:00Z",
                    "locator": "Investor FAQ / stock information",
                    "supports": "Observed operating name most likely maps to the listed issuer.",
                }
            ],
            "rationale": "Official issuer context supports the most likely listed entity while retaining inference.",
        }
    )
    evidence_by_fp = {}
    evidence_ids = BUILDER.materialize_entity_resolution_evidence(
        researched, "decision-denso", evidence_by_fp
    )
    assert len(evidence_ids) == 1
    record = next(iter(evidence_by_fp.values()))
    assert record["source_family"] == "entity_resolution"
    assert record["evidence_purpose"] == (
        "entity_resolution_only_no_relationship_score_credit"
    )
    assert record["input_decision_ids"] == ["decision-denso"]

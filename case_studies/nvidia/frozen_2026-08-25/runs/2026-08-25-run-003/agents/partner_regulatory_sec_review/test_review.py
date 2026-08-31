import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class SecDirectionReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "build_review.py")], check=True, capture_output=True, text=True)

    def rows(self, name): return [json.loads(x) for x in (ROOT / name).read_text().splitlines() if x]

    def test_coreweave_supplier_direction_is_explicit(self):
        claims = [r for r in self.rows("relationship_claims.jsonl") if r["subject_entity_id"] == "coreweave" and r["relationship_type"] == "supplier"]
        self.assertTrue(claims)
        self.assertTrue(all((r["object_entity_id"], r["direction"], r["fact_status"]) == ("nvidia", "supplies_to", "confirmed") for r in claims))
        self.assertTrue(any("$320 million" in r["quantitative_mentions"] for r in claims))

    def test_coreweave_dual_role_is_supported_by_explicit_evidence(self):
        claims = self.rows("relationship_claims.jsonl")
        customer = next(r for r in claims if r["subject_entity_id"] == "nvidia" and r["object_entity_id"] == "coreweave" and r["relationship_type"] == "customer")
        supplier = next(r for r in claims if r["subject_entity_id"] == "coreweave" and r["object_entity_id"] == "nvidia" and r["relationship_type"] == "supplier")
        self.assertEqual(("confirmed", "explicit"), (customer["fact_status"], customer["directness"]))
        self.assertEqual(("confirmed", "explicit"), (supplier["fact_status"], supplier["directness"]))

    def test_compatibility_does_not_create_direction(self):
        decisions = [r for r in self.rows("decision_ledger.jsonl") if r["canonical_entity_id"] == "entity_73ba1f6eff1a76fc"]
        self.assertTrue(decisions)
        self.assertTrue(all(r["decision"] == "rejected_non_directional" for r in decisions))

    def test_iren_dual_contract_direction(self):
        claims = self.rows("relationship_claims.jsonl")
        supplier = next(r for r in claims if r["subject_entity_id"] == "entity_045454fe093dec63" and r["relationship_type"] == "supplier")
        customer = next(r for r in claims if r["object_entity_id"] == "entity_045454fe093dec63" and r["relationship_type"] == "customer")
        self.assertEqual(("confirmed", "cloud-services"), (supplier["fact_status"], supplier["product_scope_id"]))
        self.assertEqual(("confirmed", "explicit"), (customer["fact_status"], customer["directness"]))

    def test_fabrinet_revenue_share_is_supplier_evidence(self):
        claim = next(r for r in self.rows("relationship_claims.jsonl") if r["subject_entity_id"] == "fabrinet")
        self.assertEqual(("supplier", "confirmed", "networking"), (claim["relationship_type"], claim["fact_status"], claim["product_scope_id"]))
        normalized = {x.replace(" ", "") for x in claim["quantitative_mentions"]}
        self.assertTrue({"16.3%", "27.6%", "35.1%"} <= normalized)

    def test_media_partnership_and_risk_cooccurrence_stay_rejected(self):
        decisions = {r["mention_id"]: r for r in self.rows("decision_ledger.jsonl")}
        for mention_id in ("regmention_46992801d23486e57b39", "regmention_25dbefebf9f8e3193cc7", "regmention_00cbf4e8053cceefc96b"):
            self.assertEqual("rejected_non_directional", decisions[mention_id]["decision"])

    def test_all_contexts_terminal_without_pending(self):
        decisions = self.rows("decision_ledger.jsonl")
        collection = json.loads((ROOT.parent / "partner_regulatory_review" / "collection_summary.json").read_text())
        self.assertEqual(collection["mention_contexts"], len(decisions))
        self.assertTrue(all(r["status"] == "terminal" and r["pending"] is False for r in decisions))

    def test_bitdeer_direct_purchase_is_confirmed(self):
        claim = next(r for r in self.rows("relationship_claims.jsonl") if r["object_entity_id"] == "npn-issuer-ad81309481717c2b")
        self.assertEqual(("customer", "confirmed", "explicit"), (claim["relationship_type"], claim["fact_status"], claim["directness"]))
        self.assertIn("$13.2 million", claim["quantitative_mentions"])

    def test_new_product_use_without_direct_seller_stays_inferred(self):
        claims = self.rows("relationship_claims.jsonl")
        for entity in ("npn-issuer-ea0992ccf8964407", "npn-issuer-707b51d1c6951b12", "weride", "aurora_innovation", "telus"):
            claim = next(r for r in claims if r["object_entity_id"] == entity and r["relationship_type"] == "customer")
            self.assertEqual(("inferred", "unclear"), (claim["fact_status"], claim["directness"]))
            self.assertLessEqual(claim["confidence_score"], 59)

    def test_collaboration_equity_and_platform_dependency_do_not_force_direction(self):
        claims = self.rows("relationship_claims.jsonl")
        endpoints = {r["subject_entity_id"] for r in claims} | {r["object_entity_id"] for r in claims}
        self.assertTrue({"arm_holdings", "magna", "npn-issuer-f83a62c5a610a538"}.isdisjoint(endpoints))

    def test_collection_gate_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "collection_summary.json").write_text(json.dumps({"retrieved_documents": 0}))
            result = subprocess.run([sys.executable, str(ROOT / "build_review.py"), "--input-dir", str(p)], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("retrieved_documents must be > 0", result.stderr)


if __name__ == "__main__": unittest.main()

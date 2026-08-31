import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class ResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "build_resolution.py")], check=True, capture_output=True, text=True)

    def rows(self, name):
        return [json.loads(x) for x in (ROOT / name).read_text().splitlines() if x]

    def test_all_950_are_terminal(self):
        rows = self.rows("mapping_decision_ledger.jsonl")
        self.assertEqual(950, len(rows))
        self.assertEqual(0, sum(bool(r["pending"]) for r in rows))

    def test_false_homonym_does_not_become_issuer(self):
        rejected = {r["candidate_name"] for r in self.rows("rejected_candidates.jsonl")}
        resolved = {r["npn_name"] for r in self.rows("resolved_parent_mappings.jsonl")}
        self.assertTrue({"Compugen Inc", "TEN Inc", "Cronos"} <= rejected)
        self.assertFalse({"Compugen Inc", "TEN Inc", "Cronos"} & resolved)

    def test_parent_endpoint_is_inferred_and_dual_evidenced(self):
        row = next(r for r in self.rows("resolved_parent_mappings.jsonl") if r["npn_name"] == "NTT Data Group Corporation")
        self.assertEqual("subsidiary_to_parent", row["resolution_kind"])
        self.assertEqual("inferred", row["fact_status_recommendation"])
        self.assertGreaterEqual(len(row["mapping_evidence_ids"]), 3)


if __name__ == "__main__":
    unittest.main()

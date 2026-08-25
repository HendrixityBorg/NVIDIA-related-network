import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class NormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "build.py")], check=True, capture_output=True, text=True)

    def rows(self, name):
        return [json.loads(x) for x in (ROOT / name).read_text().splitlines() if x]

    def test_known_coreweave_duplicate(self):
        row = next(r for r in self.rows("canonical_partner_universe.jsonl") if "coreweave" in r["member_entity_ids"])
        self.assertEqual({"coreweave", "npn-issuer-0f21b8aa69ac3580"}, set(row["member_entity_ids"]))
        self.assertTrue(any(b["identifier_type"] == "exchange_ticker" and b["identifier_value"] == "nasdaq:CRWV" for b in row["merge_bases"]))

    def test_original_security_and_relationship_data_retained(self):
        row = next(r for r in self.rows("canonical_partner_universe.jsonl") if {"alibaba", "entity_448ee47d0990d0c2"} <= set(r["member_entity_ids"]))
        self.assertIn("hong kong stock exchange:9988", {f"{s['exchange'].lower()}:{s['ticker']}" for s in row["securities"]})
        self.assertGreater(len(row["partner_relationship_ids"]), 0)
        self.assertEqual(set(row["relationship_source_ids"]), {s["id"] for s in row["relationship_sources"]})

    def test_multilisting_is_flagged_not_discarded(self):
        rows = {r["canonical_entity_id"]: r for r in self.rows("manual_multilisting_review.jsonl")}
        alibaba = next(r for r in self.rows("canonical_partner_universe.jsonl") if "alibaba" in r["member_entity_ids"])
        self.assertIn(alibaba["canonical_entity_id"], rows)
        self.assertGreaterEqual(len(rows[alibaba["canonical_entity_id"]]["active_exchange_ticker_candidates"]), 2)


if __name__ == "__main__": unittest.main()

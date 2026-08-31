#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
def rows(name): return [json.loads(x) for x in (HERE/name).read_text(encoding="utf-8").splitlines() if x.strip()]

frontier, candidates, evidence, decisions, access = [rows(x) for x in (
    "source_frontier.jsonl", "candidates.jsonl", "evidence.jsonl", "decision_ledger.jsonl", "access_audit.jsonl")]
errors=[]
terminals={"regulatory_hit","searched_no_hit","access_blocked","public_search_unavailable"}
if len(frontier)!=104: errors.append(f"frontier expected 104 got {len(frontier)}")
if len({x['issuer_id'] for x in frontier})!=104: errors.append("frontier issuer IDs not unique/complete")
if any(x['terminal_status'] not in terminals for x in frontier): errors.append("invalid frontier terminal")
if any(not x.get('executed_query') or not x.get('searched_scope') for x in frontier): errors.append("frontier query/scope missing")
if len(decisions)!=104 or len({x['partner_entity_id'] for x in decisions})!=104: errors.append("decision coverage not 104")
if {x['candidate_id'] for x in candidates}!={x['candidate_id'] for x in evidence}: errors.append("candidate/evidence mismatch")
evidence_ids={x['evidence_id'] for x in evidence}
for candidate in candidates:
    refs=candidate.get('source_evidence_ids', [])
    if len(refs)!=1 or any(x not in evidence_ids for x in refs): errors.append(f"candidate evidence refs {candidate['candidate_id']}")
    explicit=candidate.get('direction_review')=='explicit_procurement_or_supply'
    if explicit != bool(candidate.get('proposed_claim')): errors.append(f"proposed claim gate {candidate['candidate_id']}")
    if candidate.get('proposed_claim') and candidate['proposed_claim'].get('evidence_ids')!=refs: errors.append(f"claim evidence refs {candidate['candidate_id']}")
if any(x.get('access_control_bypassed') is not False for x in access): errors.append("access bypass flag")
claims=[c for d in decisions for c in d['new_claims']]
for c in claims:
    if not (c['subject_entity_id']=='nvidia' and c['object_entity_id']!='nvidia' and c['direction']=='sells_to' and c['relationship_type']=='customer'):
        errors.append(f"reversed/invalid claim {c['claim_id']}")
    if c['source_kind']!='regulatory_filing' or c['fact_status']!='confirmed': errors.append(f"claim cap violation {c['claim_id']}")
    if c['directness'] not in {'direct','indirect','unclear'}: errors.append(f"directness {c['claim_id']}")
report={"status":"pass" if not errors else "fail", "pending_count":0 if not errors else len(errors),
        "errors":errors, "frontier_rows":len(frontier), "decision_rows":len(decisions),
        "candidate_rows":len(candidates), "evidence_rows":len(evidence), "claim_rows":len(claims),
        "terminal_counts":dict(Counter(x['terminal_status'] for x in frontier)),
        "access_control_bypass":False, "snapshot_modified":False}
(HERE/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
raise SystemExit(0 if not errors else 1)

#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def rows(name): return [json.loads(x) for x in (ROOT/name).read_text().splitlines() if x.strip()]
def check(condition, label, checks):
    checks.append({"check":label,"passed":bool(condition)})

def main():
    src=rows("source_frontier.jsonl"); pages=rows("page_processing.jsonl"); raw=rows("raw_observations.jsonl"); listed=rows("listed_candidates.jsonl"); hold=rows("13f_holdings.jsonl"); acq=rows("acquisition_review.jsonl"); conflicts=rows("conflicts.jsonl")
    checks=[]; source_ids={x["source_id"] for x in src}; obs_ids={x["observation_id"] for x in raw}
    expected=sum(x.get("page_count",0) for x in src)
    expected_by_source={x["source_id"]:x.get("page_count",0) for x in src if x.get("page_count")}
    actual_by_source=Counter(x["source_id"] for x in pages)
    check(len(src)==9,"exactly 10-K + 13F cover/table + six PDFs",checks)
    check(len(source_ids)==9 and all(x.get("access_state")=="processed" for x in src),"all scoped sources uniquely identified and processed",checks)
    check(all(len(x.get("sha256", ""))==64 and x.get("byte_size",0)>0 and x.get("url") and x.get("publisher") and x.get("access_restrictions") for x in src),"source URL/publisher/hash/size/access metadata complete",checks)
    check(expected==379 and len(pages)==379,"PDF page total reconciles to 379",checks)
    check(all(actual_by_source[k]==v for k,v in expected_by_source.items()),"per-PDF page counts reconcile",checks)
    check(len({x["page_id"] for x in pages})==379,"unique page ids",checks)
    states=Counter(x["terminal_state"] for x in pages)
    check(set(states)<={"processed_with_candidate","processed_no_candidate","inaccessible"},"allowed page terminal states only",checks)
    check(states["processed_with_candidate"]==153 and states["processed_no_candidate"]==226 and states["inaccessible"]==0,"all pages closed: 153 candidate, 226 no-candidate, 0 inaccessible",checks)
    check(all(x["source_id"] in source_ids for x in raw),"all raw observations resolve source",checks)
    check(all(x.get("evidence_locator") and x.get("source_url") and x.get("publisher") and x.get("retrieved_at") and x.get("content_fingerprint") for x in raw),"all raw observations carry evidence/provenance",checks)
    check(all(x["observation_id"] in obs_ids for x in listed),"all listed candidates resolve observation",checks)
    check(len(hold)==8 and [x["row_number"] for x in hold]==list(range(1,9)),"13F all 8 rows in order",checks)
    check(all(x["period_of_report"]=="2026-06-30" and x["accession"]=="0001045810-26-000065" and x["is_amendment"] is False for x in hold),"13F period/accession/non-amendment",checks)
    check(sum(x["value_usd"] for x in hold)==63439974569,"13F value total $63,439,974,569",checks)
    check(all(x["value_unit"].startswith("USD") and x["put_call"] is None and x["share_type"]=="SH" and x["shares"]>0 for x in hold),"13F units/put-call/share fields",checks)
    class_counts=Counter("private" if x["listing_status"].startswith("private") else "listed" for x in hold)
    check(class_counts=={"listed":7,"private":1},"13F 7 listed + 1 private classification",checks)
    check(any(x["target"]=="Mellanox Technologies, Ltd." and "delisted" in x["status_at_cutoff"] for x in acq),"completed public acquisition separated from current graph",checks)
    check(any(x["target"].startswith("3dfx") and "asset purchase" in x["status_at_cutoff"] for x in acq),"asset purchase distinguished from company acquisition",checks)
    check(all(x["status"]=="resolved" for x in conflicts),"zero unresolved conflicts",checks)
    check(all(x.get("local_cache_state")=="removed_before_delivery" and "local_path" not in x for x in src),"public frontier has no local cache paths",checks)
    check(not (ROOT/"source_files").exists(),"temporary full source cache removed",checks)
    report={"generated_at":"2026-08-25T00:00:00+08:00","passed":all(x["passed"] for x in checks),"checks":checks,"counts":{"sources":len(src),"pdf_pages":len(pages),"page_terminal_states":states,"raw_observations":len(raw),"listed_candidate_occurrences":len(listed),"unique_listed_candidate_entities":len({x["entity_name"] for x in listed}),"13f_rows":len(hold),"13f_classification":class_counts,"acquisition_review_rows":len(acq)}}
    (ROOT/"validation_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2,default=dict))
    raise SystemExit(0 if report["passed"] else 1)
if __name__=="__main__": main()

#!/usr/bin/env python3
"""Low-frequency, public-only APAC Partner regulatory review collector.

The collector never logs in, solves a CAPTCHA, replays a private browser token,
or attempts to evade a WAF/rate limit.  It writes only review artefacts in this
directory and never edits the canonical universe or snapshot.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin

import requests
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "agents/partner_regulatory_entity_normalization/canonical_partner_universe.jsonl"
OUT = Path(__file__).resolve().parent
START = "2025-01-01"
END = "2026-08-25"
REGIONS = {"TW", "JP", "KR", "CN", "HK", "IN", "AU", "SG", "MY", "VN"}
UA = "listed-company-network-apac-regulatory-review/1.0 public-no-login research"
TERMINALS = {"regulatory_hit", "searched_no_hit", "access_blocked", "public_search_unavailable"}
TERMS = ["NVIDIA", "Nvidia", "英伟达", "英偉達", "輝達", "エヌビディア", "엔비디아"]
TERM_RE = re.compile("|".join(re.escape(x) for x in TERMS), re.I)
SPACE_RE = re.compile(r"\s+")
TAG_RE = re.compile(r"<[^>]+>")

KOREAN = {
    "doosan_enerbility": ("두산에너빌리티", "00159616"),
    "gs_ec": ("GS건설", "00120030"),
    "hyundai_motor": ("현대자동차", "00164742"),
    "lg_cns": ("엘지씨엔에스", "00139834"),
    "lg_electronics": ("엘지전자", "00401731"),
    "lg_energy_solution": ("엘지에너지솔루션", "01515323"),
    "mds_tech": ("MDS테크", "00445841"),
    "naver": ("NAVER", "00266961"),
    "samsung_electronics": ("삼성전자", "00126380"),
    "samsung_sds": ("삼성에스디에스", "00126186"),
    "snet_systems": ("에스넷", "00264635"),
    "uniquest": ("유니퀘스트", "00414601"),
    "xiilab": ("씨이랩", "00991298"),
}

PROBE_URLS = {
    "JP": "https://disclosure2.edinet-fsa.go.jp/WEee0070.aspx",
    "HK": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en",
    "AU": "https://www.asx.com.au/asx/v2/statistics/announcements.do",
    "SG": "https://www.sgx.com/securities/company-announcements",
    "MY": "https://www.bursamalaysia.com/market_information/announcements/company_announcement",
    "VN": "https://www.hsx.vn/Modules/Cms/Web/AnPham/62d2fe37-f8ce-4b1d-bee2-6e95979f7166",
}


def sid(prefix: str, *parts: object) -> str:
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:20]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows), encoding="utf-8")


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def visible(raw: str) -> str:
    return SPACE_RE.sub(" ", html.unescape(TAG_RE.sub(" ", raw))).strip()


def contexts(text: str, radius: int = 650) -> list[str]:
    out = []
    for match in TERM_RE.finditer(text):
        value = SPACE_RE.sub(" ", text[max(0, match.start() - radius):match.end() + radius]).strip()
        if value not in out:
            out.append(value)
    return out


def pdf_pages(path: Path) -> list[tuple[int, str]]:
    out = []
    reader = PdfReader(str(path))
    for index, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if TERM_RE.search(text):
            out.append((index, text))
    return out


class Collector:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Encoding": "identity"})
        self.frontier: list[dict] = []
        self.access: list[dict] = []
        self.raw_hits: list[dict] = []
        self.universe = []

    def audit(self, issuer: dict, source_id: str, url: str, method: str, status: str,
              code: int | None, size: int, detail: str, result_count: int | None = None) -> None:
        self.access.append({
            "attempt_id": sid("apac_access", issuer["canonical_entity_id"], source_id, url, len(self.access)),
            "issuer_id": issuer["canonical_entity_id"], "source_id": source_id,
            "attempted_url": url, "method": method, "attempted_at": now(),
            "http_status": code, "bytes": size, "outcome": status,
            "detail": detail, "result_count": result_count,
            "access_mode": "public_no_login", "access_control_bypassed": False,
        })

    def add_frontier(self, issuer: dict, region: str, source_id: str, terminal: str,
                     query: str, result_count: int, scope: str, note: str, url: str) -> None:
        assert terminal in TERMINALS
        tickers = sorted({s.get("ticker") for s in issuer["securities"] if s.get("listing_region_code") == region and s.get("ticker")})
        self.frontier.append({
            "frontier_id": sid("apac_frontier", issuer["canonical_entity_id"], region, source_id),
            "issuer_id": issuer["canonical_entity_id"], "legal_name": issuer["legal_name"],
            "region_code": region, "tickers": tickers, "source_id": source_id,
            "date_from": START, "date_to": END, "query_terms": TERMS,
            "executed_query": query, "searched_scope": scope, "result_count": result_count,
            "terminal_status": terminal, "attempted_url": url, "note": note,
        })

    def load(self) -> None:
        for row in read_rows(CANONICAL):
            if {s.get("listing_region_code") for s in row.get("securities", [])} & REGIONS:
                self.universe.append(row)

    def dart(self, issuer: dict) -> None:
        iid = issuer["canonical_entity_id"]
        kr_name, cik = KOREAN[iid]
        url = "https://dart.fss.or.kr/dsab007/search.ax"
        data = {
            "currentPage": "1", "maxResults": "100", "keyword": "NVIDIA|엔비디아",
            "textCrpNm": kr_name, "textCrpCik": cik, "startDate": "20250101",
            "endDate": "20260825", "docType": "", "reportName": "", "synonym": "",
        }
        try:
            r = self.s.post(url, data=data, timeout=50)
            r.raise_for_status()
            total_m = re.search(r'id="totalCnt" value="([\d,]+)"', r.text)
            total = int(total_m.group(1).replace(",", "")) if total_m else 0
            self.audit(issuer, "kr_dart", url, "POST", "processed", r.status_code, len(r.content),
                       f"exact DART corp CIK {cik}; body query NVIDIA|엔비디아", total)
        except Exception as exc:
            self.audit(issuer, "kr_dart", url, "POST", "access_blocked", getattr(getattr(exc, "response", None), "status_code", None), 0, str(exc))
            self.add_frontier(issuer, "KR", "kr_dart", "access_blocked", f"CIK={cik}; NVIDIA|엔비디아", 0,
                              "DART exact-company body search", str(exc), url)
            return
        hits = []
        pattern = re.compile(r'href="(/dsaf001/main\.do\?rcpNo=(\d+)(?:&amp;|&)dcmNo=(\d+)(?:&amp;|&)keyword=[^"]+)".*?<td>(.*?)</td>', re.S)
        for href, rcp, dcm, snippet in pattern.findall(r.text):
            clean = visible(snippet)
            hits.append((href.replace("&amp;", "&"), rcp, dcm, clean))
        # Only a representative newest filing is fetched per duplicate repeated disclosure.
        if hits:
            href, rcp, dcm, snippet = hits[0]
            main_url = urljoin("https://dart.fss.or.kr", href)
            try:
                main = self.s.get(main_url, timeout=50)
                main.raise_for_status()
                m = re.search(r'viewDoc\("(\d+)", "(\d+)", "(\d+)", "(\d+)", "(\d+)", "([^"]+)"', main.text)
                if not m:
                    raise RuntimeError("viewer parameters not found")
                viewer_url = "https://dart.fss.or.kr/report/viewer.do?" + urlencode({
                    "rcpNo": m.group(1), "dcmNo": m.group(2), "eleId": m.group(3),
                    "offset": m.group(4), "length": m.group(5), "dtd": m.group(6),
                    "keyword": "NVIDIA", "searchGubun": "1",
                })
                body = self.s.get(viewer_url, timeout=100)
                body.raise_for_status()
                text = visible(body.text)
                ctx = contexts(text)
                self.audit(issuer, "kr_dart_document", viewer_url, "GET", "processed", body.status_code,
                           len(body.content), "retrieved full filing viewer with server-side NVIDIA highlights", len(ctx))
                for j, excerpt in enumerate(ctx):
                    self.raw_hits.append({
                        "issuer_id": iid, "region_code": "KR", "source_id": "kr_dart",
                        "source_kind": "regulatory_filing", "url": main_url,
                        "document_url": viewer_url, "publisher": "Financial Supervisory Service (DART)",
                        "published_at": f"{rcp[:4]}-{rcp[4:6]}-{rcp[6:8]}",
                        "form_type": "DART periodic/report filing", "locator": f"viewer NVIDIA context {j+1}",
                        "excerpt": excerpt, "origin_publication_id": rcp,
                    })
            except Exception as exc:
                self.audit(issuer, "kr_dart_document", main_url, "GET", "document_retrieval_failed", None, 0, str(exc))
        terminal = "regulatory_hit" if any(x["issuer_id"] == iid for x in self.raw_hits) else "searched_no_hit"
        self.add_frontier(issuer, "KR", "kr_dart", terminal, f"DART CIK={cik}; body=NVIDIA|엔비디아", len(hits),
                          "exact-company DART body full-text search; newest duplicate filing retrieved", "No matching filing" if not hits else "matching filing body retrieved", url)

    def cninfo_global(self, cn_issuers: list[dict]) -> None:
        by_code = {}
        for issuer in cn_issuers:
            for sec in issuer["securities"]:
                if sec.get("listing_region_code") == "CN" and sec.get("ticker"):
                    by_code[str(sec["ticker"]).zfill(6)] = issuer
        found: dict[str, list[dict]] = defaultdict(list)
        seen = set()
        base = "https://www.cninfo.com.cn/new/fulltextSearch/full"
        for term in ("NVIDIA", "英伟达"):
            page = 1
            while True:
                params = {"searchkey": term, "sdate": START, "edate": END, "isfulltext": "true",
                          "sortName": "pubdate", "sortType": "desc", "pageNum": page, "pageSize": 30}
                url = base + "?" + urlencode(params)
                try:
                    r = self.s.get(url, timeout=45)
                    r.raise_for_status()
                    payload = r.json()
                except Exception as exc:
                    # one global failure is copied to every affected issuer below
                    for issuer in cn_issuers:
                        self.audit(issuer, "cn_cninfo", url, "GET", "access_blocked", getattr(getattr(exc, "response", None), "status_code", None), 0, str(exc))
                    break
                anns = payload.get("announcements") or []
                if page == 1:
                    for issuer in cn_issuers:
                        self.audit(issuer, "cn_cninfo", url, "GET", "processed", r.status_code, len(r.content),
                                   f"global full-text corpus query {term}; results filtered by exact secCode", payload.get("totalAnnouncement"))
                for ann in anns:
                    if ann.get("secCode") in by_code and ann.get("announcementId") not in seen:
                        seen.add(ann["announcementId"])
                        found[ann["secCode"]].append(ann)
                total = int(payload.get("totalRecordNum") or 0)
                if not anns or page * 30 >= total:
                    break
                page += 1
                time.sleep(0.18)
        for code, issuer in by_code.items():
            iid = issuer["canonical_entity_id"]
            valid = 0
            for ann in found.get(code, []):
                pdf_url = "https://static.cninfo.com.cn/" + ann["adjunctUrl"].lstrip("/")
                try:
                    r = self.s.get(pdf_url, timeout=90)
                    r.raise_for_status()
                    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                        f.write(r.content); f.flush()
                        pages = pdf_pages(Path(f.name))
                    self.audit(issuer, "cn_cninfo_document", pdf_url, "GET", "processed", r.status_code,
                               len(r.content), "downloaded matched official disclosure PDF", len(pages))
                except Exception as exc:
                    self.audit(issuer, "cn_cninfo_document", pdf_url, "GET", "document_retrieval_failed", None, 0, str(exc))
                    continue
                for page_no, text in pages:
                    for j, excerpt in enumerate(contexts(text)):
                        valid += 1
                        ts = int(ann["announcementTime"]) / 1000
                        pub = datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
                        self.raw_hits.append({
                            "issuer_id": iid, "region_code": "CN", "source_id": "cn_cninfo",
                            "source_kind": "regulatory_filing", "url": pdf_url, "document_url": pdf_url,
                            "publisher": "CNINFO (Shenzhen Securities Information Co., Ltd.)",
                            "published_at": pub, "form_type": ann.get("announcementTitle"),
                            "locator": f"PDF page {page_no}, NVIDIA context {j+1}", "excerpt": excerpt,
                            "origin_publication_id": ann["announcementId"],
                        })
            terminal = "regulatory_hit" if valid else "searched_no_hit"
            self.add_frontier(issuer, "CN", "cn_cninfo", terminal,
                              f"CNINFO global body full-text NVIDIA + 英伟达, filtered secCode={code}", len(found.get(code, [])),
                              "complete paginated CNINFO full-text result sets for both terms; exact secCode filtering",
                              "matched PDFs retrieved" if valid else "no exact-issuer result in returned corpus", base)

    def taiwan(self, issuer: dict) -> None:
        iid = issuer["canonical_entity_id"]
        code = next(str(s["ticker"]) for s in issuer["securities"] if s.get("listing_region_code") == "TW")
        listing = f"https://doc.twse.com.tw/server-java/t57sb01?step=1&colorchg=1&co_id={code}&year=115&seamon=&mtype=F&"
        try:
            r = self.s.get(listing, timeout=45)
            r.raise_for_status()
            decoded = r.content.decode("big5", errors="replace")
            # Prefer English 2025 annual report; fall back to Chinese.
            names = re.findall(r'readfile2\("F","' + re.escape(code) + r'","([^"]+(?:FE4|F04)\.pdf)"\)', decoded)
            names = sorted(names, key=lambda x: ("FE4" not in x, x))
            chosen = next((x for x in names if x.startswith("2025_")), names[0] if names else None)
            self.audit(issuer, "tw_mops_document_server", listing, "GET", "processed", r.status_code,
                       len(r.content), "exact company code; year=115; annual-report document family", len(names))
        except Exception as exc:
            self.audit(issuer, "tw_mops_document_server", listing, "GET", "access_blocked", getattr(getattr(exc, "response", None), "status_code", None), 0, str(exc))
            self.add_frontier(issuer, "TW", "tw_mops_document_server", "access_blocked", f"co_id={code}; year=115; mtype=F", 0,
                              "MOPS/TWSE official annual-report document server", str(exc), listing)
            return
        if not chosen:
            self.add_frontier(issuer, "TW", "tw_mops_document_server", "searched_no_hit", f"co_id={code}; year=115; mtype=F", 0,
                              "exact issuer annual-report list", "no 2025 annual report document returned", listing)
            return
        post_url = "https://doc.twse.com.tw/server-java/t57sb01"
        try:
            step = self.s.post(post_url, data={"step": "9", "kind": "F", "co_id": code, "filename": chosen}, timeout=45)
            step.raise_for_status()
            m = re.search(r"href='([^']+\.pdf)'", step.content.decode("big5", errors="replace"))
            if not m:
                raise RuntimeError("MOPS generated PDF link missing")
            pdf_url = urljoin("https://doc.twse.com.tw", m.group(1))
            body = self.s.get(pdf_url, timeout=180)
            body.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(body.content); f.flush()
                pages = pdf_pages(Path(f.name))
            self.audit(issuer, "tw_mops_document", pdf_url, "GET", "processed", body.status_code,
                       len(body.content), f"retrieved official annual report {chosen}", len(pages))
        except Exception as exc:
            self.audit(issuer, "tw_mops_document", post_url, "POST/GET", "document_retrieval_failed", None, 0, str(exc))
            self.add_frontier(issuer, "TW", "tw_mops_document_server", "access_blocked", f"co_id={code}; annual_report={chosen}; full-text terms", 0,
                              "official annual report selected but PDF retrieval/extraction failed", str(exc), listing)
            return
        count = 0
        date_match = re.search(r"_((?:2025|2026)\d{4})(?:F|FE)", chosen)
        published_at = (
            f"{date_match.group(1)[:4]}-{date_match.group(1)[4:6]}-{date_match.group(1)[6:8]}"
            if date_match else "2026-01-01"
        )
        for page_no, text in pages:
            for j, excerpt in enumerate(contexts(text)):
                count += 1
                self.raw_hits.append({
                    "issuer_id": iid, "region_code": "TW", "source_id": "tw_mops_document_server",
                    "source_kind": "regulatory_filing", "url": pdf_url, "document_url": pdf_url,
                    "publisher": "Taiwan Stock Exchange MOPS document server", "published_at": published_at,
                    "form_type": "2025 annual report filed for 2026 shareholders meeting",
                    "locator": f"PDF page {page_no}, NVIDIA context {j+1}", "excerpt": excerpt,
                    "origin_publication_id": chosen,
                })
        self.add_frontier(issuer, "TW", "tw_mops_document_server", "regulatory_hit" if count else "searched_no_hit",
                          f"co_id={code}; 2025 annual report={chosen}; full-text NVIDIA/輝達/英偉達", count,
                          "official 2025 annual report filed in 2026; every extractable page searched",
                          "matching contexts extracted" if count else "no matching context in extractable annual-report text", listing)

    def nse(self, issuer: dict) -> None:
        symbol = next(str(s["ticker"]) for s in issuer["securities"] if s.get("listing_region_code") == "IN")
        url = "https://www.nseindia.com/api/corporate-announcements?" + urlencode({
            "index": "equities", "symbol": symbol, "from_date": "01-01-2025", "to_date": "25-08-2026"})
        try:
            r = self.s.get(url, headers={"Accept": "application/json,text/plain,*/*"}, timeout=60)
            r.raise_for_status(); rows = r.json()
            matches = [x for x in rows if TERM_RE.search(" ".join(str(v or "") for v in x.values()))]
            self.audit(issuer, "in_nse_announcements", url, "GET", "processed", r.status_code, len(r.content),
                       f"exact NSE symbol {symbol}; date-filtered exchange announcement metadata searched for NVIDIA terms", len(matches))
        except Exception as exc:
            self.audit(issuer, "in_nse_announcements", url, "GET", "access_blocked", getattr(getattr(exc, "response", None), "status_code", None), 0, str(exc))
            self.add_frontier(issuer, "IN", "in_nse_announcements", "access_blocked", f"symbol={symbol}; metadata NVIDIA terms", 0,
                              "NSE exact-symbol corporate announcements", str(exc), url)
            return
        for item in matches:
            pdf_url = item.get("attchmntFile")
            extracted = []
            if pdf_url:
                try:
                    body = self.s.get(pdf_url, timeout=100); body.raise_for_status()
                    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                        f.write(body.content); f.flush(); pages = pdf_pages(Path(f.name))
                    for page_no, text in pages:
                        for j, excerpt in enumerate(contexts(text)):
                            extracted.append((page_no, j, excerpt))
                    self.audit(issuer, "in_nse_document", pdf_url, "GET", "processed", body.status_code, len(body.content),
                               "downloaded exact exchange announcement attachment", len(extracted))
                except Exception as exc:
                    self.audit(issuer, "in_nse_document", pdf_url, "GET", "document_retrieval_failed", None, 0, str(exc))
            for page_no, j, excerpt in extracted:
                self.raw_hits.append({
                    "issuer_id": issuer["canonical_entity_id"], "region_code": "IN", "source_id": "in_nse_announcements",
                    "source_kind": "company_news", "url": pdf_url, "document_url": pdf_url,
                    "publisher": "National Stock Exchange of India (issuer announcement attachment)",
                    "published_at": datetime.strptime(item["an_dt"][:11], "%d-%b-%Y").date().isoformat(),
                    "form_type": item.get("desc") or "Corporate announcement", "locator": f"PDF page {page_no}, NVIDIA context {j+1}",
                    "excerpt": excerpt, "origin_publication_id": item.get("seq_id") or item.get("dt"),
                })
        count = sum(1 for x in self.raw_hits if x["issuer_id"] == issuer["canonical_entity_id"] and x["source_id"] == "in_nse_announcements")
        self.add_frontier(issuer, "IN", "in_nse_announcements", "regulatory_hit" if count else "searched_no_hit",
                          f"symbol={symbol}; date-filtered announcement metadata; NVIDIA terms", len(matches),
                          "complete NSE response for exact symbol/date; matching attachments retrieved and full-text searched",
                          "matching exchange-filed company announcement" if count else "no NVIDIA term in returned announcement metadata", url)

    def probe(self, issuer: dict, region: str) -> None:
        url = PROBE_URLS[region]
        source = {"JP":"jp_edinet_fulltext","HK":"hk_hkexnews","AU":"au_asx_announcements","SG":"sg_sgxnet","MY":"my_bursa_announcements","VN":"vn_hose_disclosures"}[region]
        tickers = sorted({s.get("ticker") for s in issuer["securities"] if s.get("listing_region_code") == region and s.get("ticker")})
        try:
            r = self.s.get(url, timeout=35)
            if r.status_code in {401, 403, 429}:
                terminal, outcome, note = "access_blocked", "access_blocked", f"HTTP {r.status_code}; no bypass attempted"
            elif r.status_code >= 500:
                terminal, outcome, note = "access_blocked", "source_unavailable", f"HTTP {r.status_code}; no retry evasion"
            else:
                terminal, outcome, note = "public_search_unavailable", "page_retrieved_no_reproducible_query", "landing/search UI retrieved, but this run could not execute an exact issuer+body+date public query without JS/session interaction"
            self.audit(issuer, source, url, "GET", outcome, r.status_code, len(r.content), note)
        except Exception as exc:
            terminal, note = "access_blocked", str(exc)
            self.audit(issuer, source, url, "GET", "access_blocked", None, 0, note)
        self.add_frontier(issuer, region, source, terminal,
                          f"attempt exact issuer {tickers} + NVIDIA variants + {START}..{END}", 0,
                          "official portal public search/full-text interface probe", note, url)

    def run(self) -> None:
        self.load()
        cn = [x for x in self.universe if any(s.get("listing_region_code") == "CN" for s in x["securities"])]
        self.cninfo_global(cn)
        for issuer in self.universe:
            codes = {s.get("listing_region_code") for s in issuer["securities"]} & REGIONS
            # One terminal per APAC region represented by the canonical issuer.
            for region in sorted(codes):
                if region == "CN":
                    continue
                if region == "KR": self.dart(issuer)
                elif region == "TW": self.taiwan(issuer)
                elif region == "IN": self.nse(issuer)
                else: self.probe(issuer, region)
        write_jsonl(OUT / "source_frontier.jsonl", sorted(self.frontier, key=lambda x: (x["issuer_id"], x["region_code"])))
        write_jsonl(OUT / "access_audit.jsonl", self.access)
        write_jsonl(OUT / "raw_contexts.jsonl", self.raw_hits)
        print(json.dumps({"issuers": len(self.universe), "frontier": len(self.frontier), "raw_contexts": len(self.raw_hits),
                          "terminals": Counter(x["terminal_status"] for x in self.frontier)}, ensure_ascii=False, default=dict))


if __name__ == "__main__":
    Collector().run()

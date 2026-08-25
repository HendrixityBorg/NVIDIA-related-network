#!/usr/bin/env python3
"""Build frozen page, filing, entity and relationship-candidate artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
RETRIEVED = "2026-08-25T00:00:00+08:00"


def read_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_data(self, data):
        data = " ".join(data.split())
        if data: self.parts.append(data)


# Pages selected after full 379-page contact-sheet inspection. All other pages
# are explicitly processed_no_candidate, not silently skipped.
CANDIDATE_PAGES = {
    "gtc_2025_keynote": {2, 14, 15, 17, 21, 40, 48, 50, 51, *range(53, 64), 69},
    "gtc_taipei_computex_2025": {2, 6, 7, 16, 17, 18, 19, 21, 25, 29, 35, *range(36, 53), 54, *range(59, 68), 71},
    "gtc_paris_2025": {2, 4, 12, 15, *range(17, 21), *range(24, 30), 34, 35, *range(39, 50), *range(52, 62), 65, 68},
    "gtc_dc_2025": {2, 8, 9, 12, 13, 24, 36, *range(39, 52), *range(54, 60), 62, 64},
    "computex_2026_keynote": {4, 5, *range(15, 24), 31, *range(38, 41), 43, *range(45, 49), 54, 56, 63, 65},
    "ndr_july_2026": {5, 15},
}
LOGO_WALLS = {
    ("gtc_2025_keynote", 2), ("gtc_taipei_computex_2025", 2),
    ("gtc_paris_2025", 2), ("gtc_dc_2025", 2), ("computex_2026_keynote", 4),
}
SUPPLIER_PAGES = {("gtc_2025_keynote", 40)}
CUSTOMER_PAGES = {
    ("gtc_taipei_computex_2025", 16), ("gtc_taipei_computex_2025", 17),
    ("gtc_taipei_computex_2025", 18), ("gtc_taipei_computex_2025", 19),
    ("gtc_paris_2025", 17), ("gtc_paris_2025", 18), ("gtc_paris_2025", 19),
    ("gtc_paris_2025", 20), ("gtc_dc_2025", 54), ("gtc_dc_2025", 55),
    ("gtc_dc_2025", 56), ("gtc_dc_2025", 57), ("gtc_dc_2025", 58),
    ("gtc_dc_2025", 62), ("gtc_dc_2025", 64),
}

PRODUCT_RULES = [
    (lambda d,p: (d,p) in LOGO_WALLS, "corporate_general"),
    (lambda d,p: d == "gtc_2025_keynote" and p == 40, "v2-networking-silicon-photonics"),
    (lambda d,p: d == "gtc_dc_2025" and p in {12}, "nvqlink"),
    (lambda d,p: d == "gtc_taipei_computex_2025" and p == 7, "cuda-q"),
    (lambda d,p: d == "gtc_paris_2025" and p == 4, "cuda-q"),
    (lambda d,p: p in {62,64,65} and d in {"gtc_dc_2025","gtc_paris_2025","computex_2026_keynote"}, "drive-hyperion"),
    (lambda d,p: p >= 52 and d in {"gtc_taipei_computex_2025","gtc_paris_2025","gtc_dc_2025","computex_2026_keynote"}, "omniverse"),
    (lambda d,p: p in range(35,53), "nemo"),
    (lambda d,p: True, "nvidia-ai-enterprise"),
]

# Listing identifiers are frozen candidates, not a substitute for reviewer
# verification. Multiple aliases intentionally roll subsidiaries/brands to a
# listed parent. Exchange-formatted tickers preserve venue identity.
REGISTRY = [
    ("Accenture plc", "NYSE", "ACN", ["accenture"]), ("Adobe Inc.", "NASDAQ", "ADBE", ["adobe"]),
    ("Airbnb, Inc.", "NASDAQ", "ABNB", ["airbnb"]), ("Alibaba Group Holding Limited", "NYSE", "BABA", ["alibaba cloud","alibaba"]),
    ("Amazon.com, Inc.", "NASDAQ", "AMZN", ["amazon","aws"]), ("Amgen Inc.", "NASDAQ", "AMGN", ["amgen"]),
    ("Arm Holdings plc", "NASDAQ", "ARM", ["arm"]), ("AT&T Inc.", "NYSE", "T", ["at&t","at&t"]),
    ("Baidu, Inc.", "NASDAQ", "BIDU", ["baidu"]), ("Barclays PLC", "NYSE", "BCS", ["barclays"]),
    ("BlackRock, Inc.", "NYSE", "BLK", ["blackrock"]), ("BMW AG", "XETRA", "BMW", ["bmw"]),
    ("BNP Paribas SA", "EURONEXT_PARIS", "BNP", ["bnp paribas"]), ("Bristol-Myers Squibb Company", "NYSE", "BMY", ["bristol myers"]),
    ("Cadence Design Systems, Inc.", "NASDAQ", "CDNS", ["cadence"]), ("Capital One Financial Corporation", "NYSE", "COF", ["capitalone","capital one"]),
    ("Cerence Inc.", "NASDAQ", "CRNC", ["cerence"]), ("Cisco Systems, Inc.", "NASDAQ", "CSCO", ["cisco"]),
    ("The Coca-Cola Company", "NYSE", "KO", ["coca-cola","coca'cola"]), ("Coherent Corp.", "NYSE", "COHR", ["coherent"]),
    ("CoreWeave, Inc.", "NASDAQ", "CRWV", ["coreweave"]), ("Corning Incorporated", "NYSE", "GLW", ["corning"]),
    ("Corteva, Inc.", "NYSE", "CTVA", ["corteva"]), ("CrowdStrike Holdings, Inc.", "NASDAQ", "CRWD", ["crowdstrike"]),
    ("Dell Technologies Inc.", "NYSE", "DELL", ["dell technologies","delltechnologies"]),
    ("Delta Air Lines, Inc.", "NYSE", "DAL", ["delta air"]), ("Delta Electronics, Inc.", "TWSE", "2308", ["delta electronics"]),
    ("eBay Inc.", "NASDAQ", "EBAY", ["ebay"]), ("Electronic Arts Inc.", "NASDAQ", "EA", ["electronic arts"]),
    ("Elastic N.V.", "NYSE", "ESTC", ["elastic"]), ("Equinix, Inc.", "NASDAQ", "EQIX", ["equinix"]),
    ("Telefonaktiebolaget LM Ericsson", "NASDAQ", "ERIC", ["ericsson"]), ("Fabrinet", "NYSE", "FN", ["fabrinet"]),
    ("Ford Motor Company", "NYSE", "F", ["ford"]), ("Hon Hai Precision Industry Co., Ltd.", "TWSE", "2317", ["foxconn","hon hai"]),
    ("Fujitsu Limited", "TSE", "6702", ["fujitsu"]), ("GE HealthCare Technologies Inc.", "NASDAQ", "GEHC", ["ge healthcare"]),
    ("Giga-Byte Technology Co., Ltd.", "TWSE", "2376", ["gigabyte"]), ("Alphabet Inc.", "NASDAQ", "GOOGL", ["google cloud","google","waymo"]),
    ("GSK plc", "NYSE", "GSK", ["gsk"]), ("Hewlett Packard Enterprise Company", "NYSE", "HPE", ["hewlett packard enterprise","hpe"]),
    ("Hexagon AB", "NASDAQ_STOCKHOLM", "HEXA-B", ["hexagon"]), ("Hitachi, Ltd.", "TSE", "6501", ["hitachi vantara","hitachi"]),
    ("International Business Machines Corporation", "NYSE", "IBM", ["ibm","red hat"]), ("Infosys Limited", "NYSE", "INFY", ["infosys"]),
    ("Intel Corporation", "NASDAQ", "INTC", ["intel"]), ("IonQ, Inc.", "NYSE", "IONQ", ["ionq"]),
    ("JD.com, Inc.", "NASDAQ", "JD", ["jd.com"]), ("Kroger Co.", "NYSE", "KR", ["kroger"]),
    ("Lenovo Group Limited", "HKEX", "0992", ["lenovo"]), ("Lockheed Martin Corporation", "NYSE", "LMT", ["lockheed martin"]),
    ("Lowe's Companies, Inc.", "NYSE", "LOW", ["lowe's"]), ("Lucid Group, Inc.", "NASDAQ", "LCID", ["lucid"]),
    ("Lumentum Holdings Inc.", "NASDAQ", "LITE", ["lumentum"]), ("Mastercard Incorporated", "NYSE", "MA", ["mastercard"]),
    ("Mercedes-Benz Group AG", "XETRA", "MBG", ["mercedes-benz"]), ("Meta Platforms, Inc.", "NASDAQ", "META", ["meta"]),
    ("Micron Technology, Inc.", "NASDAQ", "MU", ["micron"]), ("Microsoft Corporation", "NASDAQ", "MSFT", ["microsoft azure","microsoft","linkedin","github"]),
    ("Nasdaq, Inc.", "NASDAQ", "NDAQ", ["nasdaq"]), ("Intercontinental Exchange, Inc.", "NYSE", "ICE", ["nyse group","new york stock exchange"]),
    ("NAVER Corporation", "KRX", "035420", ["naver cloud","naver"]),
    ("NetApp, Inc.", "NASDAQ", "NTAP", ["netapp"]), ("Nokia Oyj", "NYSE", "NOK", ["nokia"]),
    ("Novartis AG", "NYSE", "NVS", ["novartis"]), ("Nutanix, Inc.", "NASDAQ", "NTNX", ["nutanix"]),
    ("Oracle Corporation", "NYSE", "ORCL", ["oracle cloud","oracle"]), ("Palantir Technologies Inc.", "NASDAQ", "PLTR", ["palantir"]),
    ("Pegatron Corporation", "TWSE", "4938", ["pegatron"]), ("PepsiCo, Inc.", "NASDAQ", "PEP", ["pepsico"]),
    ("Pfizer Inc.", "NYSE", "PFE", ["pfizer"]), ("Pony AI Inc.", "NASDAQ", "PONY", ["pony.ai","pony ai"]),
    ("Pure Storage, Inc.", "NYSE", "PSTG", ["purestorage","pure storage"]), ("Qualcomm Incorporated", "NASDAQ", "QCOM", ["qualcomm"]),
    ("Rigetti Computing, Inc.", "NASDAQ", "RGTI", ["rigetti"]), ("Rivian Automotive, Inc.", "NASDAQ", "RIVN", ["rivian"]),
    ("Roblox Corporation", "NYSE", "RBLX", ["roblox"]), ("Rockwell Automation, Inc.", "NYSE", "ROK", ["rockwell"]),
    ("SAP SE", "NYSE", "SAP", ["sap"]), ("Samsung Electronics Co., Ltd.", "KRX", "005930", ["samsung"]),
    ("Schneider Electric SE", "EURONEXT_PARIS", "SU", ["schneider electric","schneider"]), ("ServiceNow, Inc.", "NYSE", "NOW", ["servicenow"]),
    ("Shell plc", "NYSE", "SHEL", ["shell"]), ("Shopify Inc.", "NASDAQ", "SHOP", ["shopify"]),
    ("Siemens AG", "XETRA", "SIE", ["siemens"]), ("SK hynix Inc.", "KRX", "000660", ["sk hynix"]),
    ("SLB N.V.", "NYSE", "SLB", ["slb"]), ("SoftBank Group Corp.", "TSE", "9984", ["softbank"]),
    ("S&P Global Inc.", "NYSE", "SPGI", ["s&p global"]), ("Stellantis N.V.", "NYSE", "STLA", ["stellantis"]),
    ("Sumitomo Electric Industries, Ltd.", "TSE", "5802", ["sumitomo electric"]), ("Synopsys, Inc.", "NASDAQ", "SNPS", ["synopsys"]),
    ("Taiwan Semiconductor Manufacturing Company Limited", "NYSE", "TSM", ["tsmc","taiwan semiconductor"]),
    ("Tencent Holdings Limited", "HKEX", "0700", ["tencent"]), ("T-Mobile US, Inc.", "NASDAQ", "TMUS", ["t-mobile","t mobile"]),
    ("Toyota Motor Corporation", "NYSE", "TM", ["toyota"]), ("Trend Micro Incorporated", "TSE", "4704", ["trend micro","trend vision"]),
    ("Uber Technologies, Inc.", "NYSE", "UBER", ["uber"]), ("UBS Group AG", "NYSE", "UBS", ["ubs"]),
    ("Unilever PLC", "NYSE", "UL", ["unilever"]), ("U.S. Bancorp", "NYSE", "USB", ["usbank"]),
    ("Verizon Communications Inc.", "NYSE", "VZ", ["verizon"]), ("Visa Inc.", "NYSE", "V", ["visa"]),
    ("Volkswagen AG", "XETRA", "VOW3", ["volkswagen"]), ("Volvo AB", "NASDAQ_STOCKHOLM", "VOLV-B", ["volvo"]),
    ("Walmart Inc.", "NYSE", "WMT", ["walmart"]), ("Wipro Limited", "NYSE", "WIT", ["wipro"]),
    ("Wistron Corporation", "TWSE", "3231", ["wistron"]), ("Wiwynn Corporation", "TWSE", "6669", ["wiwynn"]),
    ("Xiaomi Corporation", "HKEX", "1810", ["xiaomi"]), ("Yum! Brands, Inc.", "NYSE", "YUM", ["yum"]),
]

FILINGS_MANUAL = [
    ("Taiwan Semiconductor Manufacturing Company Limited","supplier","supplies_to","blackwell","fact","foundry producing semiconductor wafers"),
    ("Samsung Electronics Co., Ltd.","supplier","supplies_to","blackwell","fact","foundry and memory supplier"),
    ("SK hynix Inc.","supplier","supplies_to","blackwell","fact","memory supplier"),
    ("Micron Technology, Inc.","supplier","supplies_to","blackwell","fact","memory supplier"),
    ("Hon Hai Precision Industry Co., Ltd.","supplier","supplies_to","corporate_general","fact","assembly, testing and packaging contractor"),
    ("Wistron Corporation","supplier","supplies_to","corporate_general","fact","assembly, testing and packaging contractor"),
    ("Fabrinet","supplier","supplies_to","corporate_general","fact","assembly, testing and packaging contractor"),
]
PEERS = [
    ("Advanced Micro Devices, Inc.","NASDAQ","AMD","GPU/custom chips; SoC; networking"),
    ("Intel Corporation","NASDAQ","INTC","GPU/custom chips; SoC; networking"),
    ("Alibaba Group Holding Limited","NYSE","BABA","internal accelerated/AI computing"),
    ("Alphabet Inc.","NASDAQ","GOOGL","internal accelerated/AI computing"),
    ("Amazon.com, Inc.","NASDAQ","AMZN","internal accelerated/AI computing and Arm CPU"),
    ("Baidu, Inc.","NASDAQ","BIDU","internal accelerated/AI computing"),
    ("Microsoft Corporation","NASDAQ","MSFT","internal accelerated/AI computing and Arm CPU"),
    ("Ambarella, Inc.","NASDAQ","AMBA","SoC"), ("Broadcom Inc.","NASDAQ","AVGO","SoC and networking"),
    ("Qualcomm Incorporated","NASDAQ","QCOM","SoC"), ("Renesas Electronics Corporation","TSE","6723","SoC"),
    ("Samsung Electronics Co., Ltd.","KRX","005930","SoC"), ("Tesla, Inc.","NASDAQ","TSLA","internally designed SoC"),
    ("Arista Networks, Inc.","NYSE","ANET","networking"), ("Cisco Systems, Inc.","NASDAQ","CSCO","networking"),
    ("Hewlett Packard Enterprise Company","NYSE","HPE","networking"), ("Lumentum Holdings Inc.","NASDAQ","LITE","optical networking"),
    ("Marvell Technology, Inc.","NASDAQ","MRVL","networking"),
]


def context_for(deck, page):
    return next(key for test,key in PRODUCT_RULES if test(deck,page))


def main():
    frontier = {x["source_id"]:x for x in read_jsonl(ROOT/"source_frontier.jsonl")}
    by_file = {Path(x["filename"]).stem:x for x in frontier.values() if x["kind"] == "presentation-pdf"}
    ocr = {Path(x["rendered_page"]).with_suffix("").as_posix():x["ocr_lines"] for x in read_jsonl(ROOT/"source_files/page_ocr.jsonl")}
    pages=[]; raw=[]; listed=[]; oid=0; lid=0
    for deck,spec in sorted(by_file.items()):
        reader=PdfReader(ROOT/"source_files"/spec["filename"])
        for page_num,page in enumerate(reader.pages,1):
            key=f"{deck}/page-{page_num:02d}"
            lines=ocr.get(key,[])
            text=" ".join((page.extract_text() or "").split())
            has=page_num in CANDIDATE_PAGES[deck]
            pages.append({"page_id":f"{spec['source_id']}-P{page_num:03d}","source_id":spec["source_id"],"pdf_page":page_num,"terminal_state":"processed_with_candidate" if has else "processed_no_candidate","text_excerpt":text[:280],"ocr_line_count":len(lines),"visual_review":"contact-sheet inspected at 72 dpi; targeted pages enlarged","content_fingerprint":hashlib.sha256((text+"\n"+"\n".join(lines)).encode()).hexdigest()})
            if not has: continue
            product=context_for(deck,page_num)
            if (deck,page_num) in LOGO_WALLS: rel,status,direction="unknown","unknown","undetermined"
            elif (deck,page_num) in SUPPLIER_PAGES: rel,status,direction="supplier","fact","supplies_to"
            elif (deck,page_num) in CUSTOMER_PAGES: rel,status,direction="customer","fact","nvidia_sells_to_or_platform_used_by"
            else: rel,status,direction="partner","fact","collaborates_with"
            # One visual audit record guarantees a raw trace even if Vision OCR
            # cannot resolve a vector logo.
            oid+=1
            raw.append({"observation_id":f"FP-OBS-{oid:05d}","source_id":spec["source_id"],"source_url":spec["url"],"publisher":spec["publisher"],"published_at":spec["published_at"],"retrieved_at":RETRIEVED,"evidence_locator":f"PDF page {page_num}","observed_entity_string":"[page-level visual candidate audit]","observation_method":"visual_contact_sheet_and_enlargement","placement":"logo_wall_or_cover" if (deck,page_num) in LOGO_WALLS else "titled_product_or_architecture_page","product_canonical_key":product,"relationship_hypothesis":rel,"direction":direction,"status":status,"short_evidence":("Logo wall/cover without relationship title; entity relation remains unknown." if status=="unknown" else (text[:240] or "Visual page shows company logo/name in the stated NVIDIA product or collaboration context.")),"entity_resolution_state":"page_audit","access_restrictions":spec["access_restrictions"],"content_fingerprint":pages[-1]["content_fingerprint"]})
            joined=" | ".join(lines)
            # Preserve every OCR token/line on a visually selected candidate
            # page. This append-only layer intentionally includes non-company
            # labels and OCR errors; later entity resolution may reject them,
            # but collection never silently drops a logo/name candidate.
            for raw_line in lines:
                oid+=1
                raw.append({"observation_id":f"FP-OBS-{oid:05d}","source_id":spec["source_id"],"source_url":spec["url"],"publisher":spec["publisher"],"published_at":spec["published_at"],"retrieved_at":RETRIEVED,"evidence_locator":f"PDF page {page_num}","observed_entity_string":raw_line,"observation_method":"Vision OCR raw line retained without deletion","placement":"logo_wall_or_cover" if (deck,page_num) in LOGO_WALLS else "titled_product_or_architecture_page","product_canonical_key":product,"relationship_hypothesis":rel,"direction":direction,"status":status,"short_evidence":raw_line[:240],"entity_resolution_state":"unresolved_raw_ocr_may_be_nonentity_or_error","access_restrictions":spec["access_restrictions"],"content_fingerprint":pages[-1]["content_fingerprint"]})
            for entity,exchange,ticker,aliases in REGISTRY:
                hit=next((a for a in aliases if re.search(r"(?<![A-Za-z0-9])"+re.escape(a)+r"(?![A-Za-z0-9])",joined,re.I)),None)
                if not hit: continue
                oid+=1; obs=f"FP-OBS-{oid:05d}"
                raw.append({"observation_id":obs,"source_id":spec["source_id"],"source_url":spec["url"],"publisher":spec["publisher"],"published_at":spec["published_at"],"retrieved_at":RETRIEVED,"evidence_locator":f"PDF page {page_num}","observed_entity_string":hit,"observation_method":"Vision OCR followed by visual review","placement":"logo_wall_or_cover" if (deck,page_num) in LOGO_WALLS else "titled_product_or_architecture_page","product_canonical_key":product,"relationship_hypothesis":rel,"direction":direction,"status":status,"short_evidence":("Logo appears on untitled event/ecosystem wall; NVIDIA product connection is not explicit." if status=="unknown" else f"{entity} name/logo appears in the NVIDIA {product} context on the cited page."),"entity_resolution_state":"resolved_listed_candidate_manual_review","access_restrictions":spec["access_restrictions"],"content_fingerprint":pages[-1]["content_fingerprint"]})
                lid+=1; listed.append({"candidate_id":f"FP-LC-{lid:05d}","observation_id":obs,"entity_name":entity,"exchange":exchange,"ticker":ticker,"security_identifier_status":"candidate_manual_review","current_listing_status":"appears_listed_at_cutoff_manual_review","relationship_type":rel,"direction":direction,"semantic_status":status,"product_canonical_key":product,"source_id":spec["source_id"],"evidence_locator":f"PDF page {page_num}"})

    # 10-K exact named supplier and peer evidence; anonymous concentration stays unknown.
    tenk=frontier["FP-S001"]; parser=TextParser(); parser.feed((ROOT/"source_files"/tenk["filename"]).read_text(errors="ignore")); txt=" ".join(parser.parts)
    supplier_quote="We utilize foundries, such as Taiwan Semiconductor Manufacturing Company Limited, or TSMC, and Samsung Electronics Co., Ltd., or Samsung, to produce our semiconductor wafers. We purchase memory from SK Hynix Inc., Micron Technology, Inc., and Samsung."
    for entity,rel,direction,product,status,detail in FILINGS_MANUAL:
        oid+=1; obs=f"FP-OBS-{oid:05d}"; raw.append({"observation_id":obs,"source_id":"FP-S001","source_url":tenk["url"],"publisher":tenk["publisher"],"published_at":tenk["published_at"],"retrieved_at":RETRIEVED,"evidence_locator":"Item 1, Business - Manufacturing; SEC inline HTML","observed_entity_string":entity,"observation_method":"10-K named-entity extraction and human verification","placement":"explicit narrative","product_canonical_key":product,"relationship_hypothesis":rel,"direction":direction,"status":status,"short_evidence":detail,"entity_resolution_state":"resolved_listed_candidate_manual_review","access_restrictions":tenk["access_restrictions"],"content_fingerprint":tenk["sha256"]})
        match=next((r for r in REGISTRY if r[0]==entity),None)
        if match:
            lid+=1; listed.append({"candidate_id":f"FP-LC-{lid:05d}","observation_id":obs,"entity_name":entity,"exchange":match[1],"ticker":match[2],"security_identifier_status":"candidate_manual_review","current_listing_status":"appears_listed_at_cutoff_manual_review","relationship_type":rel,"direction":direction,"semantic_status":status,"product_canonical_key":product,"source_id":"FP-S001","evidence_locator":"Item 1, Business - Manufacturing"})
    for entity,exchange,ticker,scope in PEERS:
        oid+=1; obs=f"FP-OBS-{oid:05d}"; raw.append({"observation_id":obs,"source_id":"FP-S001","source_url":tenk["url"],"publisher":tenk["publisher"],"published_at":tenk["published_at"],"retrieved_at":RETRIEVED,"evidence_locator":"Item 1, Business - Competition","observed_entity_string":entity,"observation_method":"10-K explicit competitor extraction","placement":"explicit competitor list","product_canonical_key":"corporate_general","relationship_hypothesis":"peer","direction":"competes_with","status":"fact","short_evidence":scope,"entity_resolution_state":"resolved_listed_candidate_manual_review","access_restrictions":tenk["access_restrictions"],"content_fingerprint":tenk["sha256"]}); lid+=1
        listed.append({"candidate_id":f"FP-LC-{lid:05d}","observation_id":obs,"entity_name":entity,"exchange":exchange,"ticker":ticker,"security_identifier_status":"candidate_manual_review","current_listing_status":"appears_listed_at_cutoff_manual_review","relationship_type":"peer","direction":"competes_with","semantic_status":"fact","product_canonical_key":"corporate_general","source_id":"FP-S001","evidence_locator":"Item 1, Business - Competition"})
    for label,evidence in [("unnamed_direct_customer_1","22% of FY2026 revenue"),("unnamed_direct_customer_2","14% of FY2026 revenue"),("unnamed_ai_research_and_deployment_company","meaningful amount of FY2026 revenue via cloud services purchased from NVIDIA customers")]:
        oid+=1; raw.append({"observation_id":f"FP-OBS-{oid:05d}","source_id":"FP-S001","source_url":tenk["url"],"publisher":tenk["publisher"],"published_at":tenk["published_at"],"retrieved_at":RETRIEVED,"evidence_locator":"Notes to Consolidated Financial Statements - Revenue concentration","observed_entity_string":label,"observation_method":"10-K quantitative extraction","placement":"explicit but unnamed disclosure","product_canonical_key":"corporate_general","relationship_hypothesis":"customer","direction":"nvidia_sells_to_or_indirectly_serves","status":"unknown","short_evidence":evidence,"entity_resolution_state":"unresolved_by_design_do_not_guess","access_restrictions":tenk["access_restrictions"],"content_fingerprint":tenk["sha256"]})

    # 13F: full information table, including the private issuer that is excluded
    # from the current listed-company graph.
    ns={"i":"http://www.sec.gov/edgar/document/thirteenf/informationtable"}
    root=ET.parse(ROOT/"source_files/13f_2026q2_information_table.xml").getroot()
    info=[]
    listing={
      "COHERENT CORP":("Coherent Corp.","NYSE","COHR","listed"), "COREWEAVE INC":("CoreWeave, Inc.","NASDAQ","CRWV","listed"),
      "GENERATE BIOMEDICINES INC":("Generate Biomedicines, Inc.","NASDAQ","GENB","listed"), "INTEL CORP":("Intel Corporation","NASDAQ","INTC","listed"),
      "NEBIUS GROUP N.V.":("Nebius Group N.V.","NASDAQ","NBIS","listed"), "NOKIA CORP":("Nokia Oyj","NYSE","NOK","listed_adr"),
      "SPACE EXPLORATION TECHN CORP":("Space Exploration Technologies Corp.",None,None,"private_excluded_from_listed_graph"),
      "SYNOPSYS INC":("Synopsys, Inc.","NASDAQ","SNPS","listed"),
    }
    for idx,node in enumerate(root.findall("i:infoTable",ns),1):
        issuer=node.findtext("i:nameOfIssuer",namespaces=ns); resolved,ex,ticker,state=listing[issuer]
        title=node.findtext("i:titleOfClass",namespaces=ns)
        put_call=node.findtext("i:putCall",default=None,namespaces=ns)
        row={"row_number":idx,"period_of_report":"2026-06-30","filing_date":"2026-08-14","accession":"0001045810-26-000065","is_amendment":False,"issuer_raw":issuer,"issuer_entity":{"name":resolved,"exchange":ex,"ticker":ticker,"listing_status":state},"security":{"title_of_class":title,"cusip":node.findtext("i:cusip",namespaces=ns),"put_call":put_call,"share_or_principal_amount":int(node.find("i:shrsOrPrnAmt/i:sshPrnamt",ns).text),"share_or_principal_type":node.find("i:shrsOrPrnAmt/i:sshPrnamtType",ns).text},"entity_name":resolved,"title_of_class":title,"cusip":node.findtext("i:cusip",namespaces=ns),"put_call":put_call,"value_usd":int(node.findtext("i:value",namespaces=ns)),"value_unit":"USD (filed XML integer dollars; not thousands)","shares":int(node.find("i:shrsOrPrnAmt/i:sshPrnamt",ns).text),"share_type":node.find("i:shrsOrPrnAmt/i:sshPrnamtType",ns).text,"investment_discretion":node.findtext("i:investmentDiscretion",namespaces=ns),"exchange":ex,"ticker":ticker,"listing_status":state,"relationship_type":"investor_or_investee","direction":"NVIDIA_invests_in","semantic_status":"fact","source_id":"FP-S003","evidence_locator":f"information table row {idx}","security_identifier_status":"CUSIP confirmed by filing; exchange/ticker manual review"}
        info.append(row); oid+=1; obs=f"FP-OBS-{oid:05d}"; raw.append({"observation_id":obs,"source_id":"FP-S003","source_url":frontier["FP-S003"]["url"],"publisher":frontier["FP-S003"]["publisher"],"published_at":"2026-08-14","retrieved_at":RETRIEVED,"evidence_locator":f"information table row {idx}","observed_entity_string":issuer,"observation_method":"complete XML table parse","placement":"13F holding row","product_canonical_key":"corporate_general","relationship_hypothesis":"investor_or_investee","direction":"NVIDIA_invests_in","status":"fact","short_evidence":f"{row['shares']} shares; reported value ${row['value_usd']:,}; CUSIP {row['cusip']}","entity_resolution_state":state,"access_restrictions":frontier["FP-S003"]["access_restrictions"],"content_fingerprint":frontier["FP-S003"]["sha256"]})
        if state.startswith("listed"):
            lid+=1; listed.append({"candidate_id":f"FP-LC-{lid:05d}","observation_id":obs,"entity_name":resolved,"exchange":ex,"ticker":ticker,"cusip":row["cusip"],"security_identifier_status":"CUSIP confirmed; exchange/ticker manual review","current_listing_status":"appears_listed_at_cutoff_manual_review","relationship_type":"investor_or_investee","direction":"NVIDIA_invests_in","semantic_status":"fact","product_canonical_key":"corporate_general","source_id":"FP-S003","evidence_locator":f"information table row {idx}"})

    acquisitions=[
      {"target":"Mellanox Technologies, Ltd.","former_security":"NASDAQ: MLNX","completion_date":"2020-04-27","transaction_value_usd":7000000000,"status_at_cutoff":"completed_and_delisted; NVIDIA subsidiary/brand, exclude from current listed graph","source_url":"https://nvidianews.nvidia.com/news/nvidia-completes-acquisition-of-mellanox-creating-major-force-driving-next-gen-data-centers","publisher":"NVIDIA Newsroom","evidence_locator":"headline and first paragraph"},
      {"target":"PortalPlayer, Inc.","former_security":"NASDAQ: PLAY","completion_date":"2007-01","status_at_cutoff":"completed_and_delisted; exclude from current listed graph","source_url":"https://www.nvidia.com/content/transformations/issue1.pdf","publisher":"NVIDIA","evidence_locator":"On the Go with NVIDIA - acquisition paragraph","manual_review_note":"former ticker sourced from historical public-company record; verify before merge"},
      {"target":"MediaQ, Inc.","former_security":"historically public; ticker requires manual verification","completion_date":"2003-08-19","status_at_cutoff":"completed_and_delisted; exclude from current listed graph","source_url":"https://www.nvidia.com/en-us/about-nvidia/corporate-timeline/","publisher":"NVIDIA","evidence_locator":"2003 - NVIDIA acquires MediaQ","manual_review_note":"do not merge a security identifier until verified"},
      {"target":"ULi Electronics, Inc.","former_security":"former Taiwan company; listing identifier unresolved","completion_date":"2006-02-21","status_at_cutoff":"completed; no current separate listing, exclude from current listed graph","source_url":"https://www.sec.gov/Archives/edgar/data/1045810/000104581006000007/ulipressrelease.htm","publisher":"NVIDIA / SEC","evidence_locator":"completion press release","manual_review_note":"historical listing status needs market-record verification"},
      {"target":"3dfx Interactive, Inc. assets","former_security":"former NASDAQ: TDFX","completion_date":"2001-04","status_at_cutoff":"asset purchase from a former listed company, not a company acquisition; exclude from current listed graph and completed-company-acquisition count","source_url":"https://www.nvidia.com/en-us/about-nvidia/corporate-timeline/","publisher":"NVIDIA","evidence_locator":"2000/2001 timeline entries for agreement and completion","manual_review_note":"classification boundary: NVIDIA acquired substantially all assets, not the issuer"},
      {"target":"Arm Limited", "former_security":"not acquired", "completion_date":None,"status_at_cutoff":"proposed transaction terminated in 2022; not an investee-by-acquisition","source_url":"https://nvidianews.nvidia.com/news/softbank-group-and-nvidia-agree-to-terminate-nvidia-s-acquisition-of-arm-limited","publisher":"NVIDIA Newsroom","evidence_locator":"termination announcement","exclusion_reason":"not completed"},
    ]

    write_jsonl(ROOT/"page_processing.jsonl",pages); write_jsonl(ROOT/"raw_observations.jsonl",raw); write_jsonl(ROOT/"listed_candidates.jsonl",listed); write_jsonl(ROOT/"13f_holdings.jsonl",info); write_jsonl(ROOT/"acquisition_review.jsonl",acquisitions)
    conflicts=[
      {"conflict_id":"FP-C001","topic":"13F value units","resolution":"Use filed XML values as U.S. dollars; the 8-row total is $63,439,974,569. Do not multiply by 1,000.","status":"resolved"},
      {"conflict_id":"FP-C002","topic":"13F private security","entity":"Space Exploration Technologies Corp.","resolution":"Retain raw holding but exclude from current listed-company graph.","status":"resolved"},
      {"conflict_id":"FP-C003","topic":"logo-only evidence","resolution":"Untitled logo walls/covers are unknown; titled product/collaboration pages are fact placement, not automatic proof of supplier/customer role.","status":"resolved"},
      {"conflict_id":"FP-C004","topic":"anonymous major customers","resolution":"Preserve 22%, 14% and unnamed indirect-company observations as unknown; do not guess identity.","status":"resolved"},
      {"conflict_id":"FP-C005","topic":"13F amendment","resolution":"Primary filing is isAmendment=false; no 13F-HR/A filed through cutoff in SEC recent filing index.","status":"resolved"},
      {"conflict_id":"FP-C006","topic":"3dfx transaction classification","resolution":"NVIDIA acquired substantially all 3dfx assets, not the listed issuer; retain as acquisition-review boundary and do not place it in the current listed-company graph.","status":"resolved"},
    ]; write_jsonl(ROOT/"conflicts.jsonl",conflicts)
    print(json.dumps({"pages":len(pages),"raw_observations":len(raw),"listed_candidates":len(listed),"13f_rows":len(info)},indent=2))


if __name__ == "__main__": main()

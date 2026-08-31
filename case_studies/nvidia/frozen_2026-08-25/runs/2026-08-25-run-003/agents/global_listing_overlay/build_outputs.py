#!/usr/bin/env python3
"""Build the reviewed global listing overlay from hand-verified official sources."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
CANDIDATES = RUN / "agents/entity_resolution_complete/candidate_review.jsonl"
CUTOFF = "2026-08-25"
RETRIEVED = "2026-08-25T16:00:00+08:00"
ACCESS = "public_no_login; no paywall, CAPTCHA, robots, rate-limit, or access-control bypass used"
REUSE = "Facts and short locators/excerpts only; publisher copyright retained; source page is not redistributed."


def eid(value: str) -> str:
    return "gle_" + hashlib.sha256(value.encode()).hexdigest()[:16]


def aid(value: str) -> str:
    return "gla_" + hashlib.sha256(value.encode()).hexdigest()[:16]


def did(value: str) -> str:
    return "gld_" + hashlib.sha256(value.encode()).hexdigest()[:16]


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def sec(exchange: str, ticker: str, *, isin: str | None = None,
        security_class: str = "ordinary_common", primary: bool = True,
        status: str = "active_at_cutoff", mic: str | None = None,
        vendor_codes: list[str] | None = None) -> dict:
    row = {
        "exchange": exchange,
        "ticker": ticker,
        "security_class": security_class,
        "primary": primary,
        "status_at_cutoff": status,
    }
    if isin:
        row["isin"] = isin
    if mic:
        row["mic"] = mic
    if vendor_codes:
        row["vendor_codes"] = vendor_codes
    return row


def entity(entity_id: str, legal_name: str, display_name: str, jurisdiction: str,
           securities: list[dict], evidence_keys: list[str], aliases: list[str],
           *, listing_status: str = "listed_confirmed",
           merge_action: str = "insert", merge_target_entity_id: str | None = None,
           temporal_notes: list[str] | None = None,
           conflict_notes: list[str] | None = None,
           successor_entity_id: str | None = None) -> dict:
    row = {
        "entity_id": entity_id,
        "legal_name": legal_name,
        "display_name": display_name,
        "jurisdiction": jurisdiction,
        "listing_status": listing_status,
        "status_as_of": CUTOFF,
        "merge_action": merge_action,
        "securities": securities,
        "aliases": aliases,
        "listing_evidence_ids": [eid(k) for k in evidence_keys],
        "temporal_notes": temporal_notes or [],
        "conflict_notes": conflict_notes or [],
    }
    if merge_target_entity_id:
        row["merge_target_entity_id"] = merge_target_entity_id
    if successor_entity_id:
        row["successor_entity_id"] = successor_entity_id
    return row


EVIDENCE_RAW = {
    "lenovo_listing": ("lenovo_group", "issuer_listing", "https://investor.lenovo.com/en/ir/stockinfo.php", "Lenovo Group Limited", None, "Stock Information > Listing Shares", "Ordinary shares: Hong Kong Stock Exchange; codes 992/80992; ISIN HK0992009065."),
    "siemens_listing": ("siemens_ag", "issuer_listing", "https://www.siemens.com/de-de/company/investor-relations/share-bonds-rating/basic-data-key-share-figures/", "Siemens AG", None, "Basisdaten der Siemens Aktie > Wertpapierkennnummern & Kürzel", "Frankfurt/Xetra listing; ISIN DE0007236101; Reuters symbol SIEGn.DE."),
    "asustek_listing": ("asustek", "issuer_listing_and_brand_identity", "https://www.asus.com/EVENT/Investor/about_profile", "ASUSTeK Computer Inc.", None, "Company Profile table: Company Name / Stock Name / Stock Code / Market Type", "ASUSTEK COMPUTER INC.; stock name ASUSTEK; code 2357; TWSE-listed."),
    "honhai_listing": ("hon_hai", "issuer_listing_and_brand_identity", "https://www.honhai.com/en-us/press-center/press-releases/latest-news/2062", "Hon Hai Technology Group", "2026-06-12", "Opening paragraph and About Hon Hai footer", "Hon Hai Technology Group (Foxconn) (TWSE:2317)."),
    "mercedes_listing": ("mercedes_benz_group", "issuer_listing_and_group_identity", "https://group.mercedes-benz.com/investors/share/", "Mercedes-Benz Group AG", None, "Number of shares, ticker symbol, ISIN table", "Mercedes-Benz Group AG; ticker MBG; ISIN DE0007100000; Xetra price basis."),
    "pegatron_listing": ("pegatron", "issuer_listing", "https://official2.pegatroncorp.com/investorRelation/view/id/16/lang/zh_CN", "Pegatron Corporation", None, "Stock Quotes heading", "TWSE 4938 and Luxembourg Stock Exchange GDR PGRGS."),
    "gigabyte_listing": ("gigabyte_technology", "issuer_listing", "https://www.gigabyte.com/kr/press/news/2380", "GIGA-BYTE Technology Co., Ltd.", "2026-04-16", "Opening paragraph", "GIGABYTE Technology (TWSE:2376)."),
    "wistron_listing": ("wistron", "issuer_listing", "https://www.wistron.com/Investors/ShareholdersServices/StockQuotes", "Wistron Corporation", None, "Shareholders' Service > Stock Quotes", "Wistron shares are listed on TWSE under code 3231."),
    "inventec_listing": ("inventec", "issuer_listing", "https://www.inventec.com/en/investor.htm", "Inventec Corporation", None, "Investor Relations masthead", "Inventec Corporation; Stock Symbol TPE 2356."),
    "naver_listing": ("naver", "issuer_listing", "https://www.navercorp.com/en/investment/stock", "NAVER Corporation", None, "Financial Information > NAVER 035420", "NAVER 035420; KOSPI; listed date 2008-11-28."),
    "wiwynn_listing": ("wiwynn", "issuer_listing", "https://www.wiwynn.com/investors/shareholders-services", "Wiwynn Corporation", None, "FAQ: When did Wiwynn become a listed company?", "Listed on TWSE on 2019-03-27 under code 6669."),
    "schneider_listing": ("schneider_electric", "issuer_listing", "https://www.se.com/ww/en/about-us/investor-relations/share-information/share-price.jsp?businessId=6", "Schneider Electric SE", None, "Share information table", "Euronext Paris; ISIN FR0000121972; ticker SU.PA."),
    "samsung_listing": ("samsung_electronics", "issuer_listing", "https://www.samsung.com/global/ir/stock-information/listing-Info/", "Samsung Electronics Co., Ltd.", None, "Original Shares & GDRs > Ticker Symbols table", "KRX common 005930 and preferred 005935; LSE GDRs SMSN/SMSEL."),
    "samsung_current_disclosure": ("samsung_electronics", "issuer_security_code_crosscheck", "https://www.samsung.com/global/ir/reports-disclosures/public-disclosure-view.84695/", "Samsung Electronics Co., Ltd.", "2026-07-07", "2Q 2026 Pre-Earnings Guidance opening line", "Issuer identifies its securities as KS005930, KS005935, SMSN and SMSD."),
    "fujitsu_listing": ("fujitsu", "issuer_listing", "https://pr.fujitsu.com/jp/ir/faq/index.html", "Fujitsu Limited", None, "FAQ questions 2-4", "Security code 6702; listed on Tokyo Stock Exchange; no overseas listing."),
    "volvo_cars_listing": ("volvo_cars", "exchange_listing", "https://www.nasdaq.com/european-market-activity/shares/volcar-b?id=TX4016914", "Nasdaq Stockholm", None, "Instrument header and 2026 company news", "Volvo Car B remains traded as VOLCAR B on Nasdaq Stockholm at the cutoff."),
    "volvo_cars_isin": ("volvo_cars", "exchange_security_identity", "https://www.nasdaq.com/press-release/listing-of-volvo-car-ab-on-nasdaq-stockholm-211-21-2021-10-28", "Nasdaq Stockholm", "2021-10-28", "Listing notice table", "Volvo Car AB B shares; short name VOLCAR B; ISIN SE0016844831; MIC XSTO."),
    "bmw_listing": ("bmw", "issuer_listing_and_temporal_status", "https://www.bmwgroup.com/content/grpw/websites/bmwgroup_com/de/investor-relations/aktie.html", "BMW AG", None, "Aktiendetails and BMW Vorzugsaktie notice", "Ordinary ISIN DE0005190003, Frankfurt/Munich; preferred trading ceased 2026-06-30 after conversion."),
    "advantech_listing": ("advantech", "issuer_listing", "https://www.advantech.com/emt/investor/dividends", "Advantech Co., Ltd.", None, "Dividend History page stock link", "Taiwan Stock Exchange stock ticker 2395."),
    "msi_listing": ("micro_star", "issuer_listing_and_brand_identity", "https://ca.msi.com/about/investor", "Micro-Star International Co., Ltd.", None, "Investor Information > Stock Information", "MSI investor page gives stock code 2377; legal name is retained from issuer shareholder materials."),
    "asrock_listing": ("asrock", "issuer_listing", "https://asrock.com/general/investor.tw.asp?cat=Information", "ASRock Incorporation", None, "Company information table", "TWSE; stock code 3515; listed 2007-11-08."),
    "aic_listing": ("aic_taiwan", "issuer_listing", "https://www.aicipc.com/about/", "AIC Inc.", None, "Company History > 2012-2016", "AIC states it became public on the Taipei Exchange in 2013."),
    "aic_code": ("aic_taiwan", "issuer_security_code", "https://www.aicipc.com/tw/resources-detail/360/", "AIC Inc.", "2026-06-01", "Opening paragraph", "AIC / 營邦企業 identifies itself with code 3693 in an NVIDIA-specific official release."),
    "mitac_listing": ("mitac_holdings", "issuer_listing", "https://www.mitac.com/en-global/investors_overview/index", "MiTAC Holdings Corporation", None, "Investor overview live quote", "TWSE: MHC 3706; page includes 2026 financial news and an Aug. 20, 2026 quote."),
    "geely_listing": ("geely_auto", "issuer_listing_and_disambiguation", "https://www.geelyauto.com.hk/company-brief/", "Geely Automobile Holdings Limited", None, "Company Brief opening paragraph", "Listed on HKEX Main Board, codes 0175/80175; controlling shareholder Zhejiang Geely Holding Group is private."),
    "nissan_listing": ("nissan", "issuer_listing", "https://www.nissan-global.com/EN/IR/STOCK/INFORMATION/", "Nissan Motor Co., Ltd.", None, "Stock Summary table", "Securities code 7201; Tokyo Stock Exchange."),
    "denso_listing": ("denso", "issuer_listing", "https://www.denso.com/global/home/about-us/investors/faq/", "DENSO Corporation", None, "Stock Related and Historical FAQ", "Security code 6902; listed on Tokyo and Nagoya stock exchanges."),
    "dassault_listing": ("dassault_systemes", "issuer_listing", "https://investor.3ds.com/news-releases/news-release-details/dassault-systemes-declaration-number-outstanding-shares-and-84/", "Dassault Systèmes SE", "2026-05-11", "Opening paragraph", "Euronext Paris: FR0014003TT8, DSY.PA."),
    "hexagon_listing": ("hexagon", "issuer_listing_and_temporal_status", "https://investors.hexagon.com/en/share-information", "Hexagon AB", None, "Share Overview > Symbols and codes", "Nasdaq Stockholm HEXA B; ISIN SE0015961909."),
    "hexagon_octave": ("hexagon", "corporate_action_temporal_status", "https://investors.hexagon.com/share-information/octave-separation", "Hexagon AB", "2026-05-28", "Separation of Octave and FAQ items 2 and 5", "Octave became a separate public company on 2026-05-28 and Hexagon has no continuing ownership interest."),
    "kion_listing": ("kion", "issuer_listing", "https://origin.kiongroup.com/en/Investor-Relations/Share/", "KION GROUP AG", None, "Share Information table", "Frankfurt Prime Standard; abbreviation KGX; ISIN DE000KGX8881."),
    "computacenter_listing": ("computacenter", "issuer_listing", "https://investors.computacenter.com/shareholder-centre/faqs", "Computacenter plc", None, "FAQ: exchange and stock symbol", "London Stock Exchange; ordinary share symbol CCC."),
    "bnp_listing": ("bnp_paribas", "issuer_listing", "https://invest.bnpparibas/en/bnp-paribas-share", "BNP Paribas SA", None, "Stock Information table and listing FAQ", "Euronext Paris; ISIN FR0000131104; ticker BNP."),
    "hitachi_listing_parent": ("entity_43cff1458d4aab47", "issuer_listing_and_subsidiary_identity", "https://www.hitachi.com/en/press/articles/2026/03/0318a/", "Hitachi, Ltd.", "2026-03-16", "Opening paragraph and About Hitachi Vantara", "Hitachi Vantara is the data infrastructure subsidiary of Hitachi, Ltd. (TSE:6501) and is described as wholly owned."),
    "ansys_acquisition": ("ansys_historical", "acquisition_completion", "https://investor.synopsys.com/news/news-details/2025/Synopsys-Completes-Acquisition-of-Ansys/default.aspx", "Synopsys, Inc.", "2025-07-17", "News Highlights and opening paragraph", "Synopsys completed its acquisition of Ansys on 2025-07-17."),
    "ansys_delisting": ("ansys_historical", "exchange_delisting", "https://www.sec.gov/Archives/edgar/data/1013462/0001354457-25-000689-index.htm", "U.S. Securities and Exchange Commission / Nasdaq Stock Market LLC", "2025-07-17", "Form 25-NSE filing detail", "Nasdaq filed Form 25-NSE to remove ANSYS common stock from listing and registration, effective 2025-07-17."),
    "giga_parent": ("gigabyte_technology", "subsidiary_parent_identity", "https://www.gigabyte.com/us/press/news/2393", "GIGA-BYTE Technology Co., Ltd.", "2026-06-01", "Opening paragraph", "Giga Computing is identified as a subsidiary of GIGABYTE."),
    "naver_cloud_parent": ("naver", "subsidiary_parent_identity", "https://www.navercorp.com/api/article/download/67e5e29b-daa6-4df6-98ea-b8ead74f0afa", "NAVER Corporation", "2024-03-18", "Consolidated subsidiaries table", "NAVER Cloud Corporation is a 100%-owned consolidated subsidiary of NAVER Corporation."),
    "asrock_rack_parent": ("asrock", "controlled_subsidiary_identity", "https://www.asrock.com/general/Investor/Merger%282025Q4%29.pdf", "ASRock Incorporation", "2026-03-31", "Notes to consolidated financial statements: subsidiaries table", "ASRock Rack Incorporation is included as a subsidiary; ownership was 46.22% at 2025-12-31, down from 53.03%."),
    "mitac_computing_parent": ("mitac_holdings", "subsidiary_parent_identity", "https://www.mitaccomputing.com/news/29", "MiTAC Computing Technology Corporation", "2025-12-23", "Opening paragraph", "MiTAC Computing Technology Corporation is identified as a subsidiary of MiTAC Holdings Corporation (3706)."),
    "google_cloud_parent": ("alphabet", "operating_segment_parent_identity", "https://abc.xyz/assets/e1/57/8a65483e43feaa709f6cc5cc0737/annualreport2024-web.pdf", "Alphabet Inc.", "2025-04-25", "Annual Report 2024, Note 15, segment table", "Alphabet reports Google Cloud as one of its operating segments."),
    "azure_parent": ("microsoft", "product_parent_identity", "https://www.microsoft.com/investor/reports/ar25/index.html", "Microsoft Corporation", "2025-07-30", "2025 Annual Report, shareholder letter and segment discussion", "Microsoft reports Azure as a Microsoft cloud platform and discloses Azure revenue growth."),
    "github_parent": ("microsoft", "acquired_subsidiary_identity", "https://news.microsoft.com/facts-about-microsoft/", "Microsoft Corporation", None, "Company timeline entry for 2018-10-26", "Microsoft completes GitHub acquisition."),
    "redhat_parent": ("entity_7f4992b527dcdcb3", "acquired_subsidiary_identity", "https://www.ibm.com/investor/news/ibm-completes-acquisition-of-red-hat", "International Business Machines Corporation", "2019-07-09", "Opening and Financial Implications", "IBM completed its acquisition of all issued and outstanding Red Hat common shares."),
}


EVIDENCE = []
for key, (entity_id, evidence_type, url, publisher, published, locator, excerpt) in EVIDENCE_RAW.items():
    EVIDENCE.append({
        "listing_evidence_id": eid(key),
        "entity_id": entity_id,
        "evidence_type": evidence_type,
        "source_url": url,
        "publisher": publisher,
        "published_at": published,
        "retrieved_at": RETRIEVED,
        "evidence_locator": locator,
        "evidence_excerpt": excerpt,
        "access_constraints": ACCESS,
        "license_or_reuse_notes": REUSE,
        "supports_status_as_of": CUTOFF,
        "verification_method": "human_review_of_official_public_source",
    })


ENTITIES = [
    entity("lenovo_group", "Lenovo Group Limited", "Lenovo", "Hong Kong", [sec("Hong Kong Stock Exchange", "0992", isin="HK0992009065", mic="XHKG"), sec("Hong Kong Stock Exchange RMB Counter", "80992", isin="HK0992009065", primary=False)], ["lenovo_listing"], ["Lenovo", "Lenovo Group Limited"]),
    entity("siemens_ag", "Siemens Aktiengesellschaft", "Siemens", "Germany", [sec("Xetra / Frankfurt", "SIE", isin="DE0007236101", mic="XETR")], ["siemens_listing"], ["Siemens", "Siemens AG"], conflict_notes=["Do not merge Siemens AG with separately listed Siemens Energy AG."]),
    entity("asustek", "ASUSTeK Computer Inc.", "ASUS", "Taiwan", [sec("Taiwan Stock Exchange", "2357", mic="XTAI")], ["asustek_listing"], ["ASUS", "ASUSTeK", "ASUSTeK Computer Inc."]),
    entity("hon_hai", "Hon Hai Precision Industry Co., Ltd.", "Foxconn / Hon Hai", "Taiwan", [sec("Taiwan Stock Exchange", "2317", mic="XTAI")], ["honhai_listing"], ["Foxconn", "Hon Hai", "Hon Hai Technology Group", "Hon Hai Precision Industry Co., Ltd."]),
    entity("mercedes_benz_group", "Mercedes-Benz Group AG", "Mercedes-Benz", "Germany", [sec("Xetra / Frankfurt", "MBG", isin="DE0007100000", mic="XETR")], ["mercedes_listing"], ["Mercedes-Benz", "Mercedes-Benz Group", "Mercedes-Benz Group AG"], conflict_notes=["Mercedes-Benz AG is an operating subsidiary; the overlay links the brand/group reference to the listed parent Mercedes-Benz Group AG."]),
    entity("pegatron", "Pegatron Corporation", "Pegatron", "Taiwan", [sec("Taiwan Stock Exchange", "4938", mic="XTAI"), sec("Luxembourg Stock Exchange", "PGRGS", security_class="GDR", primary=False)], ["pegatron_listing"], ["Pegatron", "Pegatron Corporation"]),
    entity("gigabyte_technology", "GIGA-BYTE Technology Co., Ltd.", "GIGABYTE", "Taiwan", [sec("Taiwan Stock Exchange", "2376", mic="XTAI")], ["gigabyte_listing", "giga_parent"], ["GIGABYTE", "GIGA-BYTE Technology", "GIGA-BYTE Technology Co., Ltd.", "Giga Computing"]),
    entity("wistron", "Wistron Corporation", "Wistron", "Taiwan", [sec("Taiwan Stock Exchange", "3231", mic="XTAI")], ["wistron_listing"], ["Wistron", "Wistron Corporation"]),
    entity("inventec", "Inventec Corporation", "Inventec", "Taiwan", [sec("Taiwan Stock Exchange", "2356", mic="XTAI")], ["inventec_listing"], ["Inventec", "Inventec Corporation"]),
    entity("naver", "NAVER Corporation", "NAVER", "South Korea", [sec("Korea Exchange / KOSPI", "035420", mic="XKRX")], ["naver_listing", "naver_cloud_parent"], ["NAVER", "NAVER Corporation", "NAVER Cloud"]),
    entity("wiwynn", "Wiwynn Corporation", "Wiwynn", "Taiwan", [sec("Taiwan Stock Exchange", "6669", mic="XTAI")], ["wiwynn_listing"], ["Wiwynn", "Wiwynn Corporation"]),
    entity("schneider_electric", "Schneider Electric SE", "Schneider Electric", "France", [sec("Euronext Paris", "SU", isin="FR0000121972", mic="XPAR", vendor_codes=["SU.PA"])], ["schneider_listing"], ["Schneider Electric", "Schneider Electric SE"]),
    entity("samsung_electronics", "Samsung Electronics Co., Ltd.", "Samsung Electronics", "South Korea", [sec("Korea Exchange", "005930", isin="KR7005930003", mic="XKRX", security_class="common"), sec("Korea Exchange", "005935", isin="KR7005931001", mic="XKRX", security_class="preferred", primary=False), sec("London Stock Exchange", "SMSN", isin="US7960508882", security_class="GDR_common", primary=False), sec("London Stock Exchange", "SMSD", isin="US7960502018", security_class="GDR_preferred", primary=False, vendor_codes=["SMSEL shown on issuer listing-information page"] )], ["samsung_listing", "samsung_current_disclosure"], ["Samsung Electronics", "Samsung Electronics Co., Ltd."], conflict_notes=["Bare 'Samsung' is a conglomerate/group reference and is not promoted as a safe global alias.", "Issuer pages conflict on the preferred GDR display symbol: the listing-information page renders SMSEL, while current 2026 disclosures use SMSD. SMSD is retained as the active disclosure symbol and SMSEL is preserved only as a conflicting vendor display code."]),
    entity("fujitsu", "Fujitsu Limited", "Fujitsu", "Japan", [sec("Tokyo Stock Exchange", "6702", mic="XTKS")], ["fujitsu_listing"], ["Fujitsu", "Fujitsu Limited"]),
    entity("volvo_cars", "Volvo Car AB (publ.)", "Volvo Cars", "Sweden", [sec("Nasdaq Stockholm", "VOLCAR B", isin="SE0016844831", mic="XSTO", security_class="class_B")], ["volvo_cars_listing", "volvo_cars_isin"], ["Volvo Cars", "Volvo Car AB", "Volvo Car AB (publ.)"], conflict_notes=["Volvo Cars / Volvo Car AB is distinct from AB Volvo (Volvo Group, VOLV B). Bare 'Volvo' is not a safe alias."]),
    entity("bmw", "Bayerische Motoren Werke Aktiengesellschaft", "BMW Group", "Germany", [sec("Frankfurt / Munich", "BMW", isin="DE0005190003", security_class="ordinary")], ["bmw_listing"], ["BMW", "BMW AG", "BMW Group", "Bayerische Motoren Werke AG"], temporal_notes=["BMW preferred-share trading ceased on 2026-06-30 after conversion into ordinary shares; only the ordinary line is active here."]),
    entity("advantech", "Advantech Co., Ltd.", "Advantech", "Taiwan", [sec("Taiwan Stock Exchange", "2395", mic="XTAI")], ["advantech_listing"], ["Advantech", "Advantech Co., Ltd."]),
    entity("micro_star", "Micro-Star International Co., Ltd.", "MSI", "Taiwan", [sec("Taiwan Stock Exchange", "2377", mic="XTAI")], ["msi_listing"], ["MSI", "Micro-Star", "Micro-Star International", "Micro-Star International Co., Ltd."]),
    entity("asrock", "ASRock Incorporation", "ASRock", "Taiwan", [sec("Taiwan Stock Exchange", "3515", mic="XTAI")], ["asrock_listing", "asrock_rack_parent"], ["ASRock", "ASRock Inc.", "ASRock Incorporation", "ASRock Rack"], temporal_notes=["ASRock Rack remained a consolidated subsidiary at 2025-12-31 with 46.22% ownership; it is not treated as a separately listed issuer."]),
    entity("aic_taiwan", "AIC Inc.", "AIC (Taiwan)", "Taiwan", [sec("Taipei Exchange", "3693", mic="ROCO")], ["aic_listing", "aic_code"], ["AIC Inc.", "AIC (Taiwan)", "營邦企業"], conflict_notes=["Bare AIC is acronym-ambiguous and is only resolved for the reviewed NVIDIA server-context candidate; it is not a safe global alias."]),
    entity("mitac_holdings", "MiTAC Holdings Corporation", "MiTAC Holdings", "Taiwan", [sec("Taiwan Stock Exchange", "3706", mic="XTAI")], ["mitac_listing", "mitac_computing_parent"], ["MiTAC", "MiTAC Holdings", "MiTAC Holdings Corporation", "MiTAC Computing", "MiTAC Computing Technology Corporation"]),
    entity("geely_auto", "Geely Automobile Holdings Limited", "Geely Auto", "Cayman Islands / Hong Kong listing", [sec("Hong Kong Stock Exchange", "0175", mic="XHKG"), sec("Hong Kong Stock Exchange RMB Counter", "80175", primary=False)], ["geely_listing"], ["Geely Auto", "Geely Automobile", "Geely Automobile Holdings Limited"], conflict_notes=["Bare 'Geely' may denote private Zhejiang Geely Holding Group, Geely Auto Group, a brand, or the listed issuer; it is not promoted globally."]),
    entity("nissan", "Nissan Motor Co., Ltd.", "Nissan", "Japan", [sec("Tokyo Stock Exchange", "7201", mic="XTKS")], ["nissan_listing"], ["Nissan", "Nissan Motor", "Nissan Motor Co., Ltd."]),
    entity("denso", "DENSO Corporation", "DENSO", "Japan", [sec("Tokyo Stock Exchange", "6902", mic="XTKS"), sec("Nagoya Stock Exchange", "6902", primary=False)], ["denso_listing"], ["DENSO", "DENSO Corporation"]),
    entity("dassault_systemes", "Dassault Systèmes SE", "Dassault Systèmes", "France", [sec("Euronext Paris", "DSY", isin="FR0014003TT8", mic="XPAR", vendor_codes=["DSY.PA"])], ["dassault_listing"], ["Dassault Systèmes", "Dassault Systèmes SE"]),
    entity("hexagon", "Hexagon AB", "Hexagon", "Sweden", [sec("Nasdaq Stockholm", "HEXA B", isin="SE0015961909", mic="XSTO", security_class="class_B")], ["hexagon_listing", "hexagon_octave"], ["Hexagon", "Hexagon AB"], temporal_notes=["Octave was distributed and became a separate public company on 2026-05-28; Hexagon AB itself remains listed as HEXA B."]),
    entity("kion", "KION GROUP AG", "KION Group", "Germany", [sec("Frankfurt / Xetra", "KGX", isin="DE000KGX8881", mic="XETR")], ["kion_listing"], ["KION", "KION Group", "KION GROUP AG"]),
    entity("computacenter", "Computacenter plc", "Computacenter", "United Kingdom", [sec("London Stock Exchange", "CCC", mic="XLON")], ["computacenter_listing"], ["Computacenter", "Computacenter plc"]),
    entity("bnp_paribas", "BNP Paribas SA", "BNP Paribas", "France", [sec("Euronext Paris", "BNP", isin="FR0000131104", mic="XPAR")], ["bnp_listing"], ["BNP Paribas", "BNP Paribas SA"]),
    entity("entity_43cff1458d4aab47", "Hitachi, Ltd.", "Hitachi", "Japan", [sec("Tokyo Stock Exchange", "6501", mic="XTKS")], ["hitachi_listing_parent"], ["Hitachi", "Hitachi, Ltd.", "Hitachi Vantara"], merge_action="augment_existing", merge_target_entity_id="entity_43cff1458d4aab47", conflict_notes=["Augments the existing registry's OTC evidence with the primary Tokyo listing; does not create a duplicate Hitachi issuer."]),
    entity("ansys_historical", "ANSYS, Inc.", "Ansys (historical issuer)", "United States", [sec("Nasdaq Global Select Market", "ANSS", status="inactive_at_cutoff")], ["ansys_acquisition", "ansys_delisting"], ["Ansys", "ANSYS, Inc."], listing_status="historical_delisted_acquired", successor_entity_id="synopsys", temporal_notes=["Acquired by Synopsys and Nasdaq Form 25-NSE filed 2025-07-17; ANSS is not an active listed-company relationship endpoint at the 2026-08-25 cutoff."]),
]


ALIAS_SPECS = [
    ("Lenovo", "lenovo_group", "issuer_short_name", "safe_exact", "exact_only", ["lenovo_listing"], None),
    ("Siemens", "siemens_ag", "issuer_short_name", "safe_exact", "exact_only", ["siemens_listing"], "Exclude Siemens Energy when source context names that entity."),
    ("ASUS", "asustek", "brand_to_issuer", "safe_exact", "exact_only", ["asustek_listing"], None),
    ("ASUSTeK", "asustek", "issuer_short_name", "safe_exact", "exact_only", ["asustek_listing"], None),
    ("Foxconn", "hon_hai", "brand_to_issuer", "safe_exact", "exact_only", ["honhai_listing"], None),
    ("Hon Hai", "hon_hai", "issuer_short_name", "safe_exact", "exact_only", ["honhai_listing"], None),
    ("Mercedes-Benz", "mercedes_benz_group", "brand_to_listed_parent", "safe_exact", "exact_only", ["mercedes_listing"], "Relationship subject may operationally be Mercedes-Benz AG; listed endpoint is Mercedes-Benz Group AG."),
    ("Pegatron", "pegatron", "issuer_short_name", "safe_exact", "exact_only", ["pegatron_listing"], None),
    ("GIGABYTE", "gigabyte_technology", "brand_to_issuer", "safe_exact", "exact_only", ["gigabyte_listing"], None),
    ("Giga Computing", "gigabyte_technology", "subsidiary_to_listed_parent", "safe_exact", "exact_only", ["giga_parent"], None),
    ("Wistron", "wistron", "issuer_short_name", "safe_exact", "exact_only", ["wistron_listing"], None),
    ("Inventec", "inventec", "issuer_short_name", "safe_exact", "exact_only", ["inventec_listing"], None),
    ("NAVER", "naver", "issuer_short_name", "safe_exact", "exact_only", ["naver_listing"], None),
    ("NAVER Cloud", "naver", "subsidiary_to_listed_parent", "safe_exact", "exact_only", ["naver_cloud_parent"], None),
    ("Wiwynn", "wiwynn", "issuer_short_name", "safe_exact", "exact_only", ["wiwynn_listing"], None),
    ("Schneider Electric", "schneider_electric", "issuer_short_name", "safe_exact", "exact_only", ["schneider_listing"], None),
    ("Samsung Electronics", "samsung_electronics", "issuer_short_name", "safe_exact", "exact_only", ["samsung_listing"], None),
    ("Samsung", None, "ambiguous_group_name", "ambiguous_not_promoted", "never_auto_match", ["samsung_listing"], "Samsung may refer to the broader conglomerate or another affiliate; require Samsung Electronics explicitly."),
    ("Fujitsu", "fujitsu", "issuer_short_name", "safe_exact", "exact_only", ["fujitsu_listing"], None),
    ("Volvo Cars", "volvo_cars", "issuer_brand", "safe_exact", "exact_only", ["volvo_cars_listing"], "Never collapse to AB Volvo / Volvo Group."),
    ("Volvo", None, "ambiguous_brand", "ambiguous_not_promoted", "never_auto_match", ["volvo_cars_listing"], "Could mean Volvo Cars or AB Volvo."),
    ("BMW", "bmw", "issuer_brand", "safe_exact", "exact_only", ["bmw_listing"], None),
    ("BMW Group", "bmw", "group_brand_to_issuer", "safe_exact", "exact_only", ["bmw_listing"], None),
    ("Advantech", "advantech", "issuer_short_name", "safe_exact", "exact_only", ["advantech_listing"], None),
    ("MSI", "micro_star", "brand_to_issuer", "safe_exact", "exact_only", ["msi_listing"], None),
    ("ASRock", "asrock", "issuer_short_name", "safe_exact", "exact_only", ["asrock_listing"], None),
    ("ASRock Rack", "asrock", "controlled_subsidiary_to_listed_parent", "safe_exact", "exact_only", ["asrock_rack_parent"], "Control is supported by consolidation; ownership disclosed as 46.22% at 2025-12-31."),
    ("AIC", "aic_taiwan", "acronym_context_resolution", "context_bound", "candidate_id_only", ["aic_listing", "aic_code"], "Only valid for reviewed NVIDIA server/storage context; never use as an unrestricted alias."),
    ("AIC Inc.", "aic_taiwan", "legal_name", "safe_exact", "exact_only", ["aic_listing", "aic_code"], None),
    ("MiTAC", "mitac_holdings", "group_brand_to_issuer", "safe_exact", "exact_only", ["mitac_listing"], None),
    ("MiTAC Computing", "mitac_holdings", "subsidiary_to_listed_parent", "safe_exact", "exact_only", ["mitac_computing_parent"], None),
    ("Geely", None, "ambiguous_group_brand", "ambiguous_not_promoted", "never_auto_match", ["geely_listing"], "Could refer to private Zhejiang Geely Holding Group, Geely Auto Group, the car brand, or listed Geely Automobile."),
    ("Geely Auto", "geely_auto", "issuer_short_name", "safe_exact", "exact_only", ["geely_listing"], None),
    ("Geely Automobile", "geely_auto", "issuer_short_name", "safe_exact", "exact_only", ["geely_listing"], None),
    ("Nissan", "nissan", "issuer_short_name", "safe_exact", "exact_only", ["nissan_listing"], None),
    ("DENSO", "denso", "issuer_short_name", "safe_exact", "exact_only", ["denso_listing"], None),
    ("Dassault Systèmes", "dassault_systemes", "issuer_short_name", "safe_exact", "exact_only", ["dassault_listing"], None),
    ("Hexagon", "hexagon", "issuer_short_name", "safe_exact", "exact_only", ["hexagon_listing"], None),
    ("KION", "kion", "issuer_short_name", "safe_exact", "exact_only", ["kion_listing"], None),
    ("KION Group", "kion", "issuer_short_name", "safe_exact", "exact_only", ["kion_listing"], None),
    ("Computacenter", "computacenter", "issuer_short_name", "safe_exact", "exact_only", ["computacenter_listing"], None),
    ("BNP Paribas", "bnp_paribas", "issuer_short_name", "safe_exact", "exact_only", ["bnp_listing"], None),
    ("Google Cloud", "alphabet", "operating_segment_to_listed_parent", "safe_exact", "exact_only", ["google_cloud_parent"], None),
    ("Microsoft Azure", "microsoft", "product_to_listed_parent", "safe_exact", "exact_only", ["azure_parent"], None),
    ("Azure", "microsoft", "product_to_listed_parent", "safe_exact", "exact_only", ["azure_parent"], None),
    ("GitHub", "microsoft", "acquired_subsidiary_to_listed_parent", "safe_exact", "exact_only", ["github_parent"], None),
    ("Red Hat", "entity_7f4992b527dcdcb3", "acquired_subsidiary_to_listed_parent", "safe_exact", "exact_only", ["redhat_parent"], None),
    ("Hitachi Vantara", "entity_43cff1458d4aab47", "subsidiary_to_listed_parent", "safe_exact", "exact_only", ["hitachi_listing_parent"], None),
    ("Ansys", "ansys_historical", "historical_issuer_name", "historical_only", "exact_only", ["ansys_acquisition", "ansys_delisting"], "Do not include as an active listed-company endpoint; successor listed parent is Synopsys."),
]

# Materialize every reviewed legal/issuer alias from the overlay as an explicit
# exact alias row. This prevents the merge from depending on entity-internal
# alias arrays and terminally covers legal-name candidates in candidate_review.
_present_aliases = {norm(spec[0]) for spec in ALIAS_SPECS}
for _entity in ENTITIES:
    _status = "historical_only" if _entity["listing_status"] != "listed_confirmed" else "safe_exact"
    _keys = [key for key, value in EVIDENCE_RAW.items() if value[0] == _entity["entity_id"]]
    for _alias in [_entity["legal_name"], *_entity["aliases"]]:
        if norm(_alias) in _present_aliases:
            continue
        ALIAS_SPECS.append((_alias, _entity["entity_id"], "reviewed_legal_or_issuer_alias", _status, "exact_only", _keys, None))
        _present_aliases.add(norm(_alias))


candidate_rows = [json.loads(line) for line in CANDIDATES.open()] if CANDIDATES.exists() else []
candidate_by_norm: dict[str, list[dict]] = {}
for row in candidate_rows:
    candidate_by_norm.setdefault(row.get("normalized_name") or norm(row["candidate_name"]), []).append(row)


ALIASES = []
for alias, entity_id, kind, status, policy, evidence_keys, note in ALIAS_SPECS:
    matches = candidate_by_norm.get(norm(alias), [])
    row = {
        "alias_id": aid(alias),
        "alias": alias,
        "normalized_alias": norm(alias),
        "entity_id": entity_id,
        "alias_kind": kind,
        "alias_status": status,
        "match_policy": policy,
        "fuzzy_matching_allowed": False,
        "listing_evidence_ids": [eid(k) for k in evidence_keys],
        "candidate_review_ids": [m["candidate_id"] for m in matches],
        "candidate_observation_count": sum(m.get("observation_count", 0) for m in matches),
        "disambiguation_note": note,
        "reviewed_at": RETRIEVED,
    }
    ALIASES.append(row)


DECISIONS = []
for spec in ALIAS_SPECS:
    alias, entity_id, kind, status, policy, evidence_keys, note = spec
    matches = candidate_by_norm.get(norm(alias), [])
    terminal = {
        "safe_exact": "resolved_listed_parent",
        "context_bound": "resolved_context_bound",
        "ambiguous_not_promoted": "ambiguous_terminal",
        "historical_only": "historical_not_active_terminal",
    }[status]
    DECISIONS.append({
        "decision_id": did(alias),
        "input_name": alias,
        "normalized_input": norm(alias),
        "candidate_review_ids": [m["candidate_id"] for m in matches],
        "candidate_observation_count": sum(m.get("observation_count", 0) for m in matches),
        "terminal_status": terminal,
        "entity_id": entity_id,
        "decision_method": policy,
        "fuzzy_promotion_used": False,
        "global_alias_promoted": status == "safe_exact",
        "rationale": note or f"Official issuer/exchange evidence supports the exact {kind} mapping.",
        "listing_evidence_ids": [eid(k) for k in evidence_keys],
        "reviewed_at": RETRIEVED,
    })


# OCR-decorated lookalikes are terminally rejected rather than silently normalized.
core_tokens = {norm(a[0]) for a in ALIAS_SPECS if len(norm(a[0])) >= 4}
already = {cid for d in DECISIONS for cid in d["candidate_review_ids"]}
for cand in candidate_rows:
    if cand["candidate_id"] in already:
        continue
    n = cand.get("normalized_name") or norm(cand["candidate_name"])
    if any(t in n or n in t for t in core_tokens):
        DECISIONS.append({
            "decision_id": did(cand["candidate_id"]),
            "input_name": cand["candidate_name"],
            "normalized_input": n,
            "candidate_review_ids": [cand["candidate_id"]],
            "candidate_observation_count": cand.get("observation_count", 0),
            "terminal_status": "rejected_not_exact_terminal",
            "entity_id": None,
            "decision_method": "exact_only",
            "fuzzy_promotion_used": False,
            "global_alias_promoted": False,
            "rationale": "Name is an OCR-decorated, phrase-level, or otherwise non-exact lookalike; no fuzzy stripping or promotion is permitted.",
            "listing_evidence_ids": [],
            "reviewed_at": RETRIEVED,
        })


def write_jsonl(name: str, rows: list[dict]) -> None:
    with (HERE / name).open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


write_jsonl("entity_registry_overlay.jsonl", ENTITIES)
write_jsonl("aliases.jsonl", ALIASES)
write_jsonl("listing_evidence.jsonl", EVIDENCE)
write_jsonl("decision_ledger.jsonl", DECISIONS)

print(json.dumps({
    "entities": len(ENTITIES),
    "active_listed_entities": sum(e["listing_status"] == "listed_confirmed" for e in ENTITIES),
    "aliases": len(ALIASES),
    "evidence": len(EVIDENCE),
    "decisions": len(DECISIONS),
}, ensure_ascii=False))

#!/usr/bin/env python3
"""Build public regulatory-source routes for every listed Partner in the snapshot.

This script writes only inside its own agent directory. It never edits the snapshot.
Network access is deliberately not required: public entry points were manually verified
on the official operator/regulator sites as of 2026-08-25.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[3]
SNAPSHOT = REPOSITORY_ROOT / "data" / "snapshot_2026-08-25.json"
AS_OF = "2026-08-25"


COMMON_FAILURES = [
    "source_unavailable_transient",
    "rate_limited",
    "js_session_required",
    "captcha_or_human_challenge",
    "access_controlled_login",
    "identifier_missing",
    "no_exact_issuer_match",
    "no_documents_in_date_range",
    "issuer_outside_source_jurisdiction",
    "historical_archive_required",
    "document_link_broken_or_removed",
    "source_terms_prohibit_automation",
    "manual_review_required",
]


def source(
    source_id: str,
    regions: list[str],
    name: str,
    operator: str,
    authority_type: str,
    entry_url: str,
    verification_url: str,
    identifiers: list[str],
    document_types: list[str],
    query_recipe: list[str],
    access_class: str,
    constraints: list[str],
    official_basis: str,
    query_url_template: str | None = None,
    route_status: str = "active_public",
) -> dict:
    return {
        "source_id": source_id,
        "jurisdiction_regions": regions,
        "source_name": name,
        "operator": operator,
        "authority_type": authority_type,
        "route_status": route_status,
        "entry_url": entry_url,
        "query_url_template": query_url_template,
        "identifier_priority": identifiers,
        "supported_document_types": document_types,
        "query_recipe": query_recipe,
        "access": {
            "class": access_class,
            "public_read_without_login": route_status == "active_public",
            "automation_default": "manual_or_low_rate_only",
            "constraints": constraints,
        },
        "official_basis": official_basis,
        "failure_terminals": COMMON_FAILURES,
        "verification": {
            "verified_at": AS_OF,
            "method": "official_public_page_and_search_entry_review",
            "verification_url": verification_url,
        },
    }


SOURCES = [
    source(
        "us_sec_edgar", ["United States"], "SEC EDGAR", "U.S. Securities and Exchange Commission",
        "national_securities_regulator", "https://www.sec.gov/search-filings",
        "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
        ["cik", "ticker", "legal_name"],
        ["10-K", "10-Q", "8-K", "20-F", "40-F", "6-K", "registration_statement", "proxy", "ownership_forms", "Form_25"],
        ["Prefer the zero-padded CIK from the snapshot.", "Otherwise use ticker, then confirm the legal name and exchange on the company landing page.", "Filter by filing form and filing date; preserve accession number and filing date."],
        "public_no_login_rate_limited",
        ["Free public read access.", "Automated access must follow SEC fair-access guidance, identify the client, and remain at or below the published request-rate ceiling.", "Some pre-1994 or paper filings are not available electronically."],
        "EDGAR is the SEC public filing system for registration statements, periodic/current reports and ownership filings.",
        "https://www.sec.gov/edgar/browse/?CIK={identifier}&owner=exclude",
    ),
    source(
        "hk_hkexnews", ["Hong Kong"], "HKEXnews Listed Company Publications", "Hong Kong Exchanges and Clearing Limited",
        "exchange_regulatory_disclosure_platform", "https://www.hkexnews.hk/search/titlesearch.xhtml?lang=en",
        "https://www2.hkexnews.hk/-/media/HKEXnews/Homepage/Listed-Company-Publications/Search-Guide/TitleSearchGuide_e.pdf",
        ["ticker", "legal_name"],
        ["annual_report", "interim_report", "announcement", "circular", "listing_document", "monthly_return", "ESG_report", "delisting_or_suspension_notice"],
        ["Enter the numeric stock code or legal name and select the autocomplete issuer.", "Set From/To dates and document category.", "For former issuers, switch to delisted-securities search; record release time and document URL."],
        "public_browser_js_session",
        ["No login is needed for reading.", "Search relies on JavaScript/session state and an internal stockId; do not invent stockId values.", "Copyright and site terms apply; no bulk mirroring."],
        "HKEXnews is HKEX's central platform for issuer-submitted and HKEX-generated regulatory issuer information.",
    ),
    source(
        "tw_mops", ["Taiwan"], "MOPS 公開資訊觀測站", "Taiwan Stock Exchange Corporation",
        "exchange_designated_public_disclosure_platform", "https://mops.twse.com.tw/",
        "https://mops.twse.com.tw/",
        ["ticker", "legal_name"],
        ["material_information", "financial_statements", "annual_report", "monthly_revenue", "shareholding", "corporate_governance", "prospectus", "company_profile"],
        ["Use the company code as the primary key.", "Select the required disclosure family and reporting period.", "Distinguish TWSE from TPEx in the returned company profile."],
        "public_browser_session_postback",
        ["Public read access; forms may use POST requests, cookies and anti-replay state.", "Use a browser/manual workflow if a direct request loses session context.", "Chinese is often the authoritative language."],
        "MOPS is Taiwan's official public company disclosure observation post system operated by TWSE.",
    ),
    source(
        "kr_dart", ["South Korea"], "DART / English DART", "Financial Supervisory Service",
        "national_regulator_disclosure_system", "https://englishdart.fss.or.kr/dsbb007/main.do?option=corp",
        "https://englishdart.fss.or.kr/about/engAbout4.do",
        ["ticker", "legal_name"],
        ["annual_report", "semiannual_report", "quarterly_report", "material_event", "issuance", "equity_ownership", "audit_report", "XBRL_financials"],
        ["Search by Korean stock code or exact company name.", "Confirm KOSPI/KOSDAQ market and corporate code in the company profile.", "Capture receipt number (rcpNo), filing date, report title and revision/withdrawal flag."],
        "public_browser_session",
        ["Public read access.", "English DART may not expose every Korean-language filing or field; fall back to Korean DART without bypassing controls.", "OpenDART API requires a registered API key and is not assumed here."],
        "DART is the FSS electronic disclosure system for Korean corporate filings.",
    ),
    source(
        "jp_edinet", ["Japan"], "EDINET", "Financial Services Agency of Japan",
        "national_regulator_statutory_filing_system", "https://disclosure2.edinet-fsa.go.jp/week0020.aspx",
        "https://disclosure2.edinet-fsa.go.jp/week0020.aspx",
        ["ticker", "legal_name", "edinet_code"],
        ["annual_securities_report", "semiannual_report", "quarterly_report", "large_shareholding_report", "registration_statement", "tender_offer_document", "XBRL"],
        ["Search by stock code or exact submitter/issuer name.", "Confirm EDINET code and document type.", "Capture document ID, filing date and amendment/supersession status."],
        "public_browser_api_key_for_api_only",
        ["Browser search and documents are public.", "EDINET API use requires registration and an API key; do not scrape around that requirement.", "Scheduled maintenance can make both web and API temporarily unavailable."],
        "EDINET is the FSA statutory disclosure system; its public UI includes detailed and simple document search.",
    ),
    source(
        "jp_tdnet", ["Japan"], "TDnet / JPX Listed Company Search", "Japan Exchange Group / Tokyo Stock Exchange",
        "exchange_timely_disclosure_system", "https://www.jpx.co.jp/english/listing/co-search/index.html",
        "https://www.jpx.co.jp/english/equities/listing/disclosure/tdnet/",
        ["ticker", "legal_name"],
        ["timely_disclosure", "earnings_summary", "material_event", "English_disclosure", "public_inspection_document", "ESG_report"],
        ["Use the four-digit company code in Listed Company Search.", "Filter by disclosure date and document family.", "Use EDINET for statutory securities reports; use TDnet for exchange timely disclosures."],
        "public_browser_search_with_retention_limits",
        ["Immediate Company Announcements service retains roughly 31 days.", "Listed Company Search provides a longer public window (described by JPX as ten years for timely disclosures).", "Some English filings are summaries or delayed translations."],
        "JPX states listed companies use TDnet for fair and prompt timely disclosure and exposes public search services.",
    ),
    source(
        "cn_cninfo", ["China"], "巨潮资讯网 CNINFO", "Shenzhen Securities Information Co., Ltd. (wholly owned by SZSE)",
        "statutory_exchange_disclosure_platform", "https://www.cninfo.com.cn/new/index",
        "https://list.cninfo.com.cn/cninfo/",
        ["ticker", "legal_name"],
        ["annual_report", "interim_report", "quarterly_report", "material_announcement", "prospectus", "governance", "ownership_change"],
        ["Search the six-digit stock code first.", "Filter market, announcement category and date.", "Cross-check the exchange-hosted copy for high-risk delisting or suspension events."],
        "public_browser_js_rate_limited",
        ["Public read access.", "Dynamic APIs may require normal browser headers/session state and may throttle repeated requests.", "Do not defeat challenges or replay private endpoints."],
        "CNINFO identifies itself as SZSE's statutory information-disclosure platform and is operated by SZSE's wholly owned information subsidiary.",
    ),
    source(
        "cn_sse", ["China"], "Shanghai Stock Exchange Listed Company Announcements", "Shanghai Stock Exchange",
        "exchange_regulatory_disclosure_platform", "https://www.sse.com.cn/disclosure/listedinfo/announcement/",
        "https://english.sse.com.cn/markets/equities/announcements/",
        ["ticker", "legal_name"],
        ["listed_company_announcement", "periodic_report", "material_event", "listing_or_delisting_notice", "regulatory_inquiry_response"],
        ["Use the six-digit code and date range.", "For STAR issuers, also check the STAR announcements page.", "Treat the Chinese filing as authoritative when an English translation differs."],
        "public_browser_js",
        ["Public read access.", "Search pages can be JavaScript-backed and may block high-rate automation.", "English coverage is not complete."],
        "CSRC disclosure rules require filings on the stock exchange website; SSE provides a public announcements search.",
    ),
    source(
        "cn_szse", ["China"], "Shenzhen Stock Exchange Company Announcements", "Shenzhen Stock Exchange",
        "exchange_regulatory_disclosure_platform", "https://www.szse.cn/disclosure/listed/notice/index.html",
        "https://www.szse.cn/English/disclosures/announcements/index.html",
        ["ticker", "legal_name"],
        ["listed_company_announcement", "periodic_report", "material_event", "listing_or_delisting_notice", "regulatory_action"],
        ["Use the six-digit code and announcement date range.", "Use the Chinese disclosure portal for complete results; English is supplementary.", "Preserve exchange publication time and attachment URL."],
        "public_browser_js",
        ["Public read access.", "Dynamic search may require JavaScript/session state.", "English coverage may be partial."],
        "SZSE publishes listed-company announcements through its public disclosure pages.",
    ),
    source(
        "uk_fca_nsm", ["United Kingdom"], "FCA National Storage Mechanism", "Financial Conduct Authority",
        "national_regulator_official_storage_mechanism", "https://data.fca.org.uk/#/nsm/nationalstoragemechanism",
        "https://www.fca.org.uk/markets/primary-markets/regulatory-disclosures/national-storage-mechanism",
        ["lei", "legal_name", "ticker"],
        ["regulated_announcement", "annual_financial_report_ESEF", "prospectus", "listing_document", "inside_information", "major_holding", "correction"],
        ["Search by LEI when available, then exact legal name.", "Filter filing/publication date and headline category.", "Export search results or download original/JSON/CSV when offered; review hidden prior versions for corrections."],
        "public_browser_js_export",
        ["Public view/download is free without login.", "NSM is not real-time; FCA advises contacting the issuer if expected information is absent after 48 hours.", "Historic pre-April-2020 material may require the URL lookup route."],
        "The FCA identifies NSM as its official store of regulated information under UK listing, DTR, MAR and prospectus rules.",
    ),
    source(
        "ca_sedar_plus", ["Canada"], "SEDAR+", "Canadian Securities Administrators",
        "national_federated_regulatory_filing_system", "https://www.sedarplus.ca/csa-security/relay.html?target=csa-party&targetAppCode=csa-security&url=https%3A%2F%2Fwww.sedarplus.ca%2Fcsa-party%2Fservice%2Fcreate.html%3FtargetAppCode%3Dcsa-security%26service%3DsearchDocuments",
        "https://www.sedarplus.ca/onlinehelp/filings/view-a-filing/information-shown-on-a-submitted-filing/",
        ["legal_name", "profile_number", "ticker"],
        ["annual_and_interim_financials", "MD&A", "AIF", "material_change_report", "news_release", "prospectus", "early_warning", "issuer_profile", "regulatory_action"],
        ["Resolve the issuer profile by exact legal name/profile number.", "Search documents within that profile and filter filing/document type and date.", "Use the legacy archive for older non-migrated SEDAR documents."],
        "public_browser_session",
        ["Public sections and public documents are visible without issuer authority.", "The site uses relay/session navigation.", "Not all pre-2016 legacy filings are migrated; use the public legacy archive or CSA service route."],
        "SEDAR+ is the CSA system for issuer profiles, public filings and regulatory actions.",
    ),
    source(
        "au_asx_announcements", ["Australia"], "ASX Market Announcements", "ASX Limited",
        "exchange_market_announcement_platform", "https://www.asx.com.au/asx/v2/statistics/announcements.do",
        "https://www.asx.com.au/markets/trade-our-cash-market/announcements",
        ["ticker", "legal_name"],
        ["market_announcement", "annual_report", "half_year_report", "Appendix_3Y_4C_4E_5B", "capital_change", "meeting_document", "trading_halt"],
        ["Search by three-character ASX code or start of company name.", "Set date/released-during filters and enable delisted/code-change search when needed.", "Capture release date/time and price-sensitive flag."],
        "public_browser_terms_apply",
        ["Public read access.", "ASX terms and third-party market-data restrictions apply.", "Announcement search uses the first three characters of the ticker code."],
        "ASX exposes current and historical market announcements through its official public search.",
        "https://www.asx.com.au/markets/company/{identifier}",
    ),
    source(
        "in_nse_filings", ["India"], "NSE Corporate Filings", "National Stock Exchange of India Limited",
        "recognized_exchange_disclosure_platform", "https://www.nseindia.com/companies-listing/corporate-filings-announcements?tabIndex=equity",
        "https://www.nseindia.com/companies-listing/corporate-filings-announcements?tabIndex=equity",
        ["ticker", "legal_name"],
        ["corporate_announcement", "financial_results", "annual_report", "shareholding_pattern", "corporate_governance", "board_meeting", "XBRL", "material_event"],
        ["Search by NSE symbol and choose Equity.", "Set custom date range and subject/category.", "Capture exchange received/dissemination time and attachment/XBRL links."],
        "public_browser_cookie_rate_limited",
        ["Public read access.", "The site may require an initial homepage cookie and applies anti-bot/rate controls.", "Do not bypass 401/403/challenges; use manual browser fallback."],
        "NSE is a recognized exchange and disseminates listed-entity filings submitted under SEBI listing obligations.",
        "https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={identifier}&tabIndex=equity",
    ),
    source(
        "in_bse_filings", ["India"], "BSE Corporate Announcements", "BSE Limited",
        "recognized_exchange_disclosure_platform", "https://www.bseindia.com/corporates/ann.html",
        "https://www.bseindia.com/corporates/ann.html",
        ["bse_scrip_code", "legal_name", "isin", "ticker"],
        ["corporate_announcement", "annual_report", "financial_results", "LODR_disclosure", "meeting", "shareholding", "XBRL"],
        ["Search by BSE scrip code, ISIN or exact security name.", "Filter announcement period/category.", "If only an NSE symbol is known, first resolve the BSE scrip code rather than treating symbols as interchangeable."],
        "public_browser_session",
        ["Public read access.", "Pages can rely on session state and legacy ASP.NET controls.", "BSE scrip code is distinct from the NSE symbol."],
        "BSE disseminates listed-entity filings submitted under SEBI listing obligations.",
    ),
    source(
        "de_unternehmensregister", ["Germany"], "Unternehmensregister / Company Register", "Bundesanzeiger Verlag on behalf of the German Federal Ministry of Justice",
        "national_official_company_and_capital_market_register", "https://www.unternehmensregister.de/ureg/?submitaction=show",
        "https://www.unternehmensregister.de/ureg/pdf/D001_EN.pdf",
        ["legal_name", "isin", "register_number", "ticker"],
        ["annual_financial_statement", "management_report", "capital_market_information", "inside_information", "voting_rights", "prospectus_notice", "register_document"],
        ["Use exact legal name and, if available, register number/ISIN.", "Select Accounting/financial reports or Capital-market information and set publication dates.", "Record publication source, date and document identifier."],
        "public_search_mixed_free_and_paid_documents",
        ["Search and much capital-market information are public.", "Some register documents or retrieval products may require registration/payment.", "Do not treat a paywalled register extract as absent; terminate as access_controlled_login_or_payment."],
        "The Company Register is Germany's official central platform for company and capital-market publications.",
    ),
    source(
        "fr_amf_bdif", ["France"], "AMF BDIF", "Autorité des marchés financiers",
        "national_regulator_decisions_and_financial_disclosures_database", "https://bdif.amf-france.org/en",
        "https://www.amf-france.org/fr/actualites-publications/actualites/bdif-fait-peau-neuve-pour-mieux-repondre-vos-attentes",
        ["legal_name", "isin", "reference", "ticker"],
        ["prospectus", "takeover_bid", "director_dealing", "major_holding", "waiver_or_decision", "net_short_position", "final_terms", "other_information_document"],
        ["Search exact company name, AMF reference or keyword.", "Filter publication date and information type.", "For periodic issuer reports and inside information, also use Euronext company news/issuer website as BDIF scope is not exhaustive for every report family."],
        "public_browser_search_rss",
        ["Public search/download and RSS are available.", "AMF states pre-2008 decisions may not be exhaustive.", "Original-language document controls."],
        "AMF describes BDIF as its decisions and financial disclosures database for listed companies and prospectus issuers.",
    ),
    source(
        "eu_euronext_company_news", ["France", "Netherlands"], "Euronext Company Press Releases Archive", "Euronext N.V.",
        "regulated_exchange_company_news_archive", "https://live.euronext.com/en/products/equities/company-news-archive",
        "https://live.euronext.com/en/products/equities/company-news-archive",
        ["isin", "legal_name", "ticker"],
        ["annual_financial_report", "half_year_report", "inside_information", "major_holding", "capital_and_voting_rights", "buyback", "legal_notice", "other_regulated_information"],
        ["Search issuer name/ISIN and choose the trading location.", "Set a custom date range and regulatory topic.", "Exclude rows explicitly labelled non-regulatory when the task requires regulated information."],
        "public_browser_js_filters",
        ["Public browser search is available.", "Results mix regulatory and non-regulatory releases; classification must be retained.", "Subscription functions may require an account but reading does not."],
        "Euronext's public archive exposes issuer releases with trading location and regulatory topic filters.",
    ),
    source(
        "nl_afm_reporting", ["Netherlands"], "AFM Financial Reporting Register", "Netherlands Authority for the Financial Markets",
        "national_regulator_official_register", "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/financiele-verslaggeving",
        "https://www.afm.nl/en/sector/effectenuitgevende-ondernemingen/financiele-en-duurzaamheidsverslaggeving/verkrijgbaar-stellen-en-deponeren",
        ["legal_name", "lei", "isin"],
        ["annual_financial_report_ESEF", "semiannual_financial_report", "adopted_annual_report"],
        ["Search exact statutory name and filing date.", "Confirm home Member State is the Netherlands.", "Download/export XML or CSV metadata where available and preserve the filed document format."],
        "public_search_export",
        ["Public search and CSV/XML export are available.", "Coverage depends on Netherlands being the issuer's home Member State.", "Dutch-language metadata may control."],
        "AFM states filed annual and semiannual reporting is placed in its public register and that AFM is the Dutch OAM.",
    ),
    source(
        "nl_afm_inside_information", ["Netherlands"], "AFM Inside Information Register", "Netherlands Authority for the Financial Markets",
        "national_regulator_public_register", "https://www.afm.nl/en/sector/registers/meldingenregisters/openbaarmaking-voorwetenschap",
        "https://www.afm.nl/en/sector/registers/meldingenregisters/openbaarmaking-voorwetenschap",
        ["legal_name", "lei", "isin"],
        ["inside_information_press_release", "material_event", "periodic_report_release_notice"],
        ["Search statutory name and date range.", "Open the archived press release and preserve publication time.", "Use the reporting register for the full ESEF/periodic report."],
        "public_search_export",
        ["Public archive, with slight publication delay.", "Coverage is issuers admitted to trading in the Netherlands and within the register's statutory scope."],
        "AFM maintains this public register under Dutch law for Article 17 MAR press releases.",
    ),
    source(
        "se_fi_borsinformation", ["Sweden"], "Finansinspektionen Börsinformation", "Swedish Financial Supervisory Authority",
        "national_regulator_stock_exchange_information_database", "https://www.fi.se/sv/vara-register/borsinformation/",
        "https://www.fi.se/en/markets/issuers/periodic-financial-information/",
        ["legal_name", "lei", "isin", "ticker"],
        ["annual_report", "half_year_report", "inside_information", "major_holding", "share_and_vote_change", "buyback", "payments_to_government"],
        ["Search the issuer's exact legal name in Börsinformation.", "Filter document type and date.", "Confirm Sweden is the home Member State; otherwise route to the issuer's home-state OAM."],
        "public_search_open_data",
        ["Public searchable database.", "FI states its open data is free to use with source/date attribution.", "Coverage is home-Member-State based, not merely trading-venue based."],
        "FI states regulated-market issuers with Sweden as home Member State file public financial and other mandatory information in Börsinformation.",
    ),
    source(
        "fi_oam", ["Finland"], "Suomen OAM / Finnish National Disclosure Storage", "Nasdaq Helsinki Oy",
        "officially_appointed_storage_mechanism", "https://oam.fi/",
        "https://www.nasdaq.com/market-regulation/nordic/helsinki",
        ["legal_name", "business_id", "lei", "isin", "ticker"],
        ["annual_financial_report_ESEF", "half_year_report", "inside_information", "managers_transaction", "major_holding", "share_and_vote_change", "takeover_bid", "other_regulated_information"],
        ["Search the issuer's exact legal name or ticker in the Finnish OAM.", "Filter disclosure category and publication period.", "Preserve the OAM view URL, publication timestamp, language and correction category."],
        "public_search_export",
        ["Public search/read access and result export are available.", "Scope is issuers whose home state is Finland and whose securities are on a regulated market.", "Finnish/Swedish original-language disclosure may control over an English translation."],
        "Nasdaq Helsinki is Finland's designated OAM and keeps issuers' regulated information publicly available in the national disclosure storage.",
    ),
    source(
        "eu_nasdaq_nordic_news", ["Sweden", "Finland"], "Nasdaq Nordic Company News", "Nasdaq Nordic",
        "exchange_company_news_platform", "https://www.nasdaq.com/european-market-activity/news/company-news",
        "https://www.nasdaq.com/european-market-activity/news/company-news",
        ["legal_name", "ticker", "isin"],
        ["regulated_company_announcement", "financial_report_release", "inside_information", "takeover", "capital_change", "alliance_or_material_event"],
        ["Filter by country/exchange and exact company name.", "Retain the Reg/non-Reg label and language.", "For statutory financial reports, cross-check the national OAM when the issuer is on a regulated market."],
        "public_browser_js_filters",
        ["Public read access.", "Only messages filed with Nasdaq are included; the issuer may publish additional material elsewhere.", "Main Market and First North have different regulatory bases."],
        "Nasdaq states it continuously publishes announcements filed by companies listed on its Nordic markets.",
    ),
    source(
        "no_newsweb", ["Norway"], "Oslo Børs NewsWeb", "Euronext Oslo Børs",
        "officially_appointed_storage_mechanism", "https://newsserviceweb.oslobors.no/",
        "https://www.finanstilsynet.no/en/reporting/financial-reporting/",
        ["ticker", "isin", "legal_name"],
        ["annual_report_ESEF", "half_year_report", "inside_information", "mandatory_notification", "major_holding", "buyback", "financial_calendar"],
        ["Search issuer/ticker and date range; enable OAM-only when statutory storage is required.", "Open the announcement and attachment; preserve message ID and correction/version status.", "Use the company-news view only as a convenience; NewsWeb is the OAM record."],
        "public_browser_js_database_terms",
        ["Public read access but JavaScript is required.", "Database copyright and reuse restrictions apply; no bulk republication.", "Transient system-unavailable pages should be retried later, not bypassed."],
        "Finanstilsynet identifies Oslo Børs NewsWeb as Norway's designated OAM for published periodic financial reporting.",
    ),
    source(
        "ch_six_official_notices", ["Switzerland"], "SIX Swiss Exchange Official Notices", "SIX Swiss Exchange",
        "exchange_official_notice_platform", "https://www.six-group.com/en/market-data/news-tools/official-notices.html",
        "https://www.six-group.com/en/market-data/news-tools/official-notices.html",
        ["isin", "valor", "legal_name", "ticker"],
        ["company_event", "merger_or_acquisition", "capital_change", "dividend", "interest_rate_notice", "security_notice"],
        ["Search by issuer and ISIN/Valor.", "Filter notice type and date.", "For ad-hoc publicity and management transactions, follow the linked SIX News & Tools registers."],
        "public_browser_js_filters",
        ["Public read access.", "Dynamic data can temporarily fail to load; use manual browser retry.", "Official Notices are not a complete archive of every issuer financial report."],
        "SIX states it publishes official notices for security-related and corporate events reported by listed companies.",
    ),
    source(
        "it_1info", ["Italy"], "1INFO Regulated Information Storage", "Computershare S.p.A.",
        "consob_authorized_storage_mechanism", "https://www.1info.it/PORTALE1INFO",
        "https://www.consob.it/documents/718268/2284401/ar2015.pdf/565a3479-d2e8-5faf-48c2-0a003565ec23",
        ["legal_name", "isin", "ticker"],
        ["annual_financial_report", "half_year_report", "inside_information", "shareholding", "capital_change", "governance", "regulated_press_release"],
        ["Search exact issuer name/ISIN and date range.", "Confirm the result is stored regulated information rather than an unrelated news item.", "Capture storage timestamp and original document."],
        "public_browser_search",
        ["Public search/read access.", "Italian may be authoritative.", "If unavailable, terminate transiently and consult another CONSOB-authorized storage mechanism; do not substitute a media repost."],
        "CONSOB authorized 1INFO as a regulated-information storage mechanism and supervises authorized storage operators.",
    ),
    source(
        "lu_luxse_oam", ["Luxembourg"], "LuxSE Officially Appointed Mechanism", "Luxembourg Stock Exchange",
        "officially_appointed_storage_mechanism", "https://www.luxse.com/issuer-services-overview/oam/oam-search",
        "https://www.luxse.com/issuer-services-overview/oam/oam-search",
        ["isin", "cssf_code", "legal_name", "ticker"],
        ["periodic_financial_report", "ongoing_information", "inside_information", "major_holding", "prospectus_related_document", "other_regulated_information"],
        ["Search by ISIN or exact issuer name; CSSF code is preferred when known.", "Filter publication date, reference year and regulated-information type.", "Preserve OAM document URL and metadata."],
        "public_browser_search",
        ["Public central archive.", "Scope is issuers under Luxembourg home-Member-State transparency obligations.", "Filing functions require authorization, but public reading does not."],
        "LuxSE states it operates Luxembourg's OAM and centrally archives regulated information for public access.",
    ),
    source(
        "pl_espi_public", ["Poland"], "ESPI/EBI Public Reports Search", "Polish Financial Supervision Authority system; public dissemination by Polish Press Agency",
        "regulator_electronic_reporting_and_public_dissemination", "https://espiebi.pap.pl/wyszukiwarka",
        "https://www.knf.gov.pl/dla_konsumenta/kampanie_informacyjne/zrodla_informacji_o_emitentach",
        ["legal_name", "ticker", "isin"],
        ["current_report", "periodic_report", "inside_information", "management_transaction", "major_holding", "financial_report", "ESPI_or_EBI_report"],
        ["Search exact issuer name/ticker and choose ESPI versus EBI.", "Filter report date and category.", "Confirm regulated-market versus alternative-market status and retain report number."],
        "public_browser_search",
        ["Public search access.", "Issuer submission access to ESPI is credentialed; this route is public reading only.", "Polish-language report controls."],
        "KNF identifies ESPI and directs consumers to the public issuer-report sources, including PAP dissemination.",
    ),
    source(
        "sg_sgxnet", ["Singapore"], "SGXNet Company Announcements", "Singapore Exchange Securities Trading Limited",
        "exchange_regulatory_announcement_platform", "https://www.sgx.com/securities/company-announcements",
        "https://www.sgx.com/securities/company-announcements",
        ["ticker", "legal_name"],
        ["company_announcement", "annual_report", "financial_statement", "offer_document", "circular", "material_event", "corporate_action"],
        ["Filter by exact company/security name or ticker.", "Select announcement date/category and open attachments hosted on links.sgx.com.", "Retain announcement reference and whether SGX reviewed the content."],
        "public_browser_modern_browser_required",
        ["Public read access.", "SGX may reject unsupported browsers and relies on modern JavaScript.", "Do not bypass browser checks; use a supported interactive browser."],
        "SGXNet is SGX's company-announcement and issuer-document dissemination platform.",
    ),
    source(
        "my_bursa_announcements", ["Malaysia"], "Bursa Malaysia Company Announcements", "Bursa Malaysia Berhad",
        "exchange_regulatory_announcement_platform", "https://www.bursamalaysia.com/market_information/announcements/company_announcement",
        "https://www.bursamalaysia.com/market_information/announcements/company_announcement",
        ["ticker", "legal_name"],
        ["company_announcement", "financial_results", "annual_report", "circular", "material_event", "shareholding", "listing_status"],
        ["Select the company or search an announcement title of at least five characters.", "Set date range, category, market and sector.", "Record announcement date, category and attachment."],
        "public_browser_js_filters",
        ["Public read access.", "Bursa states it does not verify or endorse issuer announcement contents.", "Search title has a five-character minimum and may rely on JavaScript."],
        "Bursa Malaysia provides the official company-announcement search for public listed companies.",
    ),
    source(
        "vn_hose_disclosure", ["Vietnam"], "HOSE Information Disclosure", "Ho Chi Minh Stock Exchange",
        "exchange_information_disclosure_platform", "https://www.hsx.vn/",
        "https://ssc.gov.vn/webcenter/portal/ssc/pages_r/l/chitit?dDocName=APPSSCGOVVN1620147389",
        ["ticker", "legal_name"],
        ["periodic_financial_report", "annual_report", "extraordinary_information", "requested_disclosure", "governance_report", "listing_status", "exchange_notice"],
        ["Use HOSE's information-disclosure/company search with the ticker.", "Filter periodic versus extraordinary disclosure and date.", "If the portal is unavailable, record the terminal state and use the issuer's own disclosed copy only as corroboration, not as a silent replacement."],
        "public_browser_js_unstable",
        ["Public portal but JavaScript/system availability can be unstable.", "Vietnamese is authoritative; English coverage follows a phased statutory roadmap.", "Do not bypass portal controls or use unofficial mirrors as regulatory evidence."],
        "Vietnam SSC states HOSE-listed organizations use the HOSE disclosure system as the single focal point for periodic and irregular disclosures.",
    ),
    source(
        "eu_esap_future", ["Germany", "France", "Netherlands", "Sweden", "Finland", "Italy", "Luxembourg", "Poland"],
        "European Single Access Point (future public route)", "European Securities and Markets Authority",
        "supranational_future_access_point", "https://www.esma.europa.eu/press-news/esma-news/esma-launches-data-collection-under-first-phase-esap",
        "https://www.esma.europa.eu/press-news/esma-news/esma-launches-data-collection-under-first-phase-esap",
        ["lei", "legal_name", "isin"],
        ["future_EU_financial_and_sustainability_information"],
        ["Do not route production lookups here at the 2026-08-25 cutoff.", "Use the national OAM/NCA route until ESAP opens to the public."],
        "not_public_at_cutoff",
        ["ESMA began collection on 2026-07-10 but states the platform becomes public by July 2027."],
        "ESMA official launch notice: collection has started, but public access is not yet live.",
        route_status="future_not_public",
    ),
]


REGION_ROUTES = {
    "United States": ["us_sec_edgar"],
    "Hong Kong": ["hk_hkexnews"],
    "Taiwan": ["tw_mops"],
    "South Korea": ["kr_dart"],
    "Japan": ["jp_edinet", "jp_tdnet"],
    "China": ["cn_cninfo", "cn_sse", "cn_szse"],
    "United Kingdom": ["uk_fca_nsm"],
    "Canada": ["ca_sedar_plus"],
    "Australia": ["au_asx_announcements"],
    "India": ["in_nse_filings", "in_bse_filings"],
    "Germany": ["de_unternehmensregister"],
    "France": ["fr_amf_bdif", "eu_euronext_company_news"],
    "Netherlands": ["nl_afm_reporting", "nl_afm_inside_information", "eu_euronext_company_news"],
    "Sweden": ["se_fi_borsinformation", "eu_nasdaq_nordic_news"],
    "Finland": ["fi_oam", "eu_nasdaq_nordic_news"],
    "Norway": ["no_newsweb"],
    "Switzerland": ["ch_six_official_notices"],
    "Italy": ["it_1info"],
    "Luxembourg": ["lu_luxse_oam"],
    "Poland": ["pl_espi_public"],
    "Singapore": ["sg_sgxnet"],
    "Malaysia": ["my_bursa_announcements"],
    "Vietnam": ["vn_hose_disclosure"],
}


ACCESS_POLICY = {
    "as_of": AS_OF,
    "scope": "Public regulatory and exchange disclosure retrieval for listed Partner issuers only.",
    "non_bypass_rule": "Never bypass login, paywall, CAPTCHA, robots denial, browser integrity check, API-key requirement, rate limit, or source terms.",
    "allowed_actions": [
        "Open public search and issuer pages in an ordinary browser.",
        "Use documented public APIs only with required keys, identification and rate limits.",
        "Download public filing attachments for research and retain URL, publisher, filing date and locator.",
        "Use a low-rate manual workflow when a portal depends on JavaScript or session state.",
    ],
    "prohibited_actions": [
        "Circumvent CAPTCHA, WAF, browser checks, authentication, geographic controls or payment.",
        "Replay private/internal endpoints discovered from authenticated sessions.",
        "Rotate identities or IPs to evade throttling.",
        "Treat an unofficial mirror or search snippet as the regulatory filing of record.",
        "Infer that no filing exists solely from a transient 403/429/5xx response.",
    ],
    "terminal_states": {
        "public_results_available": "Exact issuer and requested document are publicly retrievable; capture the official URL and filing metadata.",
        "source_unavailable_transient": "Official source returned maintenance/5xx/timeout; retry later at low frequency.",
        "rate_limited": "429 or explicit throttle; stop and honor Retry-After/published limits.",
        "js_session_required": "Static request cannot execute required public UI; use an ordinary interactive browser once.",
        "captcha_or_human_challenge": "Human challenge encountered; do not automate or bypass; mark manual review.",
        "access_controlled_login": "Requested material requires account/authority/payment; do not enter or bypass without separate authorization.",
        "identifier_missing": "Required CIK/LEI/stock code/internal issuer identifier is absent; resolve it through a public issuer profile first.",
        "no_exact_issuer_match": "Search completed on the official source but no exact legal entity/security match was found.",
        "no_documents_in_date_range": "Exact issuer found, but no requested document in the bounded period.",
        "issuer_outside_source_jurisdiction": "Issuer is listed elsewhere or has a different home Member State; route to the competent source.",
        "historical_archive_required": "Current portal retention does not cover the period; use the named official legacy archive.",
        "document_link_broken_or_removed": "Search metadata exists but official attachment is unavailable; preserve metadata and escalate.",
        "source_terms_prohibit_automation": "Terms limit automated copying/reuse; stop automation and use compliant manual access.",
        "manual_review_required": "Ambiguous issuer, multiple securities, language, correction, or delisting state requires human review.",
        "future_not_public": "Source exists institutionally but was not open to the public at the cutoff; it cannot satisfy the route.",
    },
    "source_specific_controls": {
        "us_sec_edgar": {"max_requests_per_second": 10, "identified_user_agent_required": True, "respect_retry_after": True},
        "jp_edinet": {"api_key_required_for_api": True, "browser_search_public": True},
        "in_nse_filings": {"initial_public_cookie_may_be_required": True, "bypass_403_forbidden": True},
        "no_newsweb": {"database_reuse_restricted": True, "bulk_republication_forbidden_without_permission": True},
        "eu_esap_future": {"public_at_cutoff": False, "expected_public_by": "2027-07"},
    },
    "minimum_evidence_capture": ["source_id", "official_url", "publisher_or_operator", "filing_or_release_date", "document_type", "issuer_identifier", "locator_or_accession", "retrieved_at", "language", "correction_or_version_status"],
}


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def partner_issuers(snapshot: dict) -> list[dict]:
    partner_ids = {r["target_entity_id"] for r in snapshot["relationships"] if r.get("relation_type") == "partner"}
    counts = Counter(r["target_entity_id"] for r in snapshot["relationships"] if r.get("relation_type") == "partner")
    return sorted(
        [e | {"partner_relationship_count": counts[e["id"]]} for e in snapshot["entities"] if e["id"] in partner_ids and e.get("listing_status") == "listed"],
        key=lambda e: e["id"],
    )


def source_route_url(spec: dict, entity: dict, securities: list[dict]) -> str:
    template = spec.get("query_url_template")
    if not template:
        return spec["entry_url"]
    cik = next((s.get("cik") for s in securities if s.get("cik")), None)
    ticker = next((s.get("ticker") for s in securities if s.get("ticker")), None)
    identifier = cik or ticker or entity["legal_name"]
    return template.format(identifier=quote(str(identifier), safe=""))


def build() -> None:
    raw = SNAPSHOT.read_bytes()
    snapshot = json.loads(raw)
    snapshot_sha = hashlib.sha256(raw).hexdigest()
    source_by_id = {s["source_id"]: s for s in SOURCES}
    issuers = partner_issuers(snapshot)

    routes = []
    for entity in issuers:
        securities = entity.get("securities") or []
        issuer_routes = []
        seen_sources = set()
        for region in entity.get("listing_regions") or []:
            region_securities = [s for s in securities if s.get("listing_region") == region]
            candidate_source_ids = list(REGION_ROUTES.get(region, []))
            if region == "China":
                exchanges = " ".join(s.get("exchange", "") for s in region_securities)
                candidate_source_ids = [
                    sid for sid in candidate_source_ids
                    if sid == "cn_cninfo"
                    or (sid == "cn_sse" and "Shanghai" in exchanges)
                    or (sid == "cn_szse" and "Shenzhen" in exchanges)
                ]
            for rank, source_id in enumerate(candidate_source_ids):
                if source_id in seen_sources:
                    continue
                seen_sources.add(source_id)
                spec = source_by_id[source_id]
                issuer_routes.append({
                    "source_id": source_id,
                    "region": region,
                    "role": "primary" if rank == 0 else "supplementary",
                    "route_url": source_route_url(spec, entity, region_securities or securities),
                    "search_keys": {
                        "legal_name": entity.get("legal_name"),
                        "tickers": sorted({s.get("ticker") for s in region_securities if s.get("ticker")}),
                        "ciks": sorted({s.get("cik") for s in region_securities if s.get("cik")}),
                        "isins": sorted({s.get("isin") for s in region_securities if s.get("isin")}),
                        "exchanges": sorted({s.get("exchange") for s in region_securities if s.get("exchange")}),
                    },
                    "query_recipe": spec["query_recipe"],
                    "success_terminal": "public_results_available",
                    "failure_terminal_precedence": [
                        "identifier_missing", "issuer_outside_source_jurisdiction", "js_session_required",
                        "rate_limited", "captcha_or_human_challenge", "access_controlled_login",
                        "no_exact_issuer_match", "no_documents_in_date_range", "manual_review_required",
                    ],
                })
        routes.append({
            "issuer_id": entity["id"],
            "legal_name": entity.get("legal_name"),
            "display_name": entity.get("display_name"),
            "snapshot_partner_relationship_count": entity["partner_relationship_count"],
            "listing_status": entity.get("listing_status"),
            "listing_regions": entity.get("listing_regions") or [],
            "securities": securities,
            "routes": issuer_routes,
            "route_status": "routed" if issuer_routes else "unrouted_region",
            "snapshot_provenance": {
                "path": "data/snapshot_2026-08-25.json",
                "snapshot_version": snapshot.get("meta", {}).get("snapshot_version"),
                "snapshot_sha256": snapshot_sha,
                "as_of": AS_OF,
            },
        })

    (HERE / "regulator_registry.jsonl").write_text("\n".join(dumps(s) for s in sorted(SOURCES, key=lambda x: x["source_id"])) + "\n")
    (HERE / "issuer_source_routes.jsonl").write_text("\n".join(dumps(r) for r in routes) + "\n")
    (HERE / "access_policy.json").write_text(json.dumps(ACCESS_POLICY, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    build()

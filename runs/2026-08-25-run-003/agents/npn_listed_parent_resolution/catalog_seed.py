#!/usr/bin/env python3
"""Materialize the human-reviewed exact NPN-card to issuer catalog.

The compact tuples below are deliberately explicit.  A name is never normalized
or fuzzy-matched to one of these rows: it must equal the frozen canonical card.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# name, entity_id, display name, legal name, exchange, ticker, Yahoo symbol
DIRECT = [
    ("2CRSi", "two_crsi", "2CRSi", "2CRSi S.A.", "Euronext Paris", "AL2SI", "AL2SI.PA"),
    ("AAEON Technology Inc.", "aaeon", "AAEON", "AAEON Technology Inc.", "Taiwan Stock Exchange", "6579", "6579.TW"),
    ("ADLINK Technology Inc", "adlink", "ADLINK", "ADLINK Technology Inc.", "Taiwan Stock Exchange", "6166", "6166.TW"),
    ("APPLIED CO.,LTD", "applied_japan", "Applied Co.", "Applied Co., Ltd.", "Tokyo Stock Exchange", "3020", "3020.T"),
    ("ASBISс Enterprises PLC", "asbis", "ASBIS", "ASBISc Enterprises Plc", "Warsaw Stock Exchange", "ASB", "ASB.WA"),
    ("AVerMedia", "avermedia", "AVerMedia", "AVerMedia Technologies, Inc.", "Taiwan Stock Exchange", "2417", "2417.TW"),
    ("Accton", "accton", "Accton", "Accton Technology Corporation", "Taiwan Stock Exchange", "2345", "2345.TW"),
    ("Arcadis NV", "arcadis", "Arcadis", "Arcadis N.V.", "Euronext Amsterdam", "ARCAD", "ARCAD.AS"),
    ("Arrow Electronics", "arrow_electronics", "Arrow Electronics", "Arrow Electronics, Inc.", "NYSE", "ARW", "ARW"),
    ("Ateme", "ateme", "Ateme", "Ateme S.A.", "Euronext Paris", "ATEME", "ATEME.PA"),
    ("AtkinsRealis", "atkinsrealis", "AtkinsRéalis", "AtkinsRéalis Group Inc.", "Toronto Stock Exchange", "ATRL", "ATRL.TO"),
    ("Axiomtek", "axiomtek", "Axiomtek", "Axiomtek Co., Ltd.", "Taipei Exchange", "3088", "3088.TWO"),
    ("BIPROGY Inc", "biprogy", "BIPROGY", "BIPROGY Inc.", "Tokyo Stock Exchange", "8056", "8056.T"),
    ("BYD Electronic (International) Company Limited", "byd_electronic", "BYD Electronic", "BYD Electronic (International) Company Limited", "Hong Kong Stock Exchange", "0285", "0285.HK"),
    ("Basler AG", "basler", "Basler", "Basler AG", "Xetra", "BSL", "BSL.DE"),
    ("CANCOM", "cancom", "CANCOM", "CANCOM SE", "Xetra", "COK", "COK.DE"),
    ("Capgemini", "capgemini", "Capgemini", "Capgemini SE", "Euronext Paris", "CAP", "CAP.PA"),
    ("China Greatwall Technology Group Co Ltd", "china_greatwall", "China Greatwall Technology", "China Greatwall Technology Group Co., Ltd.", "Shenzhen Stock Exchange", "000066", "000066.SZ"),
    ("Compal Electronics Inc", "compal", "Compal", "Compal Electronics, Inc.", "Taiwan Stock Exchange", "2324", "2324.TW"),
    ("Dicker Data", "dicker_data", "Dicker Data", "Dicker Data Limited", "Australian Securities Exchange", "DDR", "DDR.AX"),
    ("Digital China Holdings Limited", "digital_china", "Digital China Holdings", "Digital China Holdings Limited", "Hong Kong Stock Exchange", "0861", "0861.HK"),
    ("E2E Networks Ltd", "e2e_networks", "E2E Networks", "E2E Networks Limited", "National Stock Exchange of India", "E2E", "E2E.NS"),
    ("EDOM", "edom", "EDOM Technology", "EDOM Technology Co., Ltd.", "Taiwan Stock Exchange", "3048", "3048.TW"),
    ("EverFocus Electronics Corp", "everfocus", "EverFocus", "EverFocus Electronics Corporation", "Taiwan Stock Exchange", "5484", "5484.TW"),
    ("GIGABYTE Technology Co., Ltd.", "gigabyte_technology", "GIGABYTE", "GIGA-BYTE Technology Co., Ltd.", "Taiwan Stock Exchange", "2376", "2376.TW"),
    ("GS Engineering & Construction Corp", "gs_ec", "GS Engineering & Construction", "GS Engineering & Construction Corporation", "Korea Exchange", "006360", "006360.KS"),
    ("Gorilla Technology Inc", "gorilla_technology", "Gorilla Technology", "Gorilla Technology Group Inc.", "Nasdaq", "GRRR", "GRRR"),
    ("HCL Technologies", "hcltech", "HCLTech", "HCL Technologies Limited", "National Stock Exchange of India", "HCLTECH", "HCLTECH.NS"),
    ("HCLTech", "hcltech", "HCLTech", "HCL Technologies Limited", "National Stock Exchange of India", "HCLTECH", "HCLTECH.NS"),
    ("Huaqin Technology Co., Ltd.,", "huaqin", "Huaqin Technology", "Huaqin Technology Co., Ltd.", "Shanghai Stock Exchange", "603296", "603296.SS"),
    ("IONOS SE", "ionos", "IONOS", "IONOS Group SE", "Xetra", "IOS", "IOS.DE"),
    ("Kontron", "kontron", "Kontron", "Kontron AG", "Xetra", "KTN", "KTN.DE"),
    ("L&T Technology Services", "ltts", "L&T Technology Services", "L&T Technology Services Limited", "National Stock Exchange of India", "LTTS", "LTTS.NS"),
    ("LDLC Group", "ldlc", "LDLC", "Groupe LDLC S.A.", "Euronext Growth Paris", "ALLDL", "ALLDL.PA"),
    ("LG CNS", "lg_cns", "LG CNS", "LG CNS Co., Ltd.", "Korea Exchange", "064400", "064400.KS"),
    ("LTIMindtree", "ltimindtree", "LTIMindtree", "LTIMindtree Limited", "National Stock Exchange of India", "LTM", "LTM.NS"),
    ("Leadtek Research Inc", "leadtek", "Leadtek Research", "Leadtek Research Inc.", "Taiwan Stock Exchange", "2465", "2465.TW"),
    ("MDS Tech Inc", "mds_tech", "MDS Tech", "MDS Tech Inc.", "KOSDAQ", "086960", "086960.KQ"),
    ("Mastek Ltd", "mastek", "Mastek", "Mastek Limited", "National Stock Exchange of India", "MASTEK", "MASTEK.NS"),
    ("Mitsubishi Heavy Industries(MHI) Co Ltd", "mitsubishi_heavy", "Mitsubishi Heavy Industries", "Mitsubishi Heavy Industries, Ltd.", "Tokyo Stock Exchange", "7011", "7011.T"),
    ("NEC Corporation", "nec", "NEC", "NEC Corporation", "Tokyo Stock Exchange", "6701", "6701.T"),
    ("NS Solutions Corporation", "ns_solutions", "NS Solutions", "NS Solutions Corporation", "Tokyo Stock Exchange", "2327", "2327.T"),
    ("NationGate Holdings Berhad", "nationgate", "NationGate", "NationGate Holdings Berhad", "Bursa Malaysia", "0270", "0270.KL"),
    ("Netweb Technologies India Pvt Ltd", "netweb_india", "Netweb Technologies India", "Netweb Technologies India Limited", "National Stock Exchange of India", "NETWEB", "NETWEB.NS"),
    ("NextDC", "nextdc", "NEXTDC", "NEXTDC Limited", "Australian Securities Exchange", "NXT", "NXT.AX"),
    ("OVH", "ovhcloud", "OVHcloud", "OVH Groupe S.A.", "Euronext Paris", "OVH", "OVH.PA"),
    ("Orbbec Inc", "orbbec", "Orbbec", "Orbbec Inc.", "Shanghai Stock Exchange STAR Market", "688322", "688322.SS"),
    ("Otsuka Corporation", "otsuka_corp", "Otsuka Corporation", "Otsuka Corporation", "Tokyo Stock Exchange", "4768", "4768.T"),
    ("Persistent Systems Limited", "persistent_systems", "Persistent Systems", "Persistent Systems Limited", "National Stock Exchange of India", "PERSISTENT", "PERSISTENT.NS"),
    ("Quanta Computer Inc", "quanta", "Quanta Computer", "Quanta Computer Inc.", "Taiwan Stock Exchange", "2382", "2382.TW"),
    ("Rashi Peripherals Pvt Ltd", "rashi_peripherals", "Rashi Peripherals", "Rashi Peripherals Limited", "National Stock Exchange of India", "RPTECH", "RPTECH.NS"),
    ("Reply S.p.A.", "reply", "Reply", "Reply S.p.A.", "Borsa Italiana", "REY", "REY.MI"),
    ("SNet Systems Inc", "snet_systems", "SNet Systems", "SNet Systems Inc.", "KOSDAQ", "038680", "038680.KQ"),
    ("Samsung SDS", "samsung_sds", "Samsung SDS", "Samsung SDS Co., Ltd.", "Korea Exchange", "018260", "018260.KS"),
    ("Sangfor Technologies Inc", "sangfor", "Sangfor Technologies", "Sangfor Technologies Inc.", "Shenzhen Stock Exchange", "300454", "300454.SZ"),
    ("Siili Solutions Oyj", "siili", "Siili Solutions", "Siili Solutions Oyj", "Nasdaq Helsinki", "SIILI", "SIILI.HE"),
    ("SoftBank Corp", "softbank_corp", "SoftBank Corp.", "SoftBank Corp.", "Tokyo Stock Exchange", "9434", "9434.T"),
    ("Softcat Plc", "softcat", "Softcat", "Softcat plc", "London Stock Exchange", "SCT", "SCT.L"),
    ("Sopra Steria Group", "sopra_steria", "Sopra Steria", "Sopra Steria Group S.A.", "Euronext Paris", "SOP", "SOP.PA"),
    ("Swisscom AG", "swisscom", "Swisscom", "Swisscom AG", "SIX Swiss Exchange", "SCMN", "SCMN.SW"),
    ("TSINGHUA TONGFANG CO., LTD.", "tsinghua_tongfang", "Tsinghua Tongfang", "Tsinghua Tongfang Co., Ltd.", "Shanghai Stock Exchange", "600100", "600100.SS"),
    ("TZTEK Technology CO.,Ltd", "tztek", "TZTEK Technology", "TZTEK Technology Co., Ltd.", "Shanghai Stock Exchange STAR Market", "688003", "688003.SS"),
    ("Tata Consultancy Services Limited", "tcs", "Tata Consultancy Services", "Tata Consultancy Services Limited", "National Stock Exchange of India", "TCS", "TCS.NS"),
    ("Tata Elxsi", "tata_elxsi", "Tata Elxsi", "Tata Elxsi Limited", "National Stock Exchange of India", "TATAELXSI", "TATAELXSI.NS"),
    ("Tatung System Technologies Inc", "tatung_system", "Tatung System Technologies", "Tatung System Technologies Inc.", "Taipei Exchange", "8099", "8099.TWO"),
    ("Tech Mahindra Limited", "tech_mahindra", "Tech Mahindra", "Tech Mahindra Limited", "National Stock Exchange of India", "TECHM", "TECHM.NS"),
    ("Thunder Software Technology Co.,Ltd", "thundersoft", "ThunderSoft", "Thunder Software Technology Co., Ltd.", "Shenzhen Stock Exchange", "300496", "300496.SZ"),
    ("Tokyo Electron Device LTD", "tokyo_electron_device", "Tokyo Electron Device", "Tokyo Electron Device Limited", "Tokyo Stock Exchange", "2760", "2760.T"),
    ("Uniquest Corporation", "uniquest", "Uniquest", "Uniquest Corporation", "Korea Exchange", "077500", "077500.KS"),
    ("Worley", "worley", "Worley", "Worley Limited", "Australian Securities Exchange", "WOR", "WOR.AX"),
    ("XIILAB Co Ltd", "xiilab", "XIILAB", "XIILAB Co., Ltd.", "KOSDAQ", "189330", "189330.KQ"),
    ("ZTE corproation", "zte", "ZTE", "ZTE Corporation", "Shenzhen Stock Exchange", "000063", "000063.SZ"),
    ("Zero One Technology Co Ltd", "zero_one_technology", "Zero One Technology", "Zero One Technology Co., Ltd.", "Taiwan Stock Exchange", "3029", "3029.TW"),
]

# name, existing registry entity id.  These are direct issuer/operating-name cards.
UPSTREAM_DIRECT = {
    "F5 Networks": "entity_0518df695de579a3",
    "Infosys Limited": "entity_0f9d3e220c6e69d9",
    "Super Micro Computer Inc": "supermicro",
    "Wipro Limited": "entity_98177a76742ec554",
}

# Parent issuer definitions used by more than one exact card.
ISSUERS = {
    "alibaba": ("entity_448ee47d0990d0c2", "Alibaba Group", "Alibaba Group Holding Limited", "NYSE", "BABA", "BABA"),
    "arrow": ("arrow_electronics", "Arrow Electronics", "Arrow Electronics, Inc.", "NYSE", "ARW", "ARW"),
    "att": ("entity_a0c5e20aaea3f465", "AT&T", "AT&T Inc.", "NYSE", "T", "T"),
    "avnet": ("avnet", "Avnet", "Avnet, Inc.", "Nasdaq", "AVT", "AVT"),
    "bce": ("bce", "BCE", "BCE Inc.", "Toronto Stock Exchange", "BCE", "BCE.TO"),
    "bechtle": ("bechtle", "Bechtle", "Bechtle AG", "Xetra", "BC8", "BC8.DE"),
    "broadcom": ("broadcom", "Broadcom", "Broadcom Inc.", "Nasdaq", "AVGO", "AVGO"),
    "cbre": ("cbre", "CBRE", "CBRE Group, Inc.", "NYSE", "CBRE", "CBRE"),
    "cognizant": ("cognizant", "Cognizant", "Cognizant Technology Solutions Corporation", "Nasdaq", "CTSH", "CTSH"),
    "computacenter": ("computacenter", "Computacenter", "Computacenter plc", "London Stock Exchange", "CCC", "CCC.L"),
    "dell": ("dell", "Dell Technologies", "Dell Technologies Inc.", "NYSE", "DELL", "DELL"),
    "edf": ("edf", "EDF", "Électricité de France S.A.", "Euronext Paris", "EDF", "EDF.PA"),
    "fpt": ("fpt", "FPT", "FPT Corporation", "Ho Chi Minh Stock Exchange", "FPT", "FPT.VN"),
    "hitachi": ("entity_43cff1458d4aab47", "Hitachi", "Hitachi, Ltd.", "Tokyo Stock Exchange", "6501", "6501.T"),
    "hpe": ("hpe", "HPE", "Hewlett Packard Enterprise Company", "NYSE", "HPE", "HPE"),
    "ibm": ("entity_7f4992b527dcdcb3", "IBM", "International Business Machines Corporation", "NYSE", "IBM", "IBM"),
    "ingram": ("ingram_micro", "Ingram Micro", "Ingram Micro Holding Corporation", "NYSE", "INGM", "INGM"),
    "infosys": ("entity_0f9d3e220c6e69d9", "Infosys", "Infosys Limited", "NYSE", "INFY", "INFY"),
    "insight": ("insight_enterprises", "Insight Enterprises", "Insight Enterprises, Inc.", "Nasdaq", "NSIT", "NSIT"),
    "lenovo": ("lenovo_group", "Lenovo", "Lenovo Group Limited", "Hong Kong Stock Exchange", "0992", "0992.HK"),
    "macnica": ("macnica", "Macnica Holdings", "Macnica Holdings, Inc.", "Tokyo Stock Exchange", "3132", "3132.T"),
    "naver": ("naver", "NAVER", "NAVER Corporation", "Korea Exchange", "035420", "035420.KS"),
    "netapp": ("entity_ad2a8ec8038a3da9", "NetApp", "NetApp, Inc.", "Nasdaq", "NTAP", "NTAP"),
    "nebius": ("nebius", "Nebius Group", "Nebius Group N.V.", "Nasdaq", "NBIS", "NBIS"),
    "nec": ("nec", "NEC", "NEC Corporation", "Tokyo Stock Exchange", "6701", "6701.T"),
    "ntt": ("ntt", "NTT", "NTT, Inc.", "Tokyo Stock Exchange", "9432", "9432.T"),
    "okaya_co": ("okaya_co", "Okaya & Co.", "Okaya & Co., Ltd.", "Nagoya Stock Exchange", "7485", None),
    "sify": ("sify", "Sify Technologies", "Sify Technologies Limited", "Nasdaq", "SIFY", "SIFY"),
    "singtel": ("singtel", "Singtel", "Singapore Telecommunications Limited", "Singapore Exchange", "Z74", "Z74.SI"),
    "slb": ("slb", "SLB", "Schlumberger Limited", "NYSE", "SLB", "SLB"),
    "softwareone": ("softwareone", "SoftwareOne", "SoftwareOne Holding AG", "SIX Swiss Exchange", "SWON", "SWON.SW"),
    "td_synnex": ("entity_30f6d340bb3ce3f2", "TD SYNNEX", "TD SYNNEX Corporation", "NYSE", "SNX", "SNX"),
    "teledyne": ("teledyne", "Teledyne Technologies", "Teledyne Technologies Incorporated", "NYSE", "TDY", "TDY"),
    "tencent": ("tencent", "Tencent", "Tencent Holdings Limited", "Hong Kong Stock Exchange", "0700", "0700.HK"),
    "trane": ("entity_509b9323874f2293", "Trane Technologies", "Trane Technologies plc", "NYSE", "TT", "TT"),
    "wsp": ("wsp_global", "WSP Global", "WSP Global Inc.", "Toronto Stock Exchange", "WSP", "WSP.TO"),
    "eplus": ("eplus", "ePlus", "ePlus inc.", "Nasdaq", "PLUS", "PLUS"),
    "accton": ("accton", "Accton", "Accton Technology Corporation", "Taiwan Stock Exchange", "2345", "2345.TW"),
    "atea": ("atea", "Atea", "Atea ASA", "Oslo Bors", "ATEA", "ATEA.OL"),
    "digital_china": ("digital_china", "Digital China Holdings", "Digital China Holdings Limited", "Hong Kong Stock Exchange", "0861", "0861.HK"),
    "dustin": ("dustin", "Dustin Group", "Dustin Group AB", "Nasdaq Stockholm", "DUST", "DUST.ST"),
    "fujitsu": ("fujitsu", "Fujitsu", "Fujitsu Limited", "Tokyo Stock Exchange", "6702", "6702.T"),
    "leadtek": ("leadtek", "Leadtek Research", "Leadtek Research Inc.", "Taiwan Stock Exchange", "2465", "2465.TW"),
    "vstecs": ("vstecs", "VSTECS Holdings", "VSTECS Holdings Limited", "Hong Kong Stock Exchange", "0856", "0856.HK"),
    "unisplendour": ("unisplendour", "Unisplendour", "Unisplendour Corporation Limited", "Shenzhen Stock Exchange", "000938", "000938.SZ"),
    "systex": ("systex", "SYSTEX", "SYSTEX Corporation", "Taiwan Stock Exchange", "6214", "6214.TW"),
    "sumitomo_corp": ("sumitomo_corporation", "Sumitomo Corporation", "Sumitomo Corporation", "Tokyo Stock Exchange", "8053", "8053.T"),
    "pc_partner": ("pc_partner", "PC Partner Group", "PC Partner Group Limited", "Singapore Exchange", "PCT", "PCT.SI"),
    "proact": ("proact", "Proact IT Group", "Proact IT Group AB", "Nasdaq Stockholm", "PACT", "PACT.ST"),
    "ryoyo_ryosan": ("ryoyo_ryosan", "Ryoyo Ryosan Holdings", "Ryoyo Ryosan Holdings, Inc.", "Tokyo Stock Exchange", "167A", "167A.T"),
}

# exact NPN name -> issuer key, resolution_kind, official mapping URL, locator/excerpt
PARENT = [
    ("AT&T Business", "att", "brand_to_parent", "https://about.att.com/pages/corporate-profile", "AT&T", "Corporate profile", "AT&T Business is presented as an AT&T business segment/brand."),
    ("Alibaba Cloud Computing (Beijing) Co Ltd", "alibaba", "subsidiary_to_parent", "https://www.alibabagroup.com/en-US/about-alibaba-businesses-1747707161551974400", "Alibaba Group", "Businesses > Alibaba Cloud", "Alibaba Group identifies Alibaba Cloud as one of its businesses."),
    ("Accton Technology China", "accton", "subsidiary_to_parent", "https://www.accton.com/about-accton/", "Accton Technology", "About Accton", "The China card is a regional operating entity of Accton Technology."),
    ("Atea Sverige AB", "atea", "subsidiary_to_parent", "https://www.atea.com/about-atea/", "Atea ASA", "About Atea", "The Swedish AB is a regional operating subsidiary of Atea ASA."),
    ("Atea A/S", "atea", "subsidiary_to_parent", "https://www.atea.com/contact-us/", "Atea ASA", "Contact us > Denmark", "Atea identifies Atea A/S as its Danish operating subsidiary; the listed issuer is Atea ASA."),
    ("Atea AS", "atea", "subsidiary_to_parent", "https://www.atea.com/contact-us/", "Atea ASA", "Contact us > Norway", "Atea identifies Atea AS as its Norwegian operating subsidiary; the listed issuer is Atea ASA."),
    ("Avnet Integrated", "avnet", "brand_to_parent", "https://www.avnet.com/americas/about-avnet/", "Avnet, Inc.", "About Avnet", "Avnet's corporate site presents Avnet Integrated as part of the Avnet group offering."),
    ("Bell Canada", "bce", "subsidiary_to_parent", "https://www.bce.ca/about-bce", "BCE Inc.", "About BCE", "BCE describes Bell Canada as its principal operating subsidiary."),
    ("CBRE Limited", "cbre", "subsidiary_to_parent", "https://www.cbre.com/about-us", "CBRE Group, Inc.", "About us", "CBRE Limited is a local operating entity of the CBRE group."),
    ("Cognizant Technology Solutions U.S. Corporation", "cognizant", "subsidiary_to_parent", "https://www.cognizant.com/us/en/about-cognizant", "Cognizant", "About Cognizant", "The U.S. operating corporation uses the Cognizant group identity."),
    ("Dell Datacenter", "dell", "brand_to_parent", "https://www.dell.com/en-us/lp/dt/corporate-info", "Dell Technologies", "Corporate information", "Dell Datacenter is an NPN operating/brand card for Dell Technologies."),
    ("Digital China Macao Commercial Offshore Limited", "digital_china", "subsidiary_to_parent", "https://www.digitalchina.com/en/about", "Digital China Holdings", "About us", "The Macao entity is a regional operating subsidiary of Digital China Holdings."),
    ("Dustin A/S", "dustin", "subsidiary_to_parent", "https://www.dustingroup.com/en/about-us", "Dustin Group", "About us", "The Danish A/S is a regional operating subsidiary of Dustin Group."),
    ("Dustin Netherlands BV", "dustin", "subsidiary_to_parent", "https://www.dustingroup.com/en/about-us", "Dustin Group", "About us", "The Netherlands BV is a regional operating subsidiary of Dustin Group."),
    ("FLIR Integrated Imaging Solutions Inc", "teledyne", "subsidiary_to_parent", "https://www.teledyne.com/en-us/news/Pages/Teledyne-Technologies-Completes-Acquisition-of-FLIR-Systems.aspx", "Teledyne Technologies", "Acquisition announcement", "Teledyne announced completion of its acquisition of FLIR Systems."),
    ("FSAS Technologies SL", "fujitsu", "subsidiary_to_parent", "https://www.fujitsu.com/global/about/corporate/subsidiaries/", "Fujitsu", "Group companies", "FSAS Technologies is identified within the Fujitsu corporate group."),
    ("HPE | Hewlett Packard Enterprise", "hpe", "direct_issuer", "https://investors.hpe.com/", "Hewlett Packard Enterprise", "Investor relations", "HPE is the issuer's operating brand."),
    ("Infosys Limited - NALA", "infosys", "subsidiary_to_parent", "https://www.infosys.com/about.html", "Infosys", "About Infosys", "NALA is a regional Infosys partner-network card."),
    ("Ingram Micro Inc", "ingram", "subsidiary_to_parent", "https://www.sec.gov/Archives/edgar/data/1897762/000162828026013588/exhibit211-subsidiariesoft.htm", "Ingram Micro Holding Corporation / U.S. SEC", "Exhibit 21.1 subsidiaries table", "Ingram Micro Inc. is a wholly owned subsidiary of the listed Ingram Micro Holding Corporation."),
    ("Lenovo DCG", "lenovo", "brand_to_parent", "https://investor.lenovo.com/en/ir/stockinfo.php", "Lenovo Group", "Stock information", "Lenovo DCG is the data-center-group brand of Lenovo Group."),
    ("Leadtek (Shanghai) Research Inc", "leadtek", "subsidiary_to_parent", "https://www.leadtek.com/eng/about/contact/", "Leadtek Research", "Global locations", "The Shanghai entity is a regional Leadtek operating company."),
    ("Macnica Inc", "macnica", "subsidiary_to_parent", "https://www.daiwair.co.jp/td_download.cgi?c=3132&i=3070722", "Macnica Holdings", "Corporate disclosure: wholly owned subsidiary", "Macnica Inc. is a wholly owned operating subsidiary of listed Macnica Holdings."),
    ("NAVER CLOUD Corp.", "naver", "subsidiary_to_parent", "https://www.navercorp.com/en/company/affiliates", "NAVER Corporation", "Affiliates", "NAVER corporate materials identify NAVER Cloud as an affiliate/subsidiary."),
    ("NCS PTE. LTD", "singtel", "subsidiary_to_parent", "https://www.singtel.com/about-us/company/ncs", "Singtel", "Group companies > NCS", "Singtel identifies NCS as a group company."),
    ("Nebius B.V.", "nebius", "subsidiary_to_parent", "https://www.sec.gov/Archives/edgar/data/1513845/000110465926052948/nbis-20251231x20f.htm", "Nebius Group N.V. / U.S. SEC", "History and Development / Organizational Structure", "Nebius Group N.V. is the Nasdaq-listed holding company and Nebius B.V. is its principal operating subsidiary."),
    ("NEC Deutschland Gmbh", "nec", "subsidiary_to_parent", "https://www.nec.com/en/global/about/group/", "NEC", "Global NEC group", "The German GmbH is a regional operating company of NEC Corporation."),
    ("NTT DATA JAPAN CORPORATION", "ntt", "subsidiary_to_parent", "https://group.ntt/en/group/", "NTT", "Group companies", "NTT DATA Japan is within the listed NTT group at the research cutoff."),
    ("NTT DOCOMO BUSINESS, INC.", "ntt", "subsidiary_to_parent", "https://group.ntt/en/group/", "NTT", "Group companies", "NTT DOCOMO BUSINESS is within the listed NTT group."),
    ("NTT Data Group Corporation", "ntt", "subsidiary_to_parent", "https://group.ntt/en/group/", "NTT", "Group companies", "NTT DATA Group became a wholly owned NTT group company before the research cutoff."),
    ("NTTPC Communications, Inc.", "ntt", "subsidiary_to_parent", "https://group.ntt/en/group/", "NTT", "Group companies", "NTTPC Communications is within the listed NTT group."),
    ("Okaya Electronics Corp.", "okaya_co", "subsidiary_to_parent", "https://www.okayaelec.co.jp/en/company/outline/", "Okaya Electric Industries", "Company outline > Shareholder", "Okaya Electric Industries identifies Okaya & Co., Ltd. as its 100% shareholder; the NPN card is not the historical 6926 issuer."),
    ("PC Partner Technology Pte", "pc_partner", "subsidiary_to_parent", "https://www.pcpartner.com/attachment/ac/1731423968OFmxQ.pdf", "PC Partner Group", "SGX introductory document, Appendix F", "PC Partner Technology Pte Ltd is a wholly owned subsidiary of listed PC Partner Group Limited."),
    ("Proact IT Sweden", "proact", "subsidiary_to_parent", "https://www.proact.eu/wp-content/uploads/2025/04/Annual-Sustainability-report-2024-Proact-IT-Group.pdf", "Proact IT Group", "Annual report Note 17", "Proact IT Sweden AB is a wholly owned subsidiary of Proact IT Group AB."),
    ("Ryoyo Ryosan", "ryoyo_ryosan", "subsidiary_to_parent", "https://www.rr-hds.co.jp/company/profile/", "Ryoyo Ryosan Holdings", "Company profile / group structure effective 2026-04-01", "Ryoyo Ryosan Inc. is the operating company under listed Ryoyo Ryosan Holdings Inc."),
    ("New H3C Information Technologies Co Ltd", "unisplendour", "subsidiary_to_parent", "https://www.unigroup.com.cn/en/business/h3c", "Tsinghua Unigroup / Unisplendour", "Business > H3C", "H3C is controlled through listed Unisplendour; endpoint substitution is conservative and inferred."),
    ("Schlumberger Technology Corporation", "slb", "subsidiary_to_parent", "https://www.slb.com/about", "SLB", "About SLB", "Schlumberger Technology Corporation is an operating entity of listed SLB."),
    ("Sify Technologies NA Corp", "sify", "subsidiary_to_parent", "https://www.sifytechnologies.com/investors/", "Sify Technologies", "Investor relations", "The North America corporation is an operating subsidiary of Sify Technologies Limited."),
    ("SCSK Corporation", "sumitomo_corp", "subsidiary_to_parent", "https://www.sumitomocorp.com/-/media/Files/hq/news/release/2025/20630/20630_en.pdf", "Sumitomo Corporation", "Tender offer result / ownership structure", "Sumitomo's transaction made SCSK a wholly owned subsidiary; 9719 is historical at the cutoff."),
    ("SoftwareONE Deutschland GmbH", "softwareone", "subsidiary_to_parent", "https://www.softwareone.com/en/about-us", "SoftwareOne", "About us", "The German GmbH is an operating subsidiary of SoftwareOne Holding AG."),
    ("Tencent Cloud Computing (Beijing) Co Ltd", "tencent", "subsidiary_to_parent", "https://www.tencent.com/en-us/business.html", "Tencent", "Business > Cloud and Smart Industries", "Tencent presents cloud as a group business."),
    ("Trane Technologies LLC", "trane", "subsidiary_to_parent", "https://investors.tranetechnologies.com/", "Trane Technologies", "Investor relations", "The LLC card maps to listed Trane Technologies plc."),
    ("VMware Inc", "broadcom", "brand_to_parent", "https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-completes-acquisition-vmware", "Broadcom Inc.", "Acquisition completion announcement", "Broadcom announced completion of its acquisition of VMware."),
    ("WSP USA Inc", "wsp", "subsidiary_to_parent", "https://www.wsp.com/en-us/who-we-are", "WSP Global", "Who we are", "WSP USA is the U.S. operating subsidiary of WSP Global."),
    ("Systex Information (HK) Ltd", "systex", "subsidiary_to_parent", "https://www.systex.com/en/about/global", "SYSTEX", "Global presence", "The Hong Kong legal entity is part of SYSTEX Corporation."),
    ("Unisplendour Xiaotong (Hong Kong) Limited", "unisplendour", "subsidiary_to_parent", "https://www.unisplendour.com/en/about", "Unisplendour", "About Unisplendour", "The Hong Kong legal entity is part of Unisplendour."),
    ("Unisplendour Xiaotong Technology Co Ltd", "unisplendour", "subsidiary_to_parent", "https://www.unisplendour.com/en/about", "Unisplendour", "About Unisplendour", "The named legal entity is part of Unisplendour."),
    ("VST ECS (Thailand) Co Ltd", "vstecs", "subsidiary_to_parent", "https://www.vstecs.com/en/about-us", "VSTECS Holdings", "About us", "The Thailand entity is a regional subsidiary of VSTECS Holdings."),
    ("VSTECS (Singapore) Pte Ltd", "vstecs", "subsidiary_to_parent", "https://www.vstecs.com/en/about-us", "VSTECS Holdings", "About us", "The Singapore entity is a regional subsidiary of VSTECS Holdings."),
    ("VSTECS Phils Inc", "vstecs", "subsidiary_to_parent", "https://www.vstecs.com/en/about-us", "VSTECS Holdings", "About us", "The Philippines entity is a regional subsidiary of VSTECS Holdings."),
    ("eInfochips", "arrow", "brand_to_parent", "https://www.arrow.com/company/einfochips", "Arrow Electronics", "eInfochips company page", "Arrow identifies eInfochips as an Arrow company."),
    ("ePlusTechnology", "eplus", "brand_to_parent", "https://www.eplus.com/about-us", "ePlus", "About us", "ePlus Technology is the operating brand/subsidiary of ePlus inc."),
]

for n in ["Arrow AGC EMEA", "Arrow AIS EMEA", "Arrow Asia Pac Limited", "Arrow ECS EMEA", "Arrow Electronics NALA", "Arrow Electronics Taiwan Limited (AET)"]:
    PARENT.append((n, "arrow", "subsidiary_to_parent", "https://investor.arrow.com/company-information", "Arrow Electronics", "Company information", "The regional Arrow card is an operating unit of Arrow Electronics, Inc."))
for n in ["Bechtle France", "Bechtle Germany", "Bechtle Logistics & Service AG", "Bechtle direct BV"]:
    PARENT.append((n, "bechtle", "subsidiary_to_parent", "https://www.bechtle.com/de-en/about-bechtle/company", "Bechtle AG", "About Bechtle > Company", "The named regional/legal entity is part of the Bechtle group."))
for n in ["Computacenter BV", "Computacenter AG & Co oHG", "Computacenter United States Inc."]:
    PARENT.append((n, "computacenter", "subsidiary_to_parent", "https://www.computacenter.com/who-we-are", "Computacenter plc", "Who we are", "The regional legal entity is part of the Computacenter group."))
for n in ["FPT Japan Holdings", "FPT Singapore", "FPT Smart Cloud", "FPT Software Europe SARL", "FPT USA Corporation"]:
    PARENT.append((n, "fpt", "subsidiary_to_parent", "https://fpt.com/en/about-us", "FPT Corporation", "About FPT", "The named regional/business entity is part of FPT Corporation."))
for n in ["Hitachi Academy Co Ltd", "Hitachi Digital", "Hitachi Vantara LLC"]:
    PARENT.append((n, "hitachi", "subsidiary_to_parent", "https://www.hitachi.com/en/about/", "Hitachi, Ltd.", "About Hitachi", "The named operating entity uses Hitachi group identity and is mapped to Hitachi, Ltd."))
for n in ["IBM Cloud and Research", "IBM Consulting", "IBM Data & AI", "IBM Watson & Cloud"]:
    PARENT.append((n, "ibm", "brand_to_parent", "https://www.ibm.com/investor", "IBM", "Investor relations", "The card is an IBM business/division brand, not a separate issuer."))
for n in ["Ingram Micro (Thailand) Ltd", "Ingram Micro Asia Ltd - Singapore", "Ingram Micro India Pvt Ltd", "Ingram Micro Indonesia", "Ingram Micro International Trading Limited", "Ingram Micro Malaysia", "Ingram Micro Pty Ltd ACN 112 487 996", "Ingram Micro Trading (Shanghai) Co Ltd"]:
    PARENT.append((n, "ingram", "subsidiary_to_parent", "https://www.ingrammicro.com/en-us/about-us", "Ingram Micro", "About us", "The regional legal entity is part of Ingram Micro."))
for n in ["Insight Canada Inc", "Insight Direct USA Inc"]:
    PARENT.append((n, "insight", "subsidiary_to_parent", "https://investor.insight.com/company-information", "Insight Enterprises", "Company information", "The regional operating entity is part of Insight Enterprises."))
for n in ["Macnica Galaxy Inc"]:
    PARENT.append((n, "macnica", "subsidiary_to_parent", "https://holdings.macnica.co.jp/en/company/group.html", "Macnica Holdings", "Group companies", "Macnica identifies the named business as a group company."))
for n in ["NetApp Austria", "NetApp USA"]:
    PARENT.append((n, "netapp", "subsidiary_to_parent", "https://investors.netapp.com/", "NetApp", "Investor relations", "The regional card is an operating entity of NetApp, Inc."))
for n in ["TD Synnex EMEA", "TD Synnex LATAM", "PT Tech Data Advanced Solutions", "Tech Data Advanced Private Limited", "Tech Data Advanced Solutions (ANZ)", "Tech Data Advanced Solutions (Singa", "Tech Data Advanced Solutions (Singapore) Pte Ltd", "Tech Data Advanced Solutions (Vietnam)"]:
    PARENT.append((n, "td_synnex", "subsidiary_to_parent", "https://www.tdsynnex.com/na/us/about-us/", "TD SYNNEX", "About us", "TD SYNNEX was formed through the merger with Tech Data; the named regional card is within the group."))


def issuer(key):
    eid, display, legal, exchange, ticker, symbol = ISSUERS[key]
    return {"entity_id": eid, "display_name": display, "legal_name": legal, "exchange": exchange, "ticker": ticker, "yahoo_symbol": symbol}


rows = []
for name, eid, display, legal, exchange, ticker, symbol in DIRECT:
    rows.append({"name": name, "resolution_kind": "direct_issuer", "issuer": {"entity_id": eid, "display_name": display, "legal_name": legal, "exchange": exchange, "ticker": ticker, "yahoo_symbol": symbol}, "review_reason": "Exact frozen NPN card identity was manually reviewed against the frozen public-market listing metadata; no fuzzy matching."})
for name, eid in UPSTREAM_DIRECT.items():
    rows.append({"name": name, "resolution_kind": "direct_issuer", "issuer": {"entity_id": eid, "upstream_entity_id": eid}, "review_reason": "Exact operating/issuer identity manually reviewed against an already-validated entity-registry issuer."})
for name, key, kind, url, publisher, locator, excerpt in PARENT:
    rows.append({"name": name, "resolution_kind": kind, "issuer": issuer(key), "mapping_source": {"url": url, "publisher": publisher, "locator": locator, "excerpt": excerpt}, "review_reason": "Exact frozen card was manually reviewed as a brand/regional/legal-unit identity of the named listed parent; endpoint substitution remains an inference."})

# The NTT ownership event and delisting are both required to justify substituting
# active listed NTT (9432) for any NTT DATA endpoint at the 2026-08-25 cutoff.
for row in rows:
    if row["name"] in {"NTT DATA JAPAN CORPORATION", "NTT Data Group Corporation"}:
        row["mapping_sources"] = [
            row.pop("mapping_source"),
            {"url": "https://group.ntt/en/newsrelease/2025/05/08/250508b.html", "publisher": "NTT", "locator": "Tender offer / wholly owned subsidiary announcement", "excerpt": "NTT announced the transaction to make NTT DATA Group a wholly owned subsidiary."},
            {"url": "https://www.jpx.co.jp/english/news/1023/20250829-12.html", "publisher": "Japan Exchange Group", "locator": "Delisting schedule for NTT DATA GROUP CORPORATION", "excerpt": "JPX documents the 2025-09-26 delisting of security code 9613."},
        ]
    if row["name"] == "SCSK Corporation":
        row["mapping_sources"] = [
            row.pop("mapping_source"),
            {"url": "https://www.jpx.co.jp/english/news/1023/20260209-11.html", "publisher": "Japan Exchange Group", "locator": "Delisting decision and date for SCSK Corporation", "excerpt": "JPX records SCSK's 2026-03-12 delisting from the TSE Prime Market."},
        ]
    if row["name"] == "Okaya Electronics Corp.":
        row["issuer"]["listing_source"] = {"url": "https://www.okaya.co.jp/en/corporate/profile/", "publisher": "Okaya & Co., Ltd.", "locator": "Corporate profile > Stock exchange listing / securities code", "excerpt": "Okaya & Co. identifies securities code 7485 and its Nagoya Stock Exchange listing."}

REJECTIONS = [
    {"name": "EXAION (EDF GROUP)", "decision": "rejected_parent_private_or_delisted_at_cutoff", "reason": "EDF was delisted from Euronext Paris on 2023-06-08 and was wholly owned by the French State; EXAION therefore has no active listed EDF endpoint at the 2026-08-25 cutoff.", "sources": [
        {"url": "https://www.edf.fr/en/the-edf-group/dedicated-sections/investors-shareholders/the-edf-share/delisting-of-edf-shares", "publisher": "EDF", "published_at": "2023-06-08", "locator": "Delisting of EDF shares", "excerpt": "EDF states that its shares were delisted and the French State held all share capital and voting rights."}
    ]}
]

rows.sort(key=lambda x: x["name"].casefold())
(ROOT / "reviewed_mappings.json").write_text(json.dumps({"research_cutoff": "2026-08-25", "matching_policy": "exact_frozen_name_only_human_reviewed", "mappings": rows, "rejections": REJECTIONS}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote {len(rows)} reviewed mappings")

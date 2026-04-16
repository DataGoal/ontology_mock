"""
CPG Domain Reference Data
Provides realistic reference data for Consumer Packaged Goods industry.
Modelled after companies like Kimberly-Clark, P&G, Unilever.
"""

# ── Product Catalog ────────────────────────────────────────────────────────

CPG_PRODUCT_CATALOG = [
    # Baby & Child Care
    {"category": "Baby & Child Care", "sub_category": "Diapers",            "brand": "Huggies",    "product_name": "Huggies Little Snugglers Newborn Diapers",     "sku_prefix": "HUG-LN", "weight_kg": 2.5,  "packaging": "Case"},
    {"category": "Baby & Child Care", "sub_category": "Diapers",            "brand": "Huggies",    "product_name": "Huggies Little Movers Size 3 Diapers",         "sku_prefix": "HUG-LM3","weight_kg": 3.2,  "packaging": "Case"},
    {"category": "Baby & Child Care", "sub_category": "Diapers",            "brand": "Huggies",    "product_name": "Huggies Snug & Dry Size 4 Diapers",            "sku_prefix": "HUG-SD4","weight_kg": 3.8,  "packaging": "Case"},
    {"category": "Baby & Child Care", "sub_category": "Training Pants",     "brand": "Pull-Ups",   "product_name": "Pull-Ups Learning Designs Boys 2T-3T",         "sku_prefix": "PUP-LB2","weight_kg": 2.1,  "packaging": "Case"},
    {"category": "Baby & Child Care", "sub_category": "Training Pants",     "brand": "Pull-Ups",   "product_name": "Pull-Ups Learning Designs Girls 4T-5T",        "sku_prefix": "PUP-LG4","weight_kg": 2.4,  "packaging": "Case"},
    {"category": "Baby & Child Care", "sub_category": "Overnight Protection","brand": "GoodNites",  "product_name": "GoodNites Bedtime Pants Boys L/XL",            "sku_prefix": "GNT-BLX","weight_kg": 1.8,  "packaging": "Case"},
    {"category": "Baby & Child Care", "sub_category": "Overnight Protection","brand": "GoodNites",  "product_name": "GoodNites Bedtime Pants Girls S/M",            "sku_prefix": "GNT-GSM","weight_kg": 1.6,  "packaging": "Case"},
    {"category": "Baby & Child Care", "sub_category": "Baby Wipes",         "brand": "Huggies",    "product_name": "Huggies Natural Care Fragrance Free Baby Wipes","sku_prefix": "HUG-WNF","weight_kg": 0.9,  "packaging": "Bag"},
    {"category": "Baby & Child Care", "sub_category": "Baby Wipes",         "brand": "Huggies",    "product_name": "Huggies Simply Clean Baby Wipes 648 ct",       "sku_prefix": "HUG-WSC","weight_kg": 1.2,  "packaging": "Bag"},

    # Personal Care
    {"category": "Personal Care",     "sub_category": "Feminine Care",      "brand": "U by Kotex", "product_name": "U by Kotex Fitness Ultra Thin Pads",           "sku_prefix": "KTX-FIT","weight_kg": 0.35, "packaging": "Box"},
    {"category": "Personal Care",     "sub_category": "Feminine Care",      "brand": "U by Kotex", "product_name": "U by Kotex Security Tampons Regular",          "sku_prefix": "KTX-STR","weight_kg": 0.18, "packaging": "Box"},
    {"category": "Personal Care",     "sub_category": "Feminine Care",      "brand": "U by Kotex", "product_name": "Kotex AllNighter Overnight Pads",              "sku_prefix": "KTX-AON","weight_kg": 0.42, "packaging": "Box"},
    {"category": "Personal Care",     "sub_category": "Adult Incontinence", "brand": "Depend",     "product_name": "Depend FIT-FLEX Underwear Men L/XL",           "sku_prefix": "DEP-FMX","weight_kg": 1.60, "packaging": "Case"},
    {"category": "Personal Care",     "sub_category": "Adult Incontinence", "brand": "Depend",     "product_name": "Depend Real Fit Underwear Women M/L",          "sku_prefix": "DEP-RFW","weight_kg": 1.40, "packaging": "Case"},
    {"category": "Personal Care",     "sub_category": "Adult Incontinence", "brand": "Poise",      "product_name": "Poise Long Pads Maximum Absorbency",           "sku_prefix": "POI-LPM","weight_kg": 0.55, "packaging": "Box"},
    {"category": "Personal Care",     "sub_category": "Adult Incontinence", "brand": "Poise",      "product_name": "Poise Ultra Thin Pads Regular Length",         "sku_prefix": "POI-UTP","weight_kg": 0.38, "packaging": "Box"},

    # Family Care – Tissue & Towels
    {"category": "Family Care",       "sub_category": "Facial Tissue",      "brand": "Kleenex",    "product_name": "Kleenex Trusted Care Facial Tissue 6-Box",     "sku_prefix": "KLN-TC6","weight_kg": 1.20, "packaging": "Shipper"},
    {"category": "Family Care",       "sub_category": "Facial Tissue",      "brand": "Kleenex",    "product_name": "Kleenex Ultra Soft Facial Tissue 3-Ply",       "sku_prefix": "KLN-US3","weight_kg": 0.85, "packaging": "Box"},
    {"category": "Family Care",       "sub_category": "Facial Tissue",      "brand": "Kleenex",    "product_name": "Kleenex On-The-Go Pocket Packs 8-Pack",        "sku_prefix": "KLN-OTG","weight_kg": 0.22, "packaging": "Bag"},
    {"category": "Family Care",       "sub_category": "Toilet Paper",       "brand": "Cottonelle", "product_name": "Cottonelle Ultra CleanCare Toilet Paper 36 Mega","sku_prefix": "COT-UC3","weight_kg": 4.50, "packaging": "Case"},
    {"category": "Family Care",       "sub_category": "Toilet Paper",       "brand": "Cottonelle", "product_name": "Cottonelle Ultra ComfortCare 9 Mega Rolls",    "sku_prefix": "COT-CC9","weight_kg": 1.80, "packaging": "Shrink Wrap"},
    {"category": "Family Care",       "sub_category": "Toilet Paper",       "brand": "Scott",      "product_name": "Scott 1000 Toilet Paper 20-Roll",              "sku_prefix": "SCT-100","weight_kg": 2.10, "packaging": "Shrink Wrap"},
    {"category": "Family Care",       "sub_category": "Paper Towels",       "brand": "Scott",      "product_name": "Scott Choose-A-Sheet Paper Towels 6 Big Rolls","sku_prefix": "SCT-CAS","weight_kg": 1.65, "packaging": "Shrink Wrap"},
    {"category": "Family Care",       "sub_category": "Paper Towels",       "brand": "Viva",       "product_name": "Viva Signature Cloth Paper Towels 6 Big Rolls","sku_prefix": "VIV-SCB","weight_kg": 1.50, "packaging": "Shrink Wrap"},
    {"category": "Family Care",       "sub_category": "Paper Towels",       "brand": "Viva",       "product_name": "Viva Multi-Surface Paper Towels 8-Pack",       "sku_prefix": "VIV-MSP","weight_kg": 2.00, "packaging": "Shrink Wrap"},

    # Professional / B2B
    {"category": "Professional",      "sub_category": "Industrial Wipes",   "brand": "WypAll",     "product_name": "WypAll L40 Wipers 18x18 in White",            "sku_prefix": "WYP-L40","weight_kg": 5.00, "packaging": "Carton"},
    {"category": "Professional",      "sub_category": "Industrial Wipes",   "brand": "WypAll",     "product_name": "WypAll X80 Wipers Blue Jumbo Roll",            "sku_prefix": "WYP-X80","weight_kg": 8.50, "packaging": "Carton"},
    {"category": "Professional",      "sub_category": "Industrial Wipes",   "brand": "WypAll",     "product_name": "WypAll X60 Cloths 12x23 Flat Sheet",           "sku_prefix": "WYP-X60","weight_kg": 4.20, "packaging": "Carton"},
    {"category": "Professional",      "sub_category": "Facility Tissue",    "brand": "Kleenex Pro","product_name": "Kleenex Professional Facial Tissue for Business","sku_prefix": "KLP-FTB","weight_kg": 3.00, "packaging": "Case"},
    {"category": "Professional",      "sub_category": "Facility Tissue",    "brand": "Scott Pro",  "product_name": "Scott Pro Hard Roll Paper Towels 1150 ft",     "sku_prefix": "SCP-HR1","weight_kg": 6.00, "packaging": "Case"},
    {"category": "Professional",      "sub_category": "Facility Tissue",    "brand": "Scott Pro",  "product_name": "Scott Pro Coreless Paper Towels 6 Rolls",      "sku_prefix": "SCP-CR6","weight_kg": 4.80, "packaging": "Case"},

    # Health & Hygiene
    {"category": "Health & Hygiene",  "sub_category": "Disinfecting Wipes", "brand": "Kleenex",    "product_name": "Kleenex Disinfecting Wipes Bleach-Free 75ct",  "sku_prefix": "KLN-DW7","weight_kg": 0.65, "packaging": "Canister"},
    {"category": "Health & Hygiene",  "sub_category": "Hand & Face Wipes",  "brand": "Kleenex",    "product_name": "Kleenex Wet Wipes Fresh 56ct",                 "sku_prefix": "KLN-WW5","weight_kg": 0.40, "packaging": "Bag"},
]

# ── Vendor Reference Data ──────────────────────────────────────────────────

VENDOR_DATA = [
    # Raw Material Suppliers
    {"name": "Cellu-Tissue Holdings LLC",       "type": "Raw Material",         "country": "United States",  "region": "North America"},
    {"name": "Resolute Forest Products",         "type": "Raw Material",         "country": "Canada",         "region": "North America"},
    {"name": "Georgia-Pacific Pulp & Paper",     "type": "Raw Material",         "country": "United States",  "region": "North America"},
    {"name": "Arauco North America Inc",         "type": "Raw Material",         "country": "United States",  "region": "North America"},
    {"name": "Suzano SA",                        "type": "Raw Material",         "country": "Brazil",         "region": "Latin America"},
    {"name": "Fibria Celulose SA",               "type": "Raw Material",         "country": "Brazil",         "region": "Latin America"},
    {"name": "UPM-Kymmene Corporation",          "type": "Raw Material",         "country": "Finland",        "region": "EMEA"},
    {"name": "Sappi Southern Africa",            "type": "Raw Material",         "country": "South Africa",   "region": "EMEA"},
    {"name": "Asia Pulp & Paper Group",          "type": "Raw Material",         "country": "Indonesia",      "region": "APAC"},
    {"name": "Nine Dragons Paper Holdings",      "type": "Raw Material",         "country": "China",          "region": "APAC"},
    # Packaging Suppliers
    {"name": "Sealed Air Corporation",           "type": "Packaging",            "country": "United States",  "region": "North America"},
    {"name": "Berry Global Group Inc",           "type": "Packaging",            "country": "United States",  "region": "North America"},
    {"name": "Amcor plc",                        "type": "Packaging",            "country": "Australia",      "region": "APAC"},
    {"name": "DS Smith Packaging",               "type": "Packaging",            "country": "United Kingdom", "region": "EMEA"},
    {"name": "Smurfit Kappa Group",              "type": "Packaging",            "country": "Ireland",        "region": "EMEA"},
    {"name": "Sonoco Products Company",          "type": "Packaging",            "country": "United States",  "region": "North America"},
    {"name": "Huhtamaki Oyj",                    "type": "Packaging",            "country": "Finland",        "region": "EMEA"},
    # Chemical / Superabsorbent Suppliers
    {"name": "BASF SE Personal Care",            "type": "Chemical Supplier",    "country": "Germany",        "region": "EMEA"},
    {"name": "Evonik Industries AG",             "type": "Chemical Supplier",    "country": "Germany",        "region": "EMEA"},
    {"name": "Nippon Shokubai Co Ltd",           "type": "Chemical Supplier",    "country": "Japan",          "region": "APAC"},
    {"name": "Sumitomo Seika Chemicals",         "type": "Chemical Supplier",    "country": "Japan",          "region": "APAC"},
    # Contract Manufacturers / Co-packers
    {"name": "Flint Group Contract Manufacturing","type": "Contract Manufacturer","country": "United States",  "region": "North America"},
    {"name": "Prolamina Corporation",            "type": "Contract Manufacturer","country": "United States",  "region": "North America"},
    {"name": "PDC BioTech Ltd",                  "type": "Contract Manufacturer","country": "Mexico",         "region": "Latin America"},
    {"name": "Alpack Empresas Plasticas",        "type": "Contract Manufacturer","country": "Chile",          "region": "Latin America"},
    # 3PL / Logistics
    {"name": "XPO Logistics Supply Chain",       "type": "3PL",                  "country": "United States",  "region": "North America"},
    {"name": "DHL Supply Chain Americas",        "type": "3PL",                  "country": "United States",  "region": "North America"},
    {"name": "CEVA Logistics",                   "type": "3PL",                  "country": "Switzerland",    "region": "EMEA"},
    {"name": "Kuehne+Nagel International AG",    "type": "3PL",                  "country": "Switzerland",    "region": "EMEA"},
    {"name": "Nippon Express Co Ltd",            "type": "3PL",                  "country": "Japan",          "region": "APAC"},
]

# ── Plant Reference Data ───────────────────────────────────────────────────

PLANT_DATA = [
    {"name": "Neenah Converting Plant",       "code": "PLT-NEW-01", "country": "United States", "region": "North America", "type": "Converting",     "capacity": 180000},
    {"name": "Memphis Diaper Facility",       "code": "PLT-MEM-01", "country": "United States", "region": "North America", "type": "Assembly",       "capacity": 220000},
    {"name": "Ogden Manufacturing Center",    "code": "PLT-OGD-01", "country": "United States", "region": "North America", "type": "Packaging",      "capacity": 95000},
    {"name": "Chester Tissue Mill",           "code": "PLT-CHE-01", "country": "United States", "region": "North America", "type": "Converting",     "capacity": 150000},
    {"name": "Paris Texas Plant",             "code": "PLT-PTX-01", "country": "United States", "region": "North America", "type": "Nonwoven Mfg",   "capacity": 130000},
    {"name": "Fullerton California Plant",    "code": "PLT-FUL-01", "country": "United States", "region": "North America", "type": "Packaging",      "capacity": 75000},
    {"name": "Barrie Ontario Facility",       "code": "PLT-BAR-CA", "country": "Canada",        "region": "North America", "type": "Converting",     "capacity": 90000},
    {"name": "Northampton UK Mill",           "code": "PLT-NTH-UK", "country": "United Kingdom","region": "EMEA",          "type": "Nonwoven Mfg",   "capacity": 110000},
    {"name": "Koblenz Germany Facility",      "code": "PLT-KOB-DE", "country": "Germany",       "region": "EMEA",          "type": "Assembly",       "capacity": 125000},
    {"name": "Hof am Regen Germany Plant",    "code": "PLT-HOF-DE", "country": "Germany",       "region": "EMEA",          "type": "Converting",     "capacity": 100000},
    {"name": "Jarcelona Spain Plant",         "code": "PLT-BAR-ES", "country": "Spain",         "region": "EMEA",          "type": "Packaging",      "capacity": 85000},
    {"name": "Seoul Korea Facility",          "code": "PLT-SEO-KR", "country": "South Korea",   "region": "APAC",          "type": "Assembly",       "capacity": 140000},
    {"name": "Petaling Jaya Malaysia Plant",  "code": "PLT-PJY-MY", "country": "Malaysia",      "region": "APAC",          "type": "Converting",     "capacity": 105000},
    {"name": "Guangzhou China Facility",      "code": "PLT-GZH-CN", "country": "China",         "region": "APAC",          "type": "Assembly",       "capacity": 195000},
    {"name": "Monterrey Mexico Plant",        "code": "PLT-MTY-MX", "country": "Mexico",        "region": "Latin America", "type": "Packaging",      "capacity": 88000},
    {"name": "São Paulo Brazil Facility",     "code": "PLT-SAO-BR", "country": "Brazil",        "region": "Latin America", "type": "Assembly",       "capacity": 160000},
]

# ── Warehouse Reference Data ───────────────────────────────────────────────

WAREHOUSE_DATA = [
    {"name": "Chicago Midwest DC",           "code": "WH-CHI-01", "type": "Finished Goods DC", "country": "United States", "region": "North America", "capacity": 800000},
    {"name": "Dallas Southwest DC",          "code": "WH-DAL-01", "type": "Finished Goods DC", "country": "United States", "region": "North America", "capacity": 650000},
    {"name": "Atlanta Southeast DC",         "code": "WH-ATL-01", "type": "Finished Goods DC", "country": "United States", "region": "North America", "capacity": 580000},
    {"name": "Los Angeles West Coast DC",    "code": "WH-LAX-01", "type": "Finished Goods DC", "country": "United States", "region": "North America", "capacity": 720000},
    {"name": "New Jersey Northeast DC",      "code": "WH-NJE-01", "type": "Finished Goods DC", "country": "United States", "region": "North America", "capacity": 900000},
    {"name": "Memphis Raw Materials Store",  "code": "WH-MEM-RM", "type": "Raw Materials",     "country": "United States", "region": "North America", "capacity": 250000},
    {"name": "Neenah Raw Materials Store",   "code": "WH-NEW-RM", "type": "Raw Materials",     "country": "United States", "region": "North America", "capacity": 300000},
    {"name": "Toronto Canada DC",            "code": "WH-TOR-CA", "type": "Finished Goods DC", "country": "Canada",        "region": "North America", "capacity": 350000},
    {"name": "London UK DC",                 "code": "WH-LDN-UK", "type": "Finished Goods DC", "country": "United Kingdom","region": "EMEA",          "capacity": 480000},
    {"name": "Rotterdam EMEA Hub",           "code": "WH-ROT-NL", "type": "Cross-Dock",        "country": "Netherlands",   "region": "EMEA",          "capacity": 1200000},
    {"name": "Frankfurt Germany DC",         "code": "WH-FRA-DE", "type": "Finished Goods DC", "country": "Germany",       "region": "EMEA",          "capacity": 420000},
    {"name": "Singapore APAC Hub",           "code": "WH-SIN-SG", "type": "Cross-Dock",        "country": "Singapore",     "region": "APAC",          "capacity": 950000},
    {"name": "Shanghai China DC",            "code": "WH-SHA-CN", "type": "Finished Goods DC", "country": "China",         "region": "APAC",          "capacity": 680000},
    {"name": "Sydney Australia DC",          "code": "WH-SYD-AU", "type": "Finished Goods DC", "country": "Australia",     "region": "APAC",          "capacity": 280000},
    {"name": "São Paulo Brazil DC",          "code": "WH-SAO-BR", "type": "Finished Goods DC", "country": "Brazil",        "region": "Latin America", "capacity": 420000},
]

# ── Carrier Reference Data ─────────────────────────────────────────────────

CARRIER_DATA = [
    {"name": "FedEx Freight",            "type": "Road",    "country": "United States", "avg_transit": 2.5,  "otd_pct": 94.2},
    {"name": "UPS Supply Chain Solutions","type": "Road",   "country": "United States", "avg_transit": 2.8,  "otd_pct": 93.5},
    {"name": "J.B. Hunt Transport",      "type": "Road",    "country": "United States", "avg_transit": 3.2,  "otd_pct": 92.1},
    {"name": "Schneider National",       "type": "Road",    "country": "United States", "avg_transit": 3.5,  "otd_pct": 91.8},
    {"name": "Maersk Line",              "type": "Ocean",   "country": "Denmark",       "avg_transit": 28.0, "otd_pct": 72.5},
    {"name": "MSC Mediterranean Shipping","type": "Ocean",  "country": "Switzerland",   "avg_transit": 30.0, "otd_pct": 70.2},
    {"name": "CMA CGM Group",            "type": "Ocean",   "country": "France",        "avg_transit": 27.5, "otd_pct": 73.1},
    {"name": "Evergreen Marine Corp",    "type": "Ocean",   "country": "Taiwan",        "avg_transit": 32.0, "otd_pct": 68.5},
    {"name": "DHL Express",              "type": "Air",     "country": "Germany",       "avg_transit": 1.5,  "otd_pct": 97.8},
    {"name": "FedEx Express International","type": "Air",   "country": "United States", "avg_transit": 1.8,  "otd_pct": 96.5},
    {"name": "XPO Logistics",            "type": "Road",    "country": "United States", "avg_transit": 3.0,  "otd_pct": 91.0},
    {"name": "DB Schenker Rail",         "type": "Rail",    "country": "Germany",       "avg_transit": 5.5,  "otd_pct": 88.5},
]

# ── Customer Reference Data ────────────────────────────────────────────────

CUSTOMER_SEGMENTS = {
    "Mass Retail": ["Walmart Inc", "Target Corporation", "Costco Wholesale", "Sam's Club",
                    "BJ's Wholesale Club", "Meijer Inc", "HEB Grocery Company"],
    "Drug / Pharmacy": ["CVS Health", "Walgreens Boots Alliance", "Rite Aid Corporation",
                        "Duane Reade", "Bartell Drugs"],
    "Grocery": ["Kroger Co", "Albertsons Companies", "Publix Super Markets",
                "Ahold Delhaize USA", "Wakefern Food Corp", "H-E-B Grocery",
                "Aldi Inc", "Lidl US"],
    "E-Commerce": ["Amazon.com Inc", "Chewy Inc", "Instacart", "Thrive Market",
                   "Grove Collaborative"],
    "Club": ["Costco Wholesale", "Sam's Club", "BJ's Wholesale Club"],
    "Dollar": ["Dollar General Corp", "Dollar Tree Stores", "Family Dollar Stores"],
    "Healthcare B2B": ["McKesson Corporation", "Cardinal Health", "AmerisourceBergen",
                       "Medline Industries", "Owens & Minor"],
}

CUSTOMER_CHANNELS = ["Direct", "E-Commerce", "Distributor", "Wholesale", "B2B Direct", "Drop-Ship"]

# ── Destination Reference Data ─────────────────────────────────────────────

DESTINATION_DATA = [
    # North America Retail DCs
    {"name": "Walmart Bentonville DC",          "type": "Customer DC",   "country": "United States", "region": "North America", "lat": 36.37, "lon": -94.21},
    {"name": "Target Distribution Center Minneapolis","type": "Customer DC","country": "United States","region": "North America","lat": 44.97, "lon": -93.27},
    {"name": "Amazon Fulfillment Center Phoenix","type": "Customer DC",   "country": "United States", "region": "North America", "lat": 33.45, "lon": -112.07},
    {"name": "Kroger DC Cincinnati",             "type": "Customer DC",   "country": "United States", "region": "North America", "lat": 39.10, "lon": -84.51},
    {"name": "Costco DC Seattle",                "type": "Customer DC",   "country": "United States", "region": "North America", "lat": 47.61, "lon": -122.33},
    {"name": "CVS DC Woonsocket",                "type": "Customer DC",   "country": "United States", "region": "North America", "lat": 41.99, "lon": -71.51},
    # EMEA Retail DCs
    {"name": "Tesco DC Daventry UK",             "type": "Customer DC",   "country": "United Kingdom","region": "EMEA",          "lat": 52.27, "lon": -1.16},
    {"name": "Carrefour DC Massy France",        "type": "Customer DC",   "country": "France",        "region": "EMEA",          "lat": 48.73, "lon": 2.27},
    {"name": "Rewe DC Cologne Germany",          "type": "Customer DC",   "country": "Germany",       "region": "EMEA",          "lat": 50.94, "lon": 6.96},
    {"name": "Lidl DC Neckarsulm",               "type": "Customer DC",   "country": "Germany",       "region": "EMEA",          "lat": 49.19, "lon": 9.23},
    # APAC
    {"name": "Woolworths DC Sydney",             "type": "Customer DC",   "country": "Australia",     "region": "APAC",          "lat": -33.87, "lon": 151.21},
    {"name": "JD.com DC Beijing",                "type": "Customer DC",   "country": "China",         "region": "APAC",          "lat": 39.90, "lon": 116.41},
    {"name": "Lazada DC Jakarta",                "type": "Customer DC",   "country": "Indonesia",     "region": "APAC",          "lat": -6.21, "lon": 106.85},
    # LatAm
    {"name": "Walmart Mexico DC Monterrey",      "type": "Customer DC",   "country": "Mexico",        "region": "Latin America", "lat": 25.69, "lon": -100.32},
    {"name": "Pão de Açúcar DC São Paulo",       "type": "Customer DC",   "country": "Brazil",        "region": "Latin America", "lat": -23.55, "lon": -46.63},
]

# ── Shift Definitions (Fixed – 3 shifts) ──────────────────────────────────

SHIFT_DATA = [
    {"name": "Morning Shift",   "start": "06:00:00", "end": "14:00:00"},
    {"name": "Afternoon Shift", "start": "14:00:00", "end": "22:00:00"},
    {"name": "Night Shift",     "start": "22:00:00", "end": "06:00:00"},
]

# ── US Public Holidays (for DIM_DATE is_holiday flag) ─────────────────────

US_FEDERAL_HOLIDAYS = {
    # Format: (month, day) or list of specific dates
    "fixed": [
        (1, 1),   # New Year's Day
        (7, 4),   # Independence Day
        (11, 11), # Veterans Day
        (12, 25), # Christmas Day
    ],
    "named": [
        "MLK Day",       # 3rd Monday Jan
        "Presidents Day",# 3rd Monday Feb
        "Memorial Day",  # Last Monday May
        "Labor Day",     # 1st Monday Sep
        "Thanksgiving",  # 4th Thursday Nov
    ]
}

# ── Geographic Region Mapping ─────────────────────────────────────────────

COUNTRY_REGION_MAP = {
    "United States":  "North America",
    "Canada":         "North America",
    "Mexico":         "Latin America",
    "Brazil":         "Latin America",
    "Colombia":       "Latin America",
    "Argentina":      "Latin America",
    "Chile":          "Latin America",
    "United Kingdom": "EMEA",
    "Germany":        "EMEA",
    "France":         "EMEA",
    "Netherlands":    "EMEA",
    "Spain":          "EMEA",
    "Italy":          "EMEA",
    "Sweden":         "EMEA",
    "Finland":        "EMEA",
    "Ireland":        "EMEA",
    "South Africa":   "EMEA",
    "China":          "APAC",
    "Japan":          "APAC",
    "South Korea":    "APAC",
    "Australia":      "APAC",
    "Singapore":      "APAC",
    "Indonesia":      "APAC",
    "Malaysia":       "APAC",
    "India":          "APAC",
    "Taiwan":         "APAC",
    "Denmark":        "EMEA",
    "Switzerland":    "EMEA",
}

PROCUREMENT_STATUSES  = ["Received", "In Transit", "Pending", "Partially Received", "Cancelled"]
SHIPMENT_STATUSES     = ["Delivered", "In Transit", "Delayed", "Returned", "Lost", "Cancelled"]
WAREHOUSE_TYPES       = ["Finished Goods DC", "Raw Materials", "Cold Storage", "Cross-Dock", "Bonded Warehouse"]
VENDOR_TIERS          = ["Tier 1", "Tier 2", "Tier 3"]
PACKAGING_TYPES       = ["Case", "Box", "Carton", "Bag", "Shrink Wrap", "Shipper", "Canister", "Pallet"]
SUPERVISOR_NAMES      = ["Sarah Mitchell", "David Okonkwo", "Maria Guerrero", "James Thornton",
                          "Priya Nair", "Carlos Mendes", "Amanda Fischer", "Raj Patel"]

from btx_omni.monitor.ontology import EventType
from btx_omni.monitor.registry import IndustryPack

PACKS = {
    "aerospace": IndustryPack("aerospace", (EventType.CONTRACT_AWARD, EventType.FACILITY_EXPANSION, EventType.PRODUCTION_RAMP, EventType.BACKLOG_CHANGE), ("sec_edgar", "company_newsroom", "federal_register"), ("airframe", "aerospace", "MRO")),
    "defense": IndustryPack("defense", (EventType.CONTRACT_AWARD, EventType.SOLICITATION, EventType.CONTRACT_MODIFICATION, EventType.SUPPLIER_AWARD), ("sam_gov", "usaspending", "dod"), ("DoD", "IDIQ", "CAGE"), agency_ids=("DoD",), source_identifier_kinds=("UEI", "CAGE")),
    "space_exploration": IndustryPack("space_exploration", (EventType.CONTRACT_AWARD, EventType.PROGRAM_LAUNCH, EventType.GOVERNMENT_FUNDING, EventType.PARTNERSHIP), ("nasa", "sam_gov", "usaspending", "company_newsroom"), ("launch", "satellite", "spacecraft"), agency_ids=("NASA",)),
    "semiconductor": IndustryPack("semiconductor", (EventType.CAPACITY_EXPANSION, EventType.NEW_FACILITY, EventType.CAPITAL_INVESTMENT, EventType.GOVERNMENT_FUNDING), ("commerce", "sec_edgar", "company_newsroom"), ("fab", "wafer", "packaging")),
    "medical": IndustryPack("medical", (EventType.REGULATORY_APPROVAL, EventType.REGULATORY_CHANGE, EventType.PRODUCT_LAUNCH, EventType.FACILITY_EXPANSION), ("fda_openfda", "federal_register", "sec_edgar", "company_newsroom"), ("510(k)", "PMA", "ISO 13485", "robotics")),
    "energy": IndustryPack("energy", (EventType.FACILITY_EXPANSION, EventType.CAPITAL_INVESTMENT, EventType.GOVERNMENT_FUNDING, EventType.PARTNERSHIP), ("sec_edgar", "company_newsroom", "state_economic_development"), ("fusion", "nuclear", "energy")),
}

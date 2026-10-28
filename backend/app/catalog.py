"""Fixed vocabularies shared by the API and the frontend."""

# The 20 practice areas from the product spec (section 3).
MATTER_TYPES = [
    "constitutional", "criminal", "police_procedure", "civil", "family", "property_tenancy",
    "employment", "consumer", "cyber_privacy", "business_contracts", "banking_finance",
    "motor_accident_insurance", "education", "women_child_protection", "disability",
    "environment", "intellectual_property", "administrative", "immigration", "adr_legal_aid",
]

CASE_STAGES = [
    "not_started", "notice_sent", "notice_received", "negotiation", "complaint_filed",
    "case_pending", "order_passed", "appeal", "closed",
]

LANGUAGES = ["en", "hi"]

SOURCE_TYPES = ["legislation", "rule_regulation", "notification_gazette", "judgment", "official_guidance"]
AUTHORITY_LEVELS = ["binding", "persuasive", "legislation", "regulation", "general_guidance"]
LEGAL_STATUSES = ["unknown", "in_force", "amended", "partially_in_force", "repealed", "stayed", "overruled"]

# Official-source allowlist for source URLs (spec section 4). Subdomains of these are allowed.
OFFICIAL_DOMAINS = [
    "indiacode.nic.in", "sci.gov.in", "ecourts.gov.in", "doj.gov.in", "nalsa.gov.in",
    "egazette.gov.in", "gov.in", "nic.in",
]

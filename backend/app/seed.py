"""Idempotent reference data: jurisdictions, plans and feature flags."""
from sqlalchemy.orm import Session

from .models import FeatureFlag, Jurisdiction, Plan

# India's 28 states and 8 union territories. Codes follow the IN-XX pattern used by ISO 3166-2:IN;
# a few ISO codes were revised in 2023 (e.g. Odisha, Telangana, Uttarakhand), so treat these as internal keys.
STATES = {
    "IN-AP": "Andhra Pradesh", "IN-AR": "Arunachal Pradesh", "IN-AS": "Assam", "IN-BR": "Bihar",
    "IN-CG": "Chhattisgarh", "IN-GA": "Goa", "IN-GJ": "Gujarat", "IN-HR": "Haryana",
    "IN-HP": "Himachal Pradesh", "IN-JH": "Jharkhand", "IN-KA": "Karnataka", "IN-KL": "Kerala",
    "IN-MP": "Madhya Pradesh", "IN-MH": "Maharashtra", "IN-MN": "Manipur", "IN-ML": "Meghalaya",
    "IN-MZ": "Mizoram", "IN-NL": "Nagaland", "IN-OD": "Odisha", "IN-PB": "Punjab", "IN-RJ": "Rajasthan",
    "IN-SK": "Sikkim", "IN-TN": "Tamil Nadu", "IN-TG": "Telangana", "IN-TR": "Tripura",
    "IN-UP": "Uttar Pradesh", "IN-UK": "Uttarakhand", "IN-WB": "West Bengal",
}
UNION_TERRITORIES = {
    "IN-AN": "Andaman and Nicobar Islands", "IN-CH": "Chandigarh",
    "IN-DH": "Dadra and Nagar Haveli and Daman and Diu", "IN-DL": "Delhi", "IN-JK": "Jammu and Kashmir",
    "IN-LA": "Ladakh", "IN-LD": "Lakshadweep", "IN-PY": "Puducherry",
}

# Prices are deliberately unset (None): they are a business decision, configured in the admin console.
PLANS = [
    dict(code="free", name="Free", sort_order=0, price_minor=0, billing_interval=None,
         description="Legal rights information, public resources and basic document explanations.",
         entitlements={"ai_questions_per_month": 20, "max_open_cases": 1, "document_drafting": False,
                       "advanced_research": False, "judge_simulation": False}),
    dict(code="premium", name="Premium", sort_order=1, price_minor=None, billing_interval="month",
         description="Higher limits, case workspaces and timelines, drafting and detailed hypothetical analysis.",
         entitlements={"ai_questions_per_month": 300, "max_open_cases": 10, "document_drafting": True,
                       "advanced_research": True, "judge_simulation": True}),
    dict(code="professional", name="Professional", sort_order=2, price_minor=None, billing_interval="month",
         description="For qualified lawyers: client matters, research workflows and version management.",
         entitlements={"ai_questions_per_month": 2000, "max_open_cases": None, "document_drafting": True,
                       "advanced_research": True, "judge_simulation": True}),
    dict(code="institutional", name="Institutional", sort_order=3, price_minor=None, billing_interval="year",
         is_public=False,
         description="Law schools, legal aid organisations, NGOs and businesses. Configured per agreement.",
         entitlements={"ai_questions_per_month": None, "max_open_cases": None, "document_drafting": True,
                       "advanced_research": True, "judge_simulation": True}),
]

# Each flag gates a module that is not built yet; they stay off until the module passes its tests.
FLAGS = {
    "ask_ai": "Ask AI question answering (Phase 3-4)",
    "legal_library": "Searchable legal library (Phase 3)",
    "ai_advocate": "AI Advocate case building (Phase 4)",
    "ai_lawyer": "AI Lawyer explanations and drafts (Phase 4)",
    "ai_judge": "AI Judge hypothetical analysis (Phase 4)",
    "document_studio": "Document generation and upload analysis (Phase 5)",
    "find_lawyer": "Lawyer discovery (Phase 6)",
    "legal_aid_directory": "Verified legal aid and emergency directory (Phase 6)",
    "billing": "Paid checkout (Phase 6)",
}


def seed(db: Session) -> None:
    if db.get(Jurisdiction, "IN") is None:
        db.add(Jurisdiction(code="IN", name="India", kind="country", parent_code=None))
        db.flush()
    for kind, rows in (("state", STATES), ("union_territory", UNION_TERRITORIES)):
        for code, name in rows.items():
            if db.get(Jurisdiction, code) is None:
                db.add(Jurisdiction(code=code, name=name, kind=kind, parent_code="IN"))
    for p in PLANS:
        if db.get(Plan, p["code"]) is None:
            db.add(Plan(**p))
    for key, desc in FLAGS.items():
        if db.get(FeatureFlag, key) is None:
            db.add(FeatureFlag(key=key, description=desc, enabled=False))
    db.commit()

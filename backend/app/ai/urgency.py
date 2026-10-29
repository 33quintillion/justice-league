"""Rule-based urgent-help detection (English, Hindi and romanised Hindi).

It runs before anything else, needs no AI, no login and no consent, and errs towards showing help.
It only points to 112 and to free legal aid; it never invents helpline numbers.
"""
from __future__ import annotations

import re
import unicodedata

EMERGENCY_TEXT = "If anyone is in immediate danger, call 112 now. It is India's single emergency number for police, fire and ambulance."
LEGAL_AID_TEXT = "Free legal help is available from your District Legal Services Authority. See the Legal Aid page."

# (category, level, patterns). Latin patterns match on word boundaries; Devanagari ones as substrings.
RULES: list[tuple[str, str, list[str]]] = [
    ("self_harm", "emergency", [
        r"suicid\w*", r"kill (?:myself|me self)", r"end (?:my|this) life", r"want to die", r"take my (?:own )?life",
        r"khudkushi", r"atmahatya", r"mar jaana chaht\w*",
        "आत्महत्या", "खुदकुशी", "जान दे दूं", "मर जाना चाहत",
    ]),
    ("violence", "emergency", [
        r"(?:going|want|threaten\w*|try\w*) to kill", r"kill (?:me|us|him|her|my)", r"beat(?:ing|s)? (?:me|us|my)",
        r"hitting (?:me|us|my)", r"attack(?:ed|ing)? (?:me|us|my)", r"(?:knife|gun|acid) (?:attack|threat)",
        r"kidnap\w*", r"abduct\w*", r"traffick\w*", r"held (?:captive|hostage)", r"locked (?:me|us) (?:in|up)",
        r"jaan se maar\w*", r"maar dal\w*", r"maar\s?peet", r"pita?i kar",
        "जान से मार", "मार डाल", "मारपीट", "पीट रहा", "पीटता", "अपहरण", "बंधक",
    ]),
    ("domestic_violence", "emergency", [
        r"domestic violence", r"(?:husband|in-?laws?|partner) (?:beats|hits|attacks|tortures)", r"dowry (?:harass\w*|death|torture)",
        r"dahej", "दहेज", "घरेलू हिंसा", "ससुराल वाले मार",
    ]),
    ("sexual_violence", "emergency", [
        r"rape[ds]?", r"raping", r"sexual(?:ly)? (?:assault\w*|abus\w*)", r"molest\w*",
        "बलात्कार", "यौन उत्पीड़न", "यौन शोषण", "छेड़छाड़",
    ]),
    ("child_safety", "emergency", [
        r"child (?:abuse|marriage|labour|labor|trafficking)", r"(?:minor|child) (?:is being|was) (?:abused|married|beaten)",
        "बाल विवाह", "बाल श्रम", "बच्चे के साथ दुर्व्यवहार",
    ]),
    ("arrest_or_detention", "urgent", [
        r"(?:been|was|got|being|is) (?:arrested|detained|picked up by (?:the )?police)", r"police custody", r"in custody",
        r"police (?:took|have taken|are taking|picked up)", r"giraftar", r"hirasat",
        "गिरफ्तार", "हिरासत", "पुलिस उठा", "पुलिस ले गई", "पुलिस ले गए",
    ]),
    ("imminent_deadline", "urgent", [
        r"(?:evict\w*|thrown out|throw (?:me|us) out|demoli\w*)\b.{0,30}\b(?:today|tonight|tomorrow)",
        r"(?:today|tonight|tomorrow)\b.{0,30}\b(?:evict\w*|thrown out|demoli\w*)",
        r"(?:hearing|deadline|last date|court date|summons)\b.{0,20}\b(?:today|tomorrow)",
        r"(?:today|tomorrow)\b.{0,20}\b(?:hearing|deadline|last date)",
        "घर से निकाल", "कल सुनवाई", "आज सुनवाई", "आज आखिरी", "कल आखिरी",
    ]),
]



def _compile(p: str) -> re.Pattern:
    if p.isascii():
        return re.compile(rf"(?<![a-z]){p}(?![a-z])")
    return re.compile(re.escape(p))  # Devanagari: plain substring (no reliable word boundaries)


_COMPILED = [(cat, lvl, [_compile(p) for p in pats]) for cat, lvl, pats in RULES]

GUIDANCE = {
    "self_harm": "You matter, and help is available right now. Please call 112 or go to the nearest hospital, and reach out to someone you trust.",
    "violence": "Get to a safe place if you can and call 112. You can file a police complaint later; your safety comes first.",
    "domestic_violence": "If you are being hurt or threatened, call 112. A Protection Officer, the police or your District Legal Services Authority can help you seek protection.",
    "sexual_violence": "Call 112 if you are in danger. You can seek medical help and report to the police, and free legal aid is available to you.",
    "child_safety": "If a child is at risk, call 112 now.",
    "arrest_or_detention": "If someone has been arrested or detained, ask which police station they are held at and contact a lawyer or your District Legal Services Authority for free legal aid straight away.",
    "imminent_deadline": "This looks time-critical. Contact a lawyer or your District Legal Services Authority today rather than waiting for a full analysis here.",
}


def _prepare(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")[:20_000].lower()
    return re.sub(r"\s+", " ", text)


def detect(text: str) -> dict:
    t = _prepare(text)
    hits = [cat for cat, _lvl, pats in _COMPILED if any(p.search(t) for p in pats)]
    levels = {lvl for cat, lvl, _ in RULES if cat in hits}
    level = "emergency" if "emergency" in levels else "urgent" if "urgent" in levels else "none"
    messages = []
    if level == "emergency":
        messages.append(EMERGENCY_TEXT)
    messages += [GUIDANCE[c] for c in hits]
    if level != "none":
        messages.append(LEGAL_AID_TEXT)
    return {
        "level": level,
        "categories": hits,
        "messages": messages,
        "call": "112" if level == "emergency" else None,
        "legal_aid_path": "/legal-aid" if level != "none" else None,
    }

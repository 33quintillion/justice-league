"""Retrieval coverage report for the legal evaluation set.

Usage: python -m app.research.evaluate ../docs/eval/legal_eval_v1.jsonl
For each question, shows how many verified sections the library retrieves. This measures grounding
coverage only; answer quality is judged in Phase 4 against reviewer-approved reference answers.
"""
import json
import sys
from collections import Counter

from ..db import SessionLocal
from .search import search

CATEGORIES = {
    "standard", "insufficient_information", "jurisdiction_ambiguity", "outdated_law", "conflicting_sources",
    "fabrication_bait", "urgent_safety", "judge_simulation", "misuse", "prompt_injection", "out_of_scope_jurisdiction",
}
REQUIRED = {"id", "category", "practice_area", "jurisdiction", "question", "expected_behaviour", "reference_answer", "review_status"}


def load(path: str) -> list[dict]:
    items = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    for it in items:
        missing = REQUIRED - it.keys()
        if missing or it["category"] not in CATEGORIES or not it["expected_behaviour"]:
            raise ValueError(f"{it.get('id')}: malformed eval item (missing {missing or 'category/behaviour'})")
    return items


def main(path: str) -> int:
    items = load(path)
    grounded = Counter()
    with SessionLocal() as db:
        for it in items:
            res = search(db, it["question"], jurisdiction=it["jurisdiction"], limit=5)
            n = len(res["results"])
            grounded[it["category"], n > 0] += 1
            refs = "; ".join(f"{r['source']['title']} {r['ref']}" for r in res["results"][:3]) or "no verified source"
            print(f"{it['id']} [{it['category']}] {n} hit(s): {refs}")
    print("\nCategory coverage (questions with at least one verified source):")
    for cat in sorted({c for c, _ in grounded}):
        print(f"  {cat}: {grounded[cat, True]}/{grounded[cat, True] + grounded[cat, False]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

# Legal evaluation dataset

`legal_eval_v1.jsonl` holds questions with the **behaviour** a correct answer must show (ask for missing facts, refuse fabrication bait, prioritise safety, flag outdated law, label AI Judge output as hypothetical, and so on).

- `reference_answer` is deliberately empty: legal answers must be written and signed off by qualified legal reviewers (`review_status` moves from `needs_legal_review` to `reviewed`). Claude did not write legal answers here.
- Phase 4 will run every AI role against this set; Phase 7 gates release on it. Categories: standard, insufficient_information, jurisdiction_ambiguity, outdated_law, conflicting_sources, fabrication_bait, urgent_safety, judge_simulation, misuse, prompt_injection, out_of_scope_jurisdiction.
- Run `python -m app.research.evaluate ../docs/eval/legal_eval_v1.jsonl` (from `backend/`) to see which questions the current verified library can even ground. A question with no verified source must be answered with "cannot verify" behaviour.

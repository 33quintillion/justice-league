export type Role = "ask" | "lawyer" | "advocate" | "judge";
export type Statement = { text: string; source_ids: string[] };
export type Urgency = { level: "none" | "urgent" | "emergency"; categories: string[]; messages: string[]; call: string | null; legal_aid_path: string | null };
export type AnswerSource = {
  label: string; cited: boolean; source_id: string | null; section_id: string | null; title: string; ref: string;
  official_url: string; document_sha256: string; text: string;
};
export type Checks = {
  removed?: { section: string; text: string; reason: string }[];
  invalid_source_ids?: string[];
  links_removed?: number;
  numbers_removed?: number;
  citations_checked?: number;
  unverified_citations?: { text: string; status: string; message: string }[];
  served_by_fallback_model?: boolean;
  reason?: string;
};
export type Answer = {
  id: string; role: Role; title: string; question: string; case_id: string | null; status: string; created_at: string;
  response: Record<string, string | string[] | Statement[]>; checks: Checks; urgency: Urgency; llm_called: boolean;
  model: string; prompt_version: string; disclaimer: string; sources: AnswerSource[]; label?: string;
};
export type AIStatus = {
  configured: boolean; model: string | null; judge_label: string; disclaimer: string;
  roles: Record<Role, { title: string; needs_case: boolean; enabled: boolean }>;
};
export type AnswerSummary = { id: string; role: Role; question: string; status: string; case_id: string | null; created_at: string };

export const STATUS_LABELS: Record<string, string> = {
  answered: "Answered from verified sources",
  cannot_verify: "Cannot verify",
  needs_more_information: "Needs more information",
};

type Section = { key: string; title: string; kind: "text" | "list" | "statements" };
const S = (key: string, title: string, kind: Section["kind"]): Section => ({ key, title, kind });

const BEFORE = [S("law_points", "What the law says (verified)", "statements")];
const AFTER = [
  S("explanation", "Explanation", "text"),
  S("assumptions", "What we assumed", "list"),
  S("uncertainties", "What is uncertain", "list"),
  S("questions_for_user", "Questions for you", "list"),
  S("next_steps", "Next steps", "list"),
];

export const SECTIONS: Record<Role, Section[]> = {
  ask: [...BEFORE, ...AFTER],
  lawyer: [...BEFORE, S("options", "Your options", "statements"), S("procedure", "Procedure, step by step", "statements"),
    S("documents_needed", "Documents to gather", "list"), ...AFTER],
  advocate: [S("issues", "Legal issues", "list"), ...BEFORE, S("supporting_points", "Points supporting your side", "statements"),
    S("evidence_checklist", "Evidence checklist", "list"), S("weaknesses", "Weaknesses to prepare for", "list"), ...AFTER],
  judge: [S("issues", "Issues to decide", "list"), S("agreed_facts", "Facts that appear agreed", "list"),
    S("disputed_facts", "Facts likely to be disputed", "list"), S("missing_evidence", "Missing evidence", "list"), ...BEFORE,
    S("claimant_arguments", "Arguments for the person bringing the claim", "statements"),
    S("respondent_arguments", "Arguments for the other side", "statements"),
    S("burden_of_proof", "Who must prove what", "statements"),
    S("hypothetical_assessment", "Hypothetical assessment", "text"), S("what_could_change", "What could change this view", "list"), ...AFTER],
};

export type Warning = { level: "severe" | "caution"; text: string };
export type SourceCard = {
  id: string; title: string; citation: string; source_type: string; authority_level: string;
  jurisdiction_code: string; publisher: string; official_url: string; effective_date: string | null;
  legal_status: string; last_verified_at: string | null; practice_areas: string[];
  document_sha256: string | null; document_retrieved_at: string | null; warnings?: Warning[];
};
export type SearchResult = {
  section_id: string; ref: string; heading: string; snippet: string; source: SourceCard; warnings: Warning[];
};
export type SearchResponse = { query: string; jurisdiction_filter: string[] | null; results: SearchResult[]; notes: string[] };

export const AUTHORITY_LABELS: Record<string, string> = {
  legislation: "Legislation",
  regulation: "Rules / regulation",
  binding: "Binding judgment",
  persuasive: "Persuasive authority",
  general_guidance: "General guidance",
};

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  legislation: "Act",
  rule_regulation: "Rules / regulations",
  notification_gazette: "Notification / gazette",
  judgment: "Judgment",
  official_guidance: "Official guidance",
};

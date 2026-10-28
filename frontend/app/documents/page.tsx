import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "Document Studio" };

export default function Page() {
  return <ModuleStatus title={"Document Studio"} flag={"document_studio"} phase={"Phase 5"} purpose={"Generate editable drafts and understand documents you upload."} planned={["Templates for legal notices, consumer complaints, RTI applications, affidavits and more", "Clearly marked placeholders; your facts kept separate from AI wording", "Upload PDF, DOCX, text or images with OCR; summaries, key dates and clauses", "DOCX/PDF export with revision history"]} safeguards={["Uploaded documents are treated as untrusted content", "Nothing is sent or filed without your explicit confirmation"]} />;
}

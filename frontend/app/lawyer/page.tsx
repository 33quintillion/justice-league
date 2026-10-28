import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "AI Lawyer" };

export default function Page() {
  return <ModuleStatus title={"AI Lawyer"} flag={"ai_lawyer"} phase={"Phase 4"} purpose={"Explains the law in plain language and prepares editable first drafts."} planned={["Explains statutes, sections, rules and judgments, with sources", "Compares legal options and procedures, limitation periods and jurisdiction", "Highlights problematic or missing clauses in documents", "Recommends when professional advice is needed"]} safeguards={["Every AI-generated document must be reviewed before it is filed, signed or served"]} />;
}

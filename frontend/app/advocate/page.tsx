import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "AI Advocate" };

export default function Page() {
  return <ModuleStatus title={"AI Advocate"} flag={"ai_advocate"} phase={"Phase 4"} purpose={"Helps you understand and organise your side of a dispute."} planned={["Guided questions about your situation", "Chronological timeline of facts, missing information and evidence checklist", "Draft notices, complaints and representations for your review", "Questions to ask a qualified lawyer; strengths, weaknesses and risks"]} safeguards={["Never fabricates evidence or encourages false allegations", "Never guarantees an outcome"]} />;
}

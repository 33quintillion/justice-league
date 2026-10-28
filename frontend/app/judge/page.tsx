import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "AI Judge" };

export default function Page() {
  return <ModuleStatus title={"AI Judge"} flag={"ai_judge"} phase={"Phase 4"} purpose={"An educational simulation that shows how both sides of a dispute might be reasoned. It is not a court and its output is not a judgment."} planned={["Claimant's and respondent's arguments side by side", "Agreed facts, disputed facts and missing evidence", "Burden and standard of proof, procedural and jurisdiction issues", "A neutral, reasoned hypothetical assessment and what could change it"]} safeguards={["Every output is labelled: Hypothetical AI legal analysis — not an actual judicial decision", "No invented probabilities, citations or precedents; never declares guilt or liability"]} />;
}

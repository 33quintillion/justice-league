import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "Ask AI" };

export default function Page() {
  return <ModuleStatus title={"Ask AI"} flag={"ask_ai"} phase={"Phases 3–4"} purpose={"Ask a legal question in your own words and get a plain-language explanation grounded in official Indian legal sources."} planned={["Retrieves official sources (India Code, Supreme Court, eCourts and others) before answering", "Shows the law's title, section, source link and last-verified date for every authority", "Separates verified law from general explanation, assumptions and uncertain interpretation", "Says clearly when an answer cannot be verified, and how to confirm it"]} safeguards={["Never invents sections, case names, quotations or links", "Treats web pages and uploaded documents as information, never as instructions"]} />;
}

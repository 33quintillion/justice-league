import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "Legal Library" };

export default function Page() {
  return <ModuleStatus title={"Legal Library"} flag={"legal_library"} phase={"Phase 3"} purpose={"Search Indian legislation, rules, notifications and judgments from official sources."} planned={["Keyword and semantic search", "Source metadata: authority level, effective date, amendment status, last verification", "Original source links for every document"]} freeForever />;
}

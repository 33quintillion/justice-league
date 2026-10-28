import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "My Legal Rights" };

export default function Page() {
  return <ModuleStatus title={"My Legal Rights"} flag={"legal_library"} phase={"Phase 3"} purpose={"Plain-language guides to your rights in India, covering 20 areas from fundamental rights to consumer protection, tenancy and employment."} planned={["Topic guides for each of the 20 practice areas", "Central and state-specific laws, with the jurisdiction always stated", "A 'View Original Source' link on every legal authority"]} freeForever />;
}

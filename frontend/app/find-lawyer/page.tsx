import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "Find a Lawyer" };

export default function Page() {
  return <ModuleStatus title={"Find a Lawyer"} flag={"find_lawyer"} phase={"Phase 6"} purpose={"Search for qualified advocates by location, practice area, language and consultation method."} planned={["Profiles with bar enrolment details and verification status", "Consultation requests and transparent fees", "Document sharing only with your consent"]} safeguards={["No invented profiles, credentials, ratings or availability", "Verified and unverified profiles are always clearly distinguished"]} />;
}

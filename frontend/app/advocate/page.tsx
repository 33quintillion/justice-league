import { AIRole } from "@/components/AIRole";

export const metadata = { title: "AI Advocate" };

export default function Page() {
  return (
    <AIRole
      role="advocate"
      title={"AI Advocate"}
      intro={"Organise your side of one of your cases: the legal issues, the points that support you, an evidence checklist and the weaknesses to prepare for."}
      safeguards={["Uses only the facts you recorded in the case and verified legal sources.", "Honest about weaknesses; it never overstates your case or invents facts.", "It will not help make false complaints or fabricate evidence."]}
      placeholder={"e.g. What supports my claim, and what evidence should I collect?"}
    />
  );
}

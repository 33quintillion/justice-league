import { AIRole } from "@/components/AIRole";

export const metadata = { title: "AI Lawyer" };

export default function Page() {
  return (
    <AIRole
      role="lawyer"
      title={"AI Lawyer"}
      intro={"Understand the law that applies to your situation, your options, the procedure step by step and the documents to gather, from verified official sources."}
      safeguards={["Explains options and procedure only from verified sources, each one linked to the original.", "Separates verified law from explanation, assumptions and uncertainty.", "It is not a lawyer and cannot represent you. For advice on your facts, speak to an advocate or your legal services authority."]}
      placeholder={"e.g. My employer has not paid my last two months' salary. What can I do?"}
    />
  );
}

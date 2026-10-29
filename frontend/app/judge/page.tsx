import { AIRole } from "@/components/AIRole";

export const metadata = { title: "AI Judge" };

export default function Page() {
  return (
    <AIRole
      role="judge"
      title={"AI Judge"}
      intro={"An educational simulation of how both sides of your dispute might be reasoned, so you can prepare. It is not a court and its output is not a judgment."}
      safeguards={["Every output carries the label: Hypothetical AI legal analysis — not an actual judicial decision.", "It gives no percentages or odds, and never declares guilt or liability.", "It has heard only your account, so it lists what the other side may say and what evidence is missing."]}
      placeholder={"e.g. How might each side argue this, and what could change the outcome?"}
    />
  );
}

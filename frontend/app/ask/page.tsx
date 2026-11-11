import { AIRole } from "@/components/AIRole";

export const metadata = { title: "Ask AI" };

export default function Page() {
  return (
    <AIRole
      role="ask"
      title={"Ask AI"}
      intro={"Ask a legal question in your own words. We first find the verified official sections that match, and the AI answers only from those, showing each source."}
      safeguards={["It answers only from verified official sources in our library, and shows each one with a link to the original.", "If nothing verified matches, it says so instead of guessing, and no AI is used.", "Every answer is checked: unsupported legal claims, links that are not official sources and percentages are removed, and citations are checked against the library.", "Text from documents and web pages is treated as information, never as instructions."]}
      placeholder={"e.g. When must my landlord return my security deposit?"}
    />
  );
}

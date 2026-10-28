import { ModuleStatus } from "@/components/ModuleStatus";

export const metadata = { title: "Legal Aid" };

export default function Page() {
  return (
    <>
      <div className="card" style={{ borderLeft: "4px solid var(--burgundy)" }}>
        <h2>If you need help right now</h2>
        <p>
          If you or someone else is in immediate danger, call <a href="tel:112"><strong>112</strong></a>, India&apos;s
          national emergency number.
        </p>
        <p>
          Free legal services may be available to you through the National Legal Services Authority and your state and
          district legal services authorities. Official website:{" "}
          <a href="https://nalsa.gov.in/" rel="noopener noreferrer" target="_blank">nalsa.gov.in</a>.
        </p>
      </div>
      <ModuleStatus
        title="Legal Aid directory"
        flag="legal_aid_directory"
        phase="Phase 6"
        purpose="A maintained directory of official legal aid and support services, with jurisdiction-specific contact details."
        planned={[
          "State and district legal services authorities, with verified contact details",
          "Helplines for women, children, cybercrime and other urgent situations, each linked to its official source",
          "Eligibility information for free legal aid",
        ]}
        safeguards={["Every contact detail is verified against an official source and dated before it is shown"]}
        freeForever
      />
    </>
  );
}

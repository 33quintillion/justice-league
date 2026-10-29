// E2E ONLY: a local stand-in for the Anthropic Messages API, so the browser journeys exercise the real
// AnthropicProvider code path without a key or network. It answers from the sources in the prompt and
// deliberately includes a non-official link and a percentage, which the server must strip.
// Start it, then run the API with ANTHROPIC_API_KEY=e2e-stub ANTHROPIC_BASE_URL=http://127.0.0.1:8787
import http from "node:http";

const PORT = Number(process.env.STUB_PORT ?? 8787);

function answer(body) {
  const prompt = body.messages?.[0]?.content ?? "";
  const srcs = [...prompt.matchAll(/<source id="(S\d+)">\ntitle: ([^\n]*)\nsection: ([^\n]*)/g)].map((m) => ({ id: m[1], title: m[2], ref: m[3] }));
  const props = body.output_config?.format?.schema?.properties ?? {};
  const deposit = srcs.find((s) => /Section 3\b/.test(s.ref)) ?? srcs[0];
  const out = {};
  for (const [k, s] of Object.entries(props)) out[k] = s.type === "string" ? "" : [];
  Object.assign(out, {
    status: "answered",
    summary: `Under ${deposit.ref.split(" ").slice(0, 2).join(" ")} of the source provided, the landlord must refund the deposit within thirty days of vacant possession.`,
    law_points: [{ text: "The security deposit must be refunded within thirty days of handing over vacant possession.", source_ids: [deposit.id] }],
    explanation: "You have about a 90% chance if you kept your receipts. More at https://example.com/not-official.",
    assumptions: ["You have already handed over vacant possession."],
    next_steps: ["Write to the landlord asking for the refund, and keep a copy."],
  });
  if ("claimant_arguments" in props) Object.assign(out, {
    issues: ["Whether the deposit became refundable", "Whether any deductions were lawful"],
    claimant_arguments: [{ text: "The tenant handed over vacant possession, so the thirty-day period began.", source_ids: [deposit.id] }],
    respondent_arguments: [{ text: "The landlord may say there was damage that justified deductions.", source_ids: [] }],
    missing_evidence: ["Proof of the date possession was handed over"],
    hypothetical_assessment: "On the tenant's account alone the claim appears reasonably strong, with roughly 80 percent likelihood, but the landlord has not been heard.",
    what_could_change: ["Written evidence of damage", "A later handover date"],
  });
  return out;
}

http.createServer((req, res) => {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    if (req.method !== "POST" || !req.url.startsWith("/v1/messages")) { res.writeHead(404).end(); return; }
    const body = JSON.parse(raw);
    const text = JSON.stringify(answer(body));
    res.writeHead(200, { "content-type": "application/json", "request-id": `req_stub_${Date.now()}` });
    res.end(JSON.stringify({
      id: "msg_stub", type: "message", role: "assistant", model: body.model, stop_reason: "end_turn", stop_sequence: null,
      content: [{ type: "text", text }], usage: { input_tokens: Math.round(raw.length / 4), output_tokens: Math.round(text.length / 4) },
    }));
  });
}).listen(PORT, "127.0.0.1", () => console.log(`stub anthropic on ${PORT}`));

// Phase 4 browser journeys: AI role gating, consent, grounded answers with sources, urgency banner,
// answer checks, AI Judge label, history delete. Needs: phase3.mjs run first (a verified fictional source),
// e2e/stub-anthropic.mjs running, and the API started with ANTHROPIC_API_KEY=e2e-stub
// ANTHROPIC_BASE_URL=http://127.0.0.1:8787 against the throwaway e2e database.
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.env.WEB_URL ?? "http://localhost:3000";
const BACKEND_DIR = process.env.BACKEND_DIR ?? path.resolve(import.meta.dirname, "../../backend");
if (!/e2e|test/.test(process.env.DATABASE_URL ?? "")) {
  console.error("Refusing to run: set DATABASE_URL to the throwaway e2e/test database the API uses.");
  process.exit(2);
}
const SHOTS = path.resolve(import.meta.dirname, "screenshots");
mkdirSync(SHOTS, { recursive: true });
const run = Date.now();
const PASSWORD = "e2e password 12345";
const results = [];
const errors = [];
const expect = (c, m) => { if (!c) throw new Error(m); };
async function step(name, fn) {
  try { await fn(); results.push(["PASS", name]); } catch (e) {
    results.push(["FAIL", name, e.message.split("\n")[0]]);
    await globalThis.user?.screenshot({ path: path.join(SHOTS, `fail-${results.length}.png`), fullPage: true }).catch(() => {});
  }
}
async function newUser(browser, email, viewport = { width: 1280, height: 900 }) {
  const ctx = await browser.newContext({ viewport });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(e.message));
  await p.goto(`${BASE}/register`);
  await p.getByLabel("Email address").fill(email);
  await p.getByLabel("Password").fill(PASSWORD);
  await p.getByLabel(/I understand JUSTICE AI/).check();
  await p.getByRole("button", { name: "Create account" }).click();
  await p.waitForURL(`${BASE}/cases`);
  return p;
}
async function verify(p) {
  await p.goto(`${BASE}/dev/outbox`);
  await p.getByRole("link", { name: /verify-email\?token=/ }).first().click();
  await p.getByText("Your email address is verified").waitFor();
}

const browser = await chromium.launch();
const admin = await newUser(browser, `root-${run}@example.com`);
execFileSync("python3", ["-m", "app.cli", "grant-role", `root-${run}@example.com`, "sysadmin"], { cwd: BACKEND_DIR });
const user = await newUser(browser, `user-${run}@example.com`);
globalThis.user = user;
await verify(user);

await step("library has a verified source to answer from (run phase3.mjs first)", async () => {
  const r = await user.request.get(`${BASE}/api/library/sources`);
  expect((await r.json()).length > 0, "no verified sources in the e2e database");
});

await step("a role whose flag is off says so and offers no form", async () => {
  for (const f of ["ask_ai", "ai_judge"]) await admin.request.put(`${BASE}/api/admin/flags/${f}`, {
    data: { enabled: false }, headers: { "x-csrf-token": (await admin.context().cookies()).find((c) => c.name === "justice_csrf").value },
  });
  await user.goto(`${BASE}/ask`);
  await user.getByText("is built but not switched on yet").waitFor();
  expect(await user.getByRole("button", { name: "Ask" }).count() === 0, "form shown while flag off");
  await user.screenshot({ path: path.join(SHOTS, "09-ask-flag-off.png"), fullPage: true });
});

await step("sysadmin switches the AI roles on in the admin console", async () => {
  await admin.goto(`${BASE}/admin`);
  await admin.getByRole("tab", { name: "Feature flags" }).click();
  for (const f of ["ask_ai", "ai_judge"]) {
    const box = admin.getByRole("checkbox", { name: new RegExp(`^${f} `) });
    await box.check();
    await admin.waitForTimeout(300);
    expect(await box.isChecked(), `${f} not on`);
  }
});

await step("without AI consent the user is sent to Settings, and can opt in", async () => {
  await user.goto(`${BASE}/ask`);
  await user.getByText("allow AI processing in").waitFor();
  await user.getByRole("link", { name: "Settings" }).last().click();
  await user.getByLabel(/Allow JUSTICE AI to process my questions/).check();
  await user.waitForTimeout(500);
});

await step("Ask AI answers from a verified source, with the source and checks shown", async () => {
  await user.goto(`${BASE}/ask`);
  await user.getByLabel("Your question").fill("When must my landlord refund the security deposit?");
  await user.getByRole("button", { name: "Ask" }).click();
  const ans = user.getByRole("region", { name: "Ask AI answer", exact: true });
  await ans.getByText("Answered from verified sources").waitFor({ timeout: 30000 });
  await ans.getByText("What the law says (verified)").waitFor();
  const body = await ans.innerText();
  expect(!body.includes("90%") && !body.includes("example.com"), "percentage or fake link shown");
  expect(body.includes("numeric estimate(s) removed") && body.includes("link(s) removed"), "checks notice missing");
  expect((await ans.locator("a", { hasText: "View original source ↗" }).first().getAttribute("href")).startsWith("https://"), "no official link");
  await ans.getByText("Legal information, not legal advice").waitFor();
  await user.screenshot({ path: path.join(SHOTS, "10-ask-answer.png"), fullPage: true });
});

await step("an emergency question shows 112 at once", async () => {
  await user.getByLabel("Your question").fill("My landlord is beating me and says he will kill me if I ask for my deposit");
  await user.getByRole("button", { name: "Ask" }).click();
  await user.getByText("This may be an emergency.").first().waitFor();
  await user.getByRole("link", { name: "Call 112" }).first().waitFor();
  await user.getByRole("region", { name: "Ask AI answer", exact: true }).waitFor({ timeout: 30000 });
  await user.screenshot({ path: path.join(SHOTS, "11-ask-emergency.png") });
});

await step("AI Judge on a case is labelled hypothetical and shows no percentages", async () => {
  await user.goto(`${BASE}/cases`);
  await user.getByRole("button", { name: "New case" }).click();
  await user.getByLabel("Short title").fill("Deposit not returned");
  await user.getByLabel("Area of law").selectOption("property_tenancy");
  await user.getByLabel(/What happened/).fill("I moved out in August and handed over the keys. The landlord kept my security deposit.");
  await user.getByRole("button", { name: /Create case/ }).click();
  await user.waitForURL(/\/cases\/[0-9a-f-]{36}$/);
  await user.getByRole("link", { name: /See both sides with AI Judge/ }).click();
  await user.waitForURL(/\/judge\?case=/);
  await user.getByText("Hypothetical AI legal analysis — not an actual judicial decision").first().waitFor();
  await user.getByLabel(/What would you like to know/).fill("How might each side argue this?");
  await user.getByRole("button", { name: "Analyse" }).click();
  const ans = user.getByRole("region", { name: "AI Judge answer", exact: true });
  await ans.getByText("Arguments for the other side").waitFor({ timeout: 30000 });
  const body = await ans.innerText();
  expect(body.includes("Hypothetical AI legal analysis — not an actual judicial decision"), "label missing in answer");
  expect(!/\d+\s?(%|percent)/.test(body), "percentage shown");
  await user.screenshot({ path: path.join(SHOTS, "12-judge-answer.png"), fullPage: true });
});

await step("answers are listed privately and can be deleted", async () => {
  const item = user.getByRole("listitem").filter({ hasText: "How might each side argue this?" });
  user.once("dialog", (d) => d.accept());
  await item.getByRole("button", { name: /Delete answer/ }).click();
  await item.waitFor({ state: "detached" });
});

await step("Ask AI is usable on a phone", async () => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, storageState: await user.context().storageState() });
  const m = await ctx.newPage();
  await m.goto(`${BASE}/ask`);
  await m.getByLabel("Your question").waitFor();
  const overflow = await m.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(!overflow, "horizontal scroll on mobile");
  await m.screenshot({ path: path.join(SHOTS, "13-ask-mobile.png"), fullPage: true });
});

await browser.close();
for (const r of results) console.log(r.join(" | "));
if (errors.length) console.log("page errors:", errors);
process.exit(results.some((r) => r[0] === "FAIL") || errors.length ? 1 : 0);

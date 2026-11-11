// Phase 3 browser journeys: source upload, independent review, library search, source pages, citation checker.
// Uses a FICTIONAL test fixture. Run against a throwaway database, never one with real users or sources:
//   DATABASE_URL=...justice_e2e  (same value as the API server) node e2e/phase3.mjs
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.env.WEB_URL ?? "http://localhost:3000";
const BACKEND_DIR = process.env.BACKEND_DIR ?? path.resolve(import.meta.dirname, "../../backend");
if (!/e2e|test/.test(process.env.DATABASE_URL ?? "")) {
  console.error("Refusing to run: set DATABASE_URL to a throwaway e2e/test database (it gets fictional legal fixtures).");
  process.exit(2);
}
const SHOTS = path.resolve(import.meta.dirname, "screenshots");
mkdirSync(SHOTS, { recursive: true });
const run = Date.now();
const PASSWORD = "e2e password 12345";
const TITLE = `The Fictional Tenancy (Test Fixture ${run}) Act, 2099`;
const FIXTURE = path.join(SHOTS, `fixture-${run}.txt`);
writeFileSync(FIXTURE, `${TITLE.toUpperCase()}
1. Short title.—This Act may be called ${TITLE}.
2. Definitions.—In this Act "security deposit" means money paid by a tenant to secure the tenancy agreement.
3. Return of security deposit.—The landlord shall refund the security deposit within thirty days of the tenant handing over vacant possession.
4. Eviction only by order.—No tenant shall be evicted except in pursuance of an order of the Rent Authority.
`);

const results = [];
const errors = [];
const expect = (c, m) => { if (!c) throw new Error(m); };
async function step(name, fn) {
  try { await fn(); results.push(["PASS", name]); } catch (e) { results.push(["FAIL", name, e.message.split("\n")[0]]); }
}
async function staffPage(browser, email, role) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(e.message));
  await p.goto(`${BASE}/register`);
  await p.getByLabel("Email address").fill(email);
  await p.getByLabel("Password").fill(PASSWORD);
  await p.getByLabel(/I understand JUSTICE AI/).check();
  await p.getByRole("button", { name: "Create account" }).click();
  await p.waitForURL(`${BASE}/cases`);
  execFileSync("python3", ["-m", "app.cli", "grant-role", email, role], { cwd: BACKEND_DIR });
  await p.goto(`${BASE}/admin`);
  await p.getByRole("tab", { name: "Legal sources" }).click();
  return p;
}

const browser = await chromium.launch();
const researcher = await staffPage(browser, `res-${run}@example.com`, "legal_researcher");
const reviewer = await staffPage(browser, `rev-${run}@example.com`, "content_reviewer");

await step("researcher adds a source; non-official URLs are refused", async () => {
  const f = researcher.locator("form", { has: researcher.getByRole("button", { name: "Add source" }) });
  await f.getByLabel("Title").fill(TITLE);
  await f.getByLabel("Official URL").fill("https://example.com/act.pdf");
  await f.getByRole("button", { name: "Add source" }).click();
  await researcher.getByText("official government domain").waitFor();
  await f.getByLabel("Official URL").fill(`https://www.indiacode.nic.in/test-fixture/${run}`);
  await f.getByLabel("Citation").fill(`Test Act ${run} of 2099`);
  await f.getByLabel(/Practice areas/).selectOption(["property_tenancy"]);
  await f.getByRole("button", { name: "Add source" }).click();
  await researcher.getByText("Upload the official document next.").waitFor();
});

await step("researcher uploads the official file; it is split into sections and sent for review", async () => {
  await researcher.getByLabel(/File \(PDF or UTF-8 text/).setInputFiles(FIXTURE);
  await researcher.getByRole("button", { name: "Upload", exact: true }).click();
  await researcher.getByText("Document uploaded and sent for review.").waitFor();
  await researcher.getByText("Sections (4)").waitFor();
  await researcher.getByText("You added or uploaded this source, so someone else must review it.").count();
});

await step("unverified source is not public", async () => {
  const r = await (await fetch(`${BASE}/api/library/search?q=security%20deposit%20refund`)).json();
  expect(!r.results.some((x) => x.source.title === TITLE), "pending source leaked into search");
});

await step("a second person reviews and verifies it", async () => {
  await reviewer.getByLabel("Show").selectOption("?review_status=pending_review");
  await reviewer.getByRole("row", { name: new RegExp(TITLE.replace(/[()]/g, ".")) }).getByRole("button", { name: "Open" }).click();
  await reviewer.getByLabel("What did you check against the official source?").fill("Compared every section with the official file");
  await reviewer.getByRole("button", { name: "Verify" }).click();
  await reviewer.getByText("Source marked verified.").waitFor();
  await reviewer.screenshot({ path: `${SHOTS}/06-admin-source-review.png`, fullPage: true });
});

const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => errors.push(e.message));

await step("public search finds the section with highlights, metadata and official link", async () => {
  await page.goto(`${BASE}/library`);
  await page.getByLabel("Search the law").fill("refund security deposit");
  await page.getByRole("button", { name: "Search" }).click();
  const card = page.locator("article.result", { hasText: TITLE }).first();
  await card.waitFor();
  expect((await card.locator(".ref").textContent()) === "Section 3", "top section should be Section 3");
  expect((await card.locator("mark").count()) > 0, "no highlights");
  const href = await card.getByRole("link", { name: "View Original Source ↗" }).getAttribute("href");
  expect(href === `https://www.indiacode.nic.in/test-fixture/${run}`, `wrong official link ${href}`);
  await card.getByText("not been confirmed").waitFor();
  expect(page.url().includes("q=refund"), "query not in URL");
  await page.screenshot({ path: `${SHOTS}/07-library-search.png`, fullPage: true });
});

await step("source page shows full sections and jumps to the cited one", async () => {
  await page.locator("article.result", { hasText: TITLE }).first().getByRole("link", { name: TITLE }).click();
  await page.waitForURL(/\/library\/sources\/[0-9a-f-]{36}#s-/);
  await page.getByRole("heading", { name: TITLE, level: 1 }).waitFor();
  await page.getByRole("heading", { name: /Section 4 · Eviction only by order/ }).waitFor();
});

await step("My Legal Rights lists the verified source under its area", async () => {
  await page.goto(`${BASE}/rights`);
  const tile = page.locator("section.tile", { has: page.getByRole("heading", { name: "Property, land & tenancy" }) });
  await tile.getByRole("link", { name: TITLE }).waitFor();
});

await step("citation checker separates verified from unverifiable citations", async () => {
  await page.goto(`${BASE}/library`);
  await page.getByLabel("Text to check").fill(
    `Under Section 3 of ${TITLE} the deposit is refundable. Section 9 of the Made Up Rights Act, 2050 also applies. See (2099) 4 SCC 77.`,
  );
  await page.getByRole("button", { name: "Check citations" }).click();
  await page.getByText("Some citations could not be verified.").waitFor();
  const rows = await page.locator("#checker ~ div table tbody tr, section[aria-labelledby=checker] tbody tr").allTextContents();
  expect(rows.some((r) => r.includes("Section 3") && r.includes("Verified")), `rows: ${rows}`);
  expect(rows.filter((r) => r.includes("Cannot verify")).length === 2, `rows: ${rows}`);
});

await step("library and source pages fit a phone screen", async () => {
  const m = await browser.newContext({ viewport: { width: 375, height: 800 }, isMobile: true });
  const mp = await m.newPage();
  for (const p of ["/library?q=security+deposit", "/rights"]) {
    await mp.goto(BASE + p);
    await mp.waitForLoadState("networkidle");
    const overflow = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow <= 0, `${p} overflows by ${overflow}px`);
  }
  await mp.goto(`${BASE}/library?q=security+deposit`);
  await mp.locator("article.result").first().waitFor();
  await mp.screenshot({ path: `${SHOTS}/08-library-mobile.png`, fullPage: true });
  await m.close();
});

await browser.close();
for (const [s, n, why] of results) console.log(`${s}  ${n}${why ? `\n      ${why}` : ""}`);
console.log(`\n${results.filter((r) => r[0] === "PASS").length}/${results.length} journeys passed`);
if (errors.length) console.log("Browser errors:\n" + errors.join("\n"));
process.exit(results.some((r) => r[0] === "FAIL") || errors.length ? 1 : 0);

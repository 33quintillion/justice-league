// End-to-end check of the Phase 2 journeys in a real Chromium browser.
// Needs: API on :8000 (JUSTICE_ENV=development), web on :3000. Run: node e2e/run.mjs
// Grants the sysadmin role through the operator CLI, so it must run where the backend is installed.
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.env.WEB_URL ?? "http://localhost:3000";
const BACKEND_DIR = process.env.BACKEND_DIR ?? path.resolve(import.meta.dirname, "../../backend");
const SHOTS = path.resolve(import.meta.dirname, "screenshots");
mkdirSync(SHOTS, { recursive: true });

const run = Date.now();
const userEmail = `e2e-user-${run}@example.com`;
const adminEmail = `e2e-admin-${run}@example.com`;
const otherEmail = `e2e-other-${run}@example.com`;
const PASSWORD = "e2e password 12345";
const results = [];
const consoleErrors = [];

async function step(name, fn) {
  try {
    await fn();
    results.push(["PASS", name]);
  } catch (e) {
    results.push(["FAIL", name, e.message.split("\n")[0]]);
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };

async function register(page, email) {
  await page.goto(`${BASE}/register`);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByLabel(/I understand JUSTICE AI/).check();
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(`${BASE}/cases`);
}

async function verifyViaOutbox(page) {
  await page.goto(`${BASE}/dev/outbox`);
  const link = page.getByRole("link", { name: /verify-email\?token=/ }).first();
  await link.click();
  await page.getByText("Your email address is verified").waitFor();
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
page.on("pageerror", (e) => consoleErrors.push(e.message));

await step("home renders brand, 7 action tiles, disclaimer and emergency number", async () => {
  await page.goto(BASE);
  await page.getByRole("heading", { name: "Legal help that explains, not intimidates" }).waitFor();
  expect((await page.locator(".tile").count()) === 7, "expected 7 tiles");
  expect(await page.getByText("legal information, not legal advice").first().isVisible(), "disclaimer missing");
  expect(await page.locator('a[href="tel:112"]').first().isVisible(), "112 link missing");
  expect((await page.locator("nav[aria-label=Main] a").count()) === 12, "expected 12 nav items");
  await page.screenshot({ path: `${SHOTS}/01-home-desktop.png`, fullPage: true });
});

await step("skip link is the first keyboard stop and moves focus to main", async () => {
  await page.goto(BASE);
  await page.keyboard.press("Tab");
  const text = await page.evaluate(() => document.activeElement?.textContent);
  expect(text === "Skip to main content", `first focus was "${text}"`);
});

await step("unimplemented modules are honestly labelled, with no fake actions", async () => {
  for (const p of ["/ask", "/advocate", "/lawyer", "/judge", "/documents", "/find-lawyer"]) {
    await page.goto(BASE + p);
    await page.getByText("Not available yet").first().waitFor();
    expect((await page.locator("main form, main input, main textarea").count()) === 0, `${p} has inputs`);
  }
  await page.goto(`${BASE}/judge`);
  await page.getByText("Hypothetical AI legal analysis — not an actual judicial decision").waitFor();
});

await step("protected pages ask anonymous visitors to sign in", async () => {
  await page.goto(`${BASE}/cases`);
  await page.getByRole("heading", { name: "Please sign in" }).waitFor();
});

await step("registration shows validation errors from the server", async () => {
  await page.goto(`${BASE}/register`);
  await page.getByLabel("Email address").fill(`short-${run}@example.com`);
  await page.getByLabel("Password").evaluate((el) => el.removeAttribute("minlength"));
  await page.getByLabel("Password").fill("short");
  await page.getByLabel(/I understand JUSTICE AI/).check();
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByRole("alert").getByText("Please check the highlighted fields").waitFor();
});

await step("register, see verification banner, verify email via dev outbox", async () => {
  await register(page, userEmail);
  await page.getByText("Please verify your email address").waitFor();
  expect(await page.getByRole("button", { name: "New case" }).isDisabled(), "New case should be disabled before verification");
  await verifyViaOutbox(page);
  await page.goto(`${BASE}/cases`);
  expect(!(await page.getByRole("button", { name: "New case" }).isDisabled()), "New case still disabled");
});

let caseUrl = "";
await step("create a case, edit it and build a timeline", async () => {
  await page.getByRole("button", { name: "New case" }).click();
  await page.getByLabel("Short title").fill("Refund for defective washing machine");
  await page.getByLabel("Area of law").selectOption("consumer");
  await page.getByLabel("Where did this happen?").selectOption("IN-MH");
  await page.getByLabel(/What happened\?/).fill("Bought on 1 March. Stopped working on 5 March.");
  await page.getByRole("button", { name: "Create case" }).click();
  await page.waitForURL(/\/cases\/[0-9a-f-]{36}$/);
  caseUrl = page.url();
  await page.getByRole("heading", { name: "Refund for defective washing machine" }).waitFor();
  await page.getByLabel("Date", { exact: true }).fill("2026-03-05");
  await page.getByLabel("What happened", { exact: true }).fill("Machine stopped working");
  await page.getByRole("button", { name: "Add event" }).click();
  await page.getByText("Machine stopped working").waitFor();
  await page.getByLabel("Date", { exact: true }).fill("2026-03-01");
  await page.getByLabel("What happened", { exact: true }).fill("Purchased from store");
  await page.getByLabel("This is a deadline or hearing date").check();
  await page.getByRole("button", { name: "Add event" }).click();
  await page.getByText("Purchased from store").waitFor();
  const order = await page.locator(".timeline li div").allTextContents();
  expect(order[0] === "Purchased from store" && order[1] === "Machine stopped working", `timeline order ${order}`);
  await page.getByRole("button", { name: "Edit details" }).click();
  await page.getByLabel("Stage").selectOption("notice_sent");
  await page.getByRole("button", { name: "Save" }).click();
  await page.locator(".badge", { hasText: "Notice sent" }).waitFor();
  await page.screenshot({ path: `${SHOTS}/02-case-detail.png`, fullPage: true });
});

await step("free plan blocks a second open case with a clear message", async () => {
  await page.goto(`${BASE}/cases`);
  await page.getByRole("button", { name: "New case" }).click();
  await page.getByLabel("Short title").fill("Second matter");
  await page.getByLabel("Area of law").selectOption("employment");
  await page.getByRole("button", { name: "Create case" }).click();
  await page.getByText("Your plan allows 1 open case").waitFor();
});

await step("settings: switch to Hindi, choose a state, set consent; persists after reload", async () => {
  await page.goto(`${BASE}/settings`);
  await page.getByLabel("State or union territory").selectOption("IN-KA");
  await page.locator("form").first().getByLabel("Language").selectOption("hi");
  await page.getByRole("button", { name: "Save profile" }).click();
  await page.getByText("Profile saved.").waitFor();
  await page.getByLabel(/Allow JUSTICE AI to process/).check();
  await page.getByText("Consent saved.").waitFor();
  await page.reload();
  await page.getByRole("link", { name: "मेरे मामले" }).waitFor();
  expect((await page.getByLabel("State or union territory").inputValue()) === "IN-KA", "state not persisted");
  expect(await page.getByLabel(/Allow JUSTICE AI to process/).isChecked(), "consent not persisted");
  await page.screenshot({ path: `${SHOTS}/03-settings-hindi.png`, fullPage: true });
  await page.locator("form").first().getByLabel("Language").selectOption("en");
  await page.getByRole("button", { name: "Save profile" }).click();
  await page.getByRole("link", { name: "My Cases" }).waitFor();
});

await step("data export downloads JSON containing the case", async () => {
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Download my data (JSON)" }).click()]);
  const file = await dl.path();
  const data = JSON.parse((await import("node:fs")).readFileSync(file, "utf8"));
  expect(data.account.email === userEmail && data.cases.length === 1, "export content wrong");
});

await step("another user cannot open the first user's case URL", async () => {
  const ctx2 = await browser.newContext();
  const p2 = await ctx2.newPage();
  await register(p2, otherEmail);
  await p2.goto(caseUrl);
  await p2.getByText("Case not found.").waitFor();
  await ctx2.close();
});

await step("admin console: hidden for users, works for a sysadmin, audit shows actions", async () => {
  await page.goto(`${BASE}/admin`);
  await page.getByText("You do not have access to the admin console.").waitFor();
  const actx = await browser.newContext();
  const ap = await actx.newPage();
  ap.on("pageerror", (e) => consoleErrors.push(e.message));
  await register(ap, adminEmail);
  execFileSync("python3", ["-m", "app.cli", "grant-role", adminEmail, "sysadmin"], { cwd: BACKEND_DIR });
  execFileSync("python3", ["-m", "app.cli", "grant-role", adminEmail, "billing_admin"], { cwd: BACKEND_DIR });
  await ap.goto(`${BASE}/admin`);
  await ap.getByRole("heading", { name: "Admin console" }).waitFor();
  await ap.getByLabel("Search by email").fill(userEmail);
  await ap.getByRole("row", { name: new RegExp(userEmail) }).getByRole("button", { name: "Manage" }).click();
  const planForm = ap.locator("form", { has: ap.getByRole("button", { name: "Change plan" }) });
  await planForm.getByLabel("Plan").selectOption("premium");
  await planForm.getByLabel("Reason").fill("E2E pilot upgrade");
  await planForm.getByRole("button", { name: "Change plan" }).click();
  await ap.getByText("Saved and recorded in the audit log.").waitFor();
  const body = await ap.locator("main").textContent();
  expect(!body.includes("washing machine"), "admin can see case content!");
  await ap.getByRole("tab", { name: "Audit log" }).click();
  await ap.getByRole("cell", { name: "admin.subscription_changed" }).first().waitFor();
  await ap.getByRole("tab", { name: "System health" }).click();
  await ap.getByText("Schema revision").waitFor();
  await ap.screenshot({ path: `${SHOTS}/04-admin.png`, fullPage: true });
  await actx.close();
  // The upgrade takes effect for the user immediately.
  await page.goto(`${BASE}/cases`);
  await page.getByRole("button", { name: "New case" }).click();
  await page.getByLabel("Short title").fill("Second matter");
  await page.getByLabel("Area of law").selectOption("employment");
  await page.getByRole("button", { name: "Create case" }).click();
  await page.waitForURL(/\/cases\/[0-9a-f-]{36}$/);
});

await step("delete a case", async () => {
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete case" }).click();
  await page.waitForURL(`${BASE}/cases`);
  await page.getByRole("link", { name: "Second matter" }).waitFor({ state: "detached" });
});

await step("mobile layout: menu toggles, no horizontal scroll", async () => {
  const m = await browser.newContext({ viewport: { width: 375, height: 800 }, isMobile: true, hasTouch: true });
  const mp = await m.newPage();
  for (const p of ["/", "/cases", "/register", "/judge", "/legal-aid"]) {
    await mp.goto(BASE + p);
    await mp.waitForLoadState("networkidle");
    const overflow = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow <= 0, `${p} overflows by ${overflow}px`);
  }
  await mp.goto(BASE);
  expect(!(await mp.locator("#sidenav").isVisible()), "nav should start hidden on mobile");
  await mp.getByRole("button", { name: /Menu/ }).click();
  await mp.getByRole("link", { name: "AI Judge" }).click();
  await mp.waitForURL(`${BASE}/judge`);
  expect(!(await mp.locator("#sidenav").isVisible()), "nav should close after navigating");
  await mp.goto(BASE);
  await mp.screenshot({ path: `${SHOTS}/05-home-mobile.png`, fullPage: true });
  await m.close();
});

await step("sign out of all devices, then delete account", async () => {
  await page.goto(`${BASE}/settings`);
  await page.getByRole("button", { name: "Sign out of all devices" }).click();
  await page.waitForURL(`${BASE}/login`);
  await page.getByLabel("Email address").fill(userEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(`${BASE}/cases`);
  await page.goto(`${BASE}/settings`);
  const del = page.locator("form", { has: page.getByRole("button", { name: "Delete my account" }) });
  await del.getByLabel("Password").fill(PASSWORD);
  await del.getByLabel("Type DELETE MY ACCOUNT to confirm").fill("DELETE MY ACCOUNT");
  await del.getByRole("button", { name: "Delete my account" }).click();
  await page.waitForURL(`${BASE}/`);
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email address").fill(userEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByText("Email or password is incorrect").waitFor();
});

await browser.close();

// 401s from /api/auth/me on anonymous pages are expected; anything else is a defect.
const unexpected = consoleErrors.filter((e) => !/401|403|402|404|422|Failed to load resource/.test(e));
for (const [s, n, why] of results) console.log(`${s}  ${n}${why ? `\n      ${why}` : ""}`);
console.log(`\n${results.filter((r) => r[0] === "PASS").length}/${results.length} journeys passed`);
if (unexpected.length) console.log("Unexpected browser errors:\n" + unexpected.join("\n"));
process.exit(results.some((r) => r[0] === "FAIL") || unexpected.length ? 1 : 0);

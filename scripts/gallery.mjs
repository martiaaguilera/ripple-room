// Devpost / README gallery: node ../../scripts/gallery.mjs <outdir> [baseUrl]  (run from apps/web so @playwright/test resolves)
// App shots come from whatever server baseUrl points at; in mock mode the UI itself says "Simulated agent".
import { readFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// Resolve Playwright from the current directory (apps/web), not from this file's folder.
const { chromium } = createRequire(path.join(process.cwd(), "package.json"))("@playwright/test");

const out = path.resolve(process.argv[2] ?? "gallery");
const base = process.argv[3] ?? "http://localhost:8000";
const src = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "docs", "submission", "gallery", "src");

const browser = await chromium.launch();
const settle = (page, ms = 1800) => page.waitForTimeout(ms);

async function desktop() {
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  await page.goto(base + "/");
  const start = page.getByRole("button", { name: /What if the truck arrives/ });
  await start.waitFor();
  await settle(page, 2600);
  await page.screenshot({ path: `${out}/01-plan.png` });
  await start.click();
  await page.getByRole("heading", { name: /Doors \d+ min late/ }).waitFor();
  await settle(page, 2200);
  await page.screenshot({ path: `${out}/02-ripple.png` });
  await page.getByRole("region", { name: /How it spreads/i }).or(page.getByText("How it spreads")).first().scrollIntoViewIfNeeded();
  await settle(page, 1200);
  await page.screenshot({ path: `${out}/03-spread.png` });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("button", { name: "Find recovery options" }).click();
  await page.getByRole("button", { name: "Apply this plan" }).waitFor({ timeout: 90_000 });
  await settle(page, 1500);
  await page.screenshot({ path: `${out}/04-verified-options.png` });
  await page.getByRole("button", { name: "Apply this plan" }).click();
  await page.getByRole("heading", { name: "Recovery applied" }).waitFor();
  await settle(page, 1500);
  await page.screenshot({ path: `${out}/05-applied.png` });
  await page.close();
}

async function phone() {
  const shots = [];
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await page.goto(base + "/");
  await page.getByRole("button", { name: /What if the truck arrives/ }).waitFor();
  await settle(page, 2600);
  shots.push(`${out}/phone-a.png`);
  await page.screenshot({ path: shots[0] });
  await page.getByRole("button", { name: /What if the truck arrives/ }).click();
  await page.getByRole("heading", { name: /Doors \d+ min late/ }).waitFor();
  await settle(page, 2200);
  shots.push(`${out}/phone-b.png`);
  await page.screenshot({ path: shots[1] });
  await page.close();
  // Side by side on one 3:2 canvas.
  const frame = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  const img = (p) =>
    `<img src="data:image/png;base64,${readFileSync(p).toString("base64")}" style="height:844px;border-radius:28px;border:1px solid #344657">`;
  await frame.setContent(
    `<body style="margin:0;background:#090d13;display:flex;gap:64px;justify-content:center;align-items:center;height:960px">${img(shots[0])}${img(shots[1])}</body>`,
  );
  await frame.waitForLoadState("load");
  await frame.screenshot({ path: `${out}/06-phone.png` });
  await frame.close();
  for (const p of shots) rmSync(p);
}

async function rendered(name, file) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  await page.goto(pathToFileURL(path.join(src, file)).href);
  await page.screenshot({ path: `${out}/${name}` });
  await page.close();
}

await desktop();
await phone();
await rendered("07-architecture.png", "architecture.html");
await rendered("08-evaluation.png", "evaluation.html");
await browser.close();
console.log(`gallery written to ${out}`);

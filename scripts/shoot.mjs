// Visual QA journey: node scripts/shoot.mjs <outdir> [baseUrl]  (run from apps/web so @playwright/test resolves)
import { chromium } from "@playwright/test";
const out = process.argv[2] ?? "shots";
const base = process.argv[3] ?? "http://localhost:3000";
const browser = await chromium.launch();
async function journey(name, viewport) {
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(base + "/");
  await page.getByRole("button", { name: /What if the truck arrives/ }).waitFor();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${out}/${name}-1-ready.png`, fullPage: true });
  await page.getByLabel("Describe the incident").fill("Driver called: stuck on the ring road, 35 more minutes. No extra spend today.");
  await page.getByRole("button", { name: "Read the incident" }).click();
  await page.getByRole("button", { name: /Apply to the plan/ }).waitFor();
  await page.screenshot({ path: `${out}/${name}-2-intake.png`, fullPage: true });
  await page.getByRole("button", { name: /Apply to the plan/ }).click();
  await page.getByRole("heading", { name: /Doors \d+ min late/ }).waitFor();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${out}/${name}-3-impact.png`, fullPage: true });
  await page.getByRole("button", { name: "Find recovery options" }).click();
  await page.getByRole("button", { name: "Apply this plan" }).waitFor({ timeout: 90000 });
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${out}/${name}-4-options.png`, fullPage: true });
  await page.getByRole("button", { name: "Apply this plan" }).click();
  await page.getByRole("heading", { name: "Recovery applied" }).waitFor();
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${out}/${name}-5-applied.png`, fullPage: true });
  console.log(name, "console errors:", errors.length ? errors : "none");
  await page.close();
}
await journey("desktop", { width: 1440, height: 900 });
await journey("mobile", { width: 390, height: 844 });
await browser.close();

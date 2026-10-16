// Screenshot journey driver for visual QA: node scripts/shoot.mjs <outdir> [baseUrl]
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
  await page.getByRole("heading", { name: "Break the plan" }).waitFor();
  await page.screenshot({ path: `${out}/${name}-1-ready.png`, fullPage: true });
  await page.getByRole("button", { name: /Truck delayed \+35/ }).click();
  await page.getByText(/min late/).first().waitFor();
  await page.waitForTimeout(1600);
  await page.screenshot({ path: `${out}/${name}-2-impact.png`, fullPage: true });
  await page.getByRole("button", { name: "Find recovery options" }).click();
  await page.getByRole("button", { name: "Apply this plan" }).waitFor({ timeout: 60000 });
  await page.screenshot({ path: `${out}/${name}-3-options.png`, fullPage: true });
  await page.getByRole("button", { name: "Apply this plan" }).click();
  await page.getByRole("heading", { name: "Recovery applied" }).waitFor();
  await page.screenshot({ path: `${out}/${name}-4-applied.png`, fullPage: true });
  console.log(name, "console errors:", errors.length ? errors : "none");
  await page.close();
}
await journey("desktop", { width: 1440, height: 900 });
await journey("mobile", { width: 390, height: 844 });
await browser.close();

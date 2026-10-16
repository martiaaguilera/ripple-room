import { expect, test, type Page } from "@playwright/test";

const lateHeading = (page: Page) => page.getByRole("heading", { name: /Doors \d+ min late/ });
const startButton = (page: Page) => page.getByRole("button", { name: "What if the truck arrives 35 minutes late?" });

test.describe("control room journey", () => {
  test("first screen explains itself: scene, deadline, one obvious action", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("img", { name: /Illustrative venue scene/ })).toBeVisible();
    await expect(page.getByText("Doors are ready at 17:40, 20 minutes to spare.")).toBeVisible();
    await expect(startButton(page)).toBeVisible();
    await expect(page.getByText("Simulated agent, no model calls")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Progress" })).toContainText("See the plan");
  });

  test("shock → narrated consequences → recover → verdicts → apply → undo → reset", async ({ page }) => {
    await page.goto("/");
    await startButton(page).click();
    await expect(page.getByRole("heading", { name: "Doors 15 min late" })).toBeVisible();
    await expect(page.getByText("The truck arrives at 14:35 instead of 14:00.")).toBeVisible();
    await expect(page.getByText("Doors would be ready at 18:15, 15 minutes after the 18:00 opening.")).toBeVisible();
    await expect(startButton(page)).toHaveCount(0);

    await page.getByRole("button", { name: "Find recovery options" }).click();
    await expect(page.getByText(/of \d+ proposals hold/)).toBeVisible();
    const verdicts = page.getByRole("list", { name: "Verifier verdicts" });
    await expect(verdicts).toContainText("rejected");
    await expect(verdicts).toContainText("does not touch what sets the doors time");
    const apply = page.getByRole("button", { name: "Apply this plan" });
    await expect(apply).toBeVisible();
    await expect(page.getByText("With the selected recovery")).toBeVisible();

    await apply.click();
    await expect(page.getByRole("heading", { name: "Recovery applied" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Who needs to know" })).toBeVisible();
    await expect(page.getByText(/tell by \d\d:\d\d/).first()).toBeVisible();

    await page.getByRole("button", { name: "Undo" }).first().click();
    await expect(page.getByRole("heading", { name: "Doors 15 min late" })).toBeVisible();

    await page.getByRole("button", { name: "Reset" }).click();
    await expect(startButton(page)).toBeVisible();
  });

  test("plain-language incident is confirmed before it changes anything", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Describe the incident").fill("The truck is stuck in traffic, 35 more minutes. No extra spend today.");
    await page.getByRole("button", { name: "Read the incident" }).click();
    await expect(page.getByText(/Truck arrives 35 min late/)).toBeVisible();
    await expect(page.getByText("Extra spend: protect")).toBeVisible();
    await expect(startButton(page)).toBeVisible();
    await page.getByRole("button", { name: "Apply to the plan" }).click();
    await expect(lateHeading(page)).toBeVisible();
    await expect(page.getByRole("radio", { name: "Protect" }).nth(1)).toBeChecked();
  });

  test("priorities change the ranking deterministically", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Truck delayed \+35/ }).click();
    await expect(lateHeading(page)).toBeVisible();
    await page.getByText("Protect").nth(1).click(); // Extra spend: protect
    await page.getByRole("button", { name: "Or run the playbook search without AI" }).click();
    await expect(page.locator("article").first()).toContainText("€0");
  });

  test("impossible incident is reported honestly", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Truck breakdown \+90/ }).click();
    await expect(lateHeading(page)).toBeVisible();
    await page.getByRole("button", { name: "Or run the playbook search without AI" }).click();
    await expect(page.getByText("No verified recovery found.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Apply this plan" })).toHaveCount(0);
  });

  test("absorbed delay needs no recovery", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Dock access delayed/ }).click();
    await expect(page.getByRole("heading", { name: "Delay absorbed" })).toBeVisible();
    await expect(page.getByText(/Doors are ready at 17:55, 5 minutes to spare/)).toBeVisible();
  });

  test("no horizontal page overflow", async ({ page }) => {
    await page.goto("/");
    await startButton(page).click();
    await expect(lateHeading(page)).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test("reduced motion: no ripple ring, scene shows the whole day, meaning intact", async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    await page.goto("/");
    await startButton(page).click();
    await expect(page.getByText("Doors would be ready at 18:15, 15 minutes after the 18:00 opening.")).toBeVisible();
    await expect(page.locator("circle.ripple-ring").first()).toBeHidden();
    await expect(page.getByRole("button", { name: "Replay the day" })).toBeVisible();
    await context.close();
  });
});

import { expect, test, type Page } from "@playwright/test";

const lateHeading = (page: Page) => page.getByRole("heading", { name: /Doors \d+ min late/ });

test.describe("control room journey", () => {
  test("hero → shock → recover → preview → apply → undo → reset", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /One late truck/ })).toBeVisible();
    await expect(page.getByText("Simulated agent, no model calls")).toBeVisible();
    await expect(page.getByText("20 min to spare")).toBeVisible();

    await page.getByRole("button", { name: "Delay the truck 35 min" }).click();
    await expect(page.getByRole("heading", { name: "Doors 15 min late" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /One late truck/ })).toHaveCount(0);

    await page.getByRole("button", { name: "Find recovery options" }).click();
    await expect(page.getByText(/of \d+ proposals hold/)).toBeVisible();
    const apply = page.getByRole("button", { name: "Apply this plan" });
    await expect(apply).toBeVisible();
    await expect(page.getByText("With this option")).toBeVisible();

    await apply.click();
    await expect(page.getByRole("heading", { name: "Recovery applied" })).toBeVisible();

    await page.getByRole("button", { name: "Undo" }).first().click();
    await expect(page.getByRole("heading", { name: "Doors 15 min late" })).toBeVisible();

    await page.getByRole("button", { name: "Reset" }).click();
    await expect(page.getByRole("heading", { name: "The plan holds" })).toBeVisible();
  });

  test("plain-language incident is confirmed before it changes anything", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Describe the incident").fill("The truck is stuck in traffic, 35 more minutes. No extra spend today.");
    await page.getByRole("button", { name: "Read the incident" }).click();
    await expect(page.getByText(/Truck arrives 35 min late/)).toBeVisible();
    await expect(page.getByText("Extra spend: protect")).toBeVisible();
    await expect(page.getByRole("heading", { name: "The plan holds" })).toBeVisible();
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
    const first = page.locator("article").first();
    await expect(first).toContainText("€0");
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
    await expect(page.getByText("5 min to spare")).toBeVisible();
  });

  test("no horizontal page overflow", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Truck delayed \+35/ }).click();
    await expect(lateHeading(page)).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test("reduced motion hides the ripple ring but keeps the meaning", async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    await page.goto("/");
    await page.getByRole("button", { name: /Truck delayed \+35/ }).click();
    await expect(page.getByText("15 min late").first()).toBeVisible();
    await expect(page.locator("circle.ripple-ring").first()).toBeHidden();
    await context.close();
  });
});

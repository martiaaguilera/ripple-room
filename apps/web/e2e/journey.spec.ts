import { expect, test } from "@playwright/test";

test.describe("control room journey", () => {
  test("shock → recover → preview → apply → undo → reset", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "The plan holds" })).toBeVisible();
    await expect(page.getByText("Simulated agent, no model calls")).toBeVisible();
    await expect(page.getByText("20 min to spare")).toBeVisible();

    await page.getByRole("button", { name: /Truck delayed \+35/ }).click();
    await expect(page.getByRole("heading", { name: "Doors 15 min late" })).toBeVisible();
    await expect(page.getByText("If nobody acts")).toBeVisible();

    await page.getByRole("button", { name: "Find recovery options" }).click();
    await expect(page.getByText(/Does not fit/).first()).toBeVisible();
    const apply = page.getByRole("button", { name: "Apply this plan" });
    await expect(apply).toBeVisible();
    await expect(page.getByText("With this option")).toBeVisible();

    await apply.click();
    await expect(page.getByRole("heading", { name: "Recovery applied" })).toBeVisible();
    await expect(page.getByText("Current plan")).toBeVisible();

    await page.getByRole("button", { name: "Undo" }).first().click();
    await expect(page.getByRole("heading", { name: "Doors 15 min late" })).toBeVisible();

    await page.getByRole("button", { name: "Reset" }).click();
    await expect(page.getByRole("heading", { name: "The plan holds" })).toBeVisible();
  });

  test("impossible incident is reported honestly", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Truck breakdown \+90/ }).click();
    await expect(page.getByRole("heading", { name: /Doors \d+ min late/ })).toBeVisible();
    await page.getByRole("button", { name: "Or run the solver search without AI" }).click();
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
    await expect(page.getByText("If nobody acts")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test("reduced motion hides the ripple ring but keeps the meaning", async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    await page.goto("/");
    await page.getByRole("button", { name: /Truck delayed \+35/ }).click();
    await expect(page.getByText("15 min late").first()).toBeVisible();
    const ring = page.locator("circle.ripple-ring").first();
    await expect(ring).toBeHidden();
    await context.close();
  });
});

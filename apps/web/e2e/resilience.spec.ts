import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

/**
 * Failure states and keyboard access. Every AI failure is faked with page.route, so no model is
 * ever called; deterministic endpoints (shock, search, notice, apply) hit the real mock-mode API.
 */

const startButton = (page: Page) => page.getByRole("button", { name: "What if the truck arrives 35 minutes late?" });
const lateHeading = (page: Page) => page.getByRole("heading", { name: "Doors 15 min late" });
const playbookLink = (page: Page) => page.getByRole("button", { name: "Or run the playbook search without AI" });
const applyButton = (page: Page) => page.getByRole("button", { name: "Apply this plan" });
const revisionLabel = (page: Page) => page.getByText(/^Revision \S+ \(\d+\)$/);

type AiStatus = "live" | "paused" | "budget_exhausted";

/** Serve the real /api/health with the AI block replaced, as a live deployment would report it. */
async function fakeHealth(page: Page, status: AiStatus) {
  await page.route("**/api/health", async (route: Route) => {
    const response = await route.fetch();
    const body = (await response.json()) as { ai: Record<string, unknown> };
    body.ai = { ...body.ai, mode: "live", status, provider: "nebius-token-factory", configured: true };
    await route.fulfill({ response, json: body });
  });
}

/** Record every call to an AI endpoint, so a test can prove none happened. */
function aiCalls(page: Page): string[] {
  const calls: string[] = [];
  page.on("request", (r) => {
    if (/\/api\/(recover|interpret)$/.test(new URL(r.url()).pathname)) calls.push(r.url());
  });
  return calls;
}

async function shockTruck(page: Page) {
  await page.goto("/");
  await startButton(page).click();
  await expect(lateHeading(page)).toBeVisible();
}

async function playbookWorksAndApplies(page: Page) {
  await expect(page.getByText("Standard fix from the playbook search, verified").first()).toBeVisible();
  await applyButton(page).click();
  await expect(page.getByRole("heading", { name: "Recovery applied" })).toBeVisible();
}

test.describe("live AI unavailable: explained, recoverable", () => {
  const blocked = [
    { status: "paused" as const, badge: "Live AI paused", why: "Live AI is paused by the operator." },
    { status: "budget_exhausted" as const, badge: "Today's live AI budget used", why: "Today's live AI budget is used up" },
  ];

  for (const c of blocked) {
    test(`health reports ${c.status}: AI action disabled with a reason, playbook still recovers`, async ({ page }) => {
      const calls = aiCalls(page);
      await fakeHealth(page, c.status);
      await shockTruck(page);
      await expect(page.getByText(c.badge)).toBeVisible();
      await expect(page.getByRole("button", { name: "Find recovery options" })).toBeDisabled();
      const reason = page.getByRole("status").filter({ hasText: c.why });
      await expect(reason).toContainText("The playbook search below still finds and verifies recoveries, without AI.");
      await playbookLink(page).click();
      await playbookWorksAndApplies(page);
      expect(calls).toEqual([]);
    });
  }

  const refusals = [
    { code: "AI_PAUSED", message: "Live AI is paused by the operator. The playbook search (no AI) still works." },
    { code: "AI_BUDGET_EXHAUSTED", message: "Today's live AI budget is used up. The playbook search (no AI) still works." },
    { code: "MODEL_UNAVAILABLE", message: "Nebius returned 503: model overloaded." },
  ];

  for (const r of refusals) {
    test(`recover refused with ${r.code}: message shown, nothing changed, playbook recovers`, async ({ page }) => {
      await fakeHealth(page, "live");
      await page.route("**/api/recover", (route) =>
        route.fulfill({ status: 503, json: { error: { code: r.code, message: r.message, details: null } } }),
      );
      await shockTruck(page);
      const before = await revisionLabel(page).textContent();
      await page.getByRole("button", { name: "Find recovery options" }).click();

      const alert = page.getByRole("alert").filter({ hasText: "The recovery agent could not finish." });
      await expect(alert).toContainText(r.message);
      await expect(lateHeading(page)).toBeVisible();
      await expect(revisionLabel(page)).toHaveText(before!);
      await expect(applyButton(page)).toHaveCount(0);
      // Nothing from a failed run is ever presented as a Nemotron proposal.
      await expect(page.getByText(/Nemotron's own first choice|Nemotron listed it/)).toHaveCount(0);

      await alert.getByRole("button", { name: "Run the playbook search without AI" }).click();
      await playbookWorksAndApplies(page);
    });
  }

  test("incident reader refused: error explained, rehearsed incidents still work", async ({ page }) => {
    await fakeHealth(page, "live");
    await page.route("**/api/interpret", (route) =>
      route.fulfill({
        status: 503,
        json: { error: { code: "AI_PAUSED", message: "Live AI is paused by the operator.", details: null } },
      }),
    );
    await page.goto("/");
    await page.getByLabel("Describe the incident").fill("The truck is 35 minutes late.");
    await page.getByRole("button", { name: "Read the incident" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Live AI is paused" })).toHaveText(
      "Live AI is paused by the operator. Use a rehearsed incident below instead.",
    );
    await page.getByRole("button", { name: /Truck delayed \+35/ }).click();
    await expect(lateHeading(page)).toBeVisible();
  });
});

test.describe("recovery stream breaks: the run ends visibly and nothing changes", () => {
  test("network drop before the stream opens shows a plain-language reason", async ({ page }) => {
    await page.route("**/api/recover", (route) => route.abort("internetdisconnected"));
    await shockTruck(page);
    await page.getByRole("button", { name: "Find recovery options" }).click();
    const alert = page.getByRole("alert").filter({ hasText: "The recovery agent could not finish." });
    await expect(alert).toContainText("Cannot reach the Ripple Room server. Check your connection and retry.");
    await expect(alert).not.toContainText("Failed to fetch");
    await alert.getByRole("button", { name: "Run the playbook search without AI" }).click();
    await playbookWorksAndApplies(page);
  });

  test("stream that closes without a done event is reported, not left spinning", async ({ page }) => {
    await page.route("**/api/recover", async (route) => {
      const response = await route.fetch();
      const full = await response.text();
      // Keep only the opening frames, as if a proxy or platform timeout cut the connection mid-run.
      const cut = full.slice(0, full.indexOf("event: tool_result"));
      expect(cut).toContain("event: run_started");
      await route.fulfill({ response, body: cut });
    });
    await shockTruck(page);
    const before = await revisionLabel(page).textContent();
    await page.getByRole("button", { name: "Find recovery options" }).click();
    const alert = page.getByRole("alert").filter({ hasText: "The recovery agent could not finish." });
    await expect(alert).toContainText("The connection closed before the run finished");
    await expect(page.getByText("Waiting for the next step…")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Undo" })).toBeEnabled();
    await expect(revisionLabel(page)).toHaveText(before!);
    await alert.getByRole("button", { name: "Run the playbook search without AI" }).click();
    await playbookWorksAndApplies(page);
  });
});

test.describe("apply fails in transit: banner shown, plan unchanged, retry works", () => {
  const failures: { name: string; banner: RegExp; fail: (route: Route) => Promise<void> }[] = [
    {
      name: "network drop",
      banner: /Something went wrong\.\s*Cannot reach the Ripple Room server/,
      fail: (route) => route.abort("internetdisconnected"),
    },
    {
      name: "stale revision (409)",
      banner: /That option is out of date\.\s*This option was computed for an older revision/,
      fail: (route) =>
        route.fulfill({
          status: 409,
          json: {
            error: {
              code: "STALE_REVISION",
              message: "This option was computed for an older revision. Re-run recovery.",
              details: null,
            },
          },
        }),
    },
    {
      name: "proxy error page (502, not JSON)",
      banner: /Something went wrong\.\s*Request failed \(502\)\./,
      fail: (route) => route.fulfill({ status: 502, contentType: "text/html", body: "<h1>Bad gateway</h1>" }),
    },
  ];

  for (const f of failures) {
    test(f.name, async ({ page }) => {
      await shockTruck(page);
      await playbookLink(page).click();
      await expect(applyButton(page)).toBeVisible();
      const before = await revisionLabel(page).textContent();

      await page.route("**/api/apply", f.fail);
      await applyButton(page).click();

      const banner = page.getByRole("alert").filter({ hasText: f.banner });
      await expect(banner).toBeVisible();
      await expect(page.getByRole("heading", { name: "Recovery applied" })).toHaveCount(0);
      await expect(lateHeading(page)).toBeVisible();
      await expect(revisionLabel(page)).toHaveText(before!);
      await expect(applyButton(page)).toBeEnabled();

      await page.unroute("**/api/apply");
      await applyButton(page).click();
      await expect(page.getByRole("heading", { name: "Recovery applied" })).toBeVisible();
      await expect(banner).toHaveCount(0);
      await expect(revisionLabel(page)).not.toHaveText(before!);
    });
  }
});

/** Press Tab until `target` has focus (wrapping round the page if needed). */
async function tabTo(page: Page, target: Locator, max = 250) {
  for (let i = 0; i < max; i++) {
    if (await target.evaluate((el) => el === document.activeElement).catch(() => false)) return;
    await page.keyboard.press("Tab");
  }
  throw new Error(`Tab never reached ${target.toString()}`);
}

/** The focused element shows a visible focus ring (keyboard focus, not colour of the control alone). */
async function expectVisibleFocus(target: Locator) {
  await expect(target).toBeFocused();
  const ring = await target.evaluate((el) => {
    const s = getComputedStyle(el);
    return { visible: el.matches(":focus-visible"), style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
  });
  expect(ring.visible).toBe(true);
  expect(ring.style).not.toBe("none");
  expect(ring.width).toBeGreaterThanOrEqual(2);
}

test("keyboard only: start, find options, pick a card, apply, undo, with visible focus", async ({ page }) => {
  await page.goto("/");
  await expect(startButton(page)).toBeVisible();

  await tabTo(page, startButton(page));
  await expectVisibleFocus(startButton(page));
  await page.keyboard.press("Enter");
  await expect(lateHeading(page)).toBeVisible();

  const find = page.getByRole("button", { name: "Find recovery options" });
  await tabTo(page, find);
  await expectVisibleFocus(find);
  await page.keyboard.press("Enter");

  const cards = page.locator("article button[aria-pressed]");
  await expect(cards.first()).toBeVisible();
  const target = (await cards.count()) > 1 ? cards.nth(1) : cards.first();
  await tabTo(page, target);
  await expectVisibleFocus(target);
  if ((await target.getAttribute("aria-pressed")) !== "true") await page.keyboard.press("Enter");
  await expect(target).toHaveAttribute("aria-pressed", "true");

  await tabTo(page, applyButton(page));
  await expectVisibleFocus(applyButton(page));
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Recovery applied" })).toBeVisible();

  const undo = page.getByRole("button", { name: "Undo" }).last();
  await tabTo(page, undo);
  await expectVisibleFocus(undo);
  await page.keyboard.press("Enter");
  await expect(lateHeading(page)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recovery applied" })).toHaveCount(0);
});

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * Automated accessibility gate, run on every journey state on desktop and mobile.
 *
 * 1. axe-core (WCAG 2.0/2.1/2.2 A+AA and best-practice rules): any serious or critical
 *    violation fails the test. Lower-impact findings are attached as annotations.
 * 2. Every interactive control is reachable with Tab alone and exposes a non-empty accessible
 *    name in the browser's accessibility tree (read through CDP: what a screen reader gets).
 *
 * Mock agent only: AI failures are faked with page.route, nothing calls a model.
 */

const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];
const BLOCKING = new Set(["serious", "critical"]);

const startButton = (page: Page) => page.getByRole("button", { name: "What if the truck arrives 35 minutes late?" });
const lateHeading = (page: Page) => page.getByRole("heading", { name: "Doors 15 min late" });
const applyButton = (page: Page) => page.getByRole("button", { name: "Apply this plan" });

/** Wait for finite CSS animations (fades, ripples) to end so contrast is measured on final colours. */
async function settle(page: Page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().endTime !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  );
}

async function blockingViolations(page: Page): Promise<string[]> {
  await settle(page);
  const { violations } = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
  for (const v of violations.filter((x) => !BLOCKING.has(x.impact ?? ""))) {
    test.info().annotations.push({ type: `axe ${v.impact}`, description: `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}` });
  }
  return violations
    .filter((v) => BLOCKING.has(v.impact ?? ""))
    .flatMap((v) => v.nodes.map((n) => `[${v.impact}] ${v.id} at ${n.target.join(" ")}: ${n.failureSummary?.replace(/\s+/g, " ")}`));
}

// ---- journey states --------------------------------------------------------------------------

async function firstScreen(page: Page) {
  await page.goto("/");
  await expect(startButton(page)).toBeVisible();
}

async function afterTruck(page: Page) {
  await firstScreen(page);
  await startButton(page).click();
  await expect(lateHeading(page)).toBeVisible();
}

async function optionsListed(page: Page) {
  await afterTruck(page);
  await page.getByRole("button", { name: "Find recovery options" }).click();
  // The mock agent still runs CP-SAT on every proposal: allow for CPU contention.
  await expect(page.getByText(/of \d+ proposals hold/)).toBeVisible({ timeout: 15_000 });
  await expect(applyButton(page)).toBeVisible();
}

async function recoveryApplied(page: Page) {
  await optionsListed(page);
  await applyButton(page).click();
  await expect(page.getByRole("heading", { name: "Recovery applied" })).toBeVisible();
  // Open the collapsed incident desk too, so its controls are audited as well.
  await page.getByText("Add another incident").click();
  await expect(page.getByLabel("Describe the incident")).toBeVisible();
}

/** Live AI reported available, then the recover call is refused: the error banner and playbook path. */
async function aiRefused(page: Page) {
  await page.route("**/api/health", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as { ai: Record<string, unknown> };
    body.ai = { ...body.ai, mode: "live", status: "live", provider: "nebius-token-factory", configured: true };
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/recover", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { code: "AI_BUDGET_EXHAUSTED", message: "Today's live AI budget is used up. The playbook search (no AI) still works.", details: null } },
    }),
  );
  await afterTruck(page);
  await page.getByRole("button", { name: "Find recovery options" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "The recovery agent could not finish." })).toContainText("Today's live AI budget is used up");
}

const STATES: { name: string; reach: (page: Page) => Promise<void> }[] = [
  { name: "first screen", reach: firstScreen },
  { name: "after the truck incident", reach: afterTruck },
  { name: "options listed (mock run)", reach: optionsListed },
  { name: "recovery applied", reach: recoveryApplied },
  { name: "live AI refused (error banner)", reach: aiRefused },
];

// ---- control inventory -----------------------------------------------------------------------

declare global {
  interface Window {
    __a11yReached?: string[];
  }
}

/**
 * Tag every rendered, enabled control: anything in the sequential focus order (tabIndex >= 0)
 * plus anything that claims an interactive role (so a role="button" with tabindex=-1 shows up as
 * unreachable). Radios sharing a name are one Tab stop, so they share a group.
 */
async function tagControls(page: Page): Promise<number> {
  return page.evaluate(() => {
    const ROLES = new Set(["button", "link", "checkbox", "radio", "slider", "spinbutton", "switch", "tab", "menuitem", "option", "combobox", "textbox", "searchbox"]);
    let n = 0;
    for (const el of Array.from(document.querySelectorAll<HTMLElement | SVGElement>("*"))) {
      el.removeAttribute("data-a11y-i");
      el.removeAttribute("data-a11y-group");
      const role = el.getAttribute("role");
      if (el.tabIndex < 0 && !(role && ROLES.has(role))) continue;
      if ("disabled" in el && el.disabled === true) continue;
      if (el.closest("[inert]") || !el.checkVisibility({ checkVisibilityCSS: true })) continue;
      const closed = el.closest("details:not([open])");
      if (closed && el.closest("summary")?.parentElement !== closed) continue;
      const radio = el instanceof HTMLInputElement && el.type === "radio" && el.name;
      el.setAttribute("data-a11y-i", String(n));
      el.setAttribute("data-a11y-group", radio ? `radio:${el.name}` : `el:${n}`);
      n += 1;
    }
    return n;
  });
}

/** Press Tab from the top of the document until the focus order has wrapped; return groups reached. */
async function tabWalk(page: Page, controls: number): Promise<Set<string>> {
  await page.evaluate(() => {
    window.__a11yReached = [];
    document.addEventListener(
      "focusin",
      (e) => {
        const group = e.target instanceof Element ? e.target.getAttribute("data-a11y-group") : null;
        if (group) window.__a11yReached?.push(group);
      },
      true,
    );
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  for (let i = 0; i < controls * 2 + 5; i += 1) await page.keyboard.press("Tab");
  return new Set(await page.evaluate(() => window.__a11yReached ?? []));
}

type AxControl = { group: string; role: string; name: string; html: string };

/** Role and accessible name of every tagged control, as Chromium's accessibility tree exposes them. */
async function accessibleControls(page: Page): Promise<AxControl[]> {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("DOM.enable");
  await cdp.send("Accessibility.enable");
  const { root } = await cdp.send("DOM.getDocument", { depth: 0 });
  const { nodeIds } = await cdp.send("DOM.querySelectorAll", { nodeId: root.nodeId, selector: "[data-a11y-i]" });
  const out: AxControl[] = [];
  for (const nodeId of nodeIds) {
    const { nodes } = await cdp.send("Accessibility.getPartialAXTree", { nodeId, fetchRelatives: false });
    const ax = nodes[0];
    const { attributes } = await cdp.send("DOM.getAttributes", { nodeId });
    const { outerHTML } = await cdp.send("DOM.getOuterHTML", { nodeId });
    out.push({
      group: attributes[attributes.indexOf("data-a11y-group") + 1] ?? "",
      role: ax?.ignored ? "(ignored)" : String(ax?.role?.value ?? ""),
      name: String(ax?.name?.value ?? "").trim(),
      html: outerHTML.replace(/\s+/g, " ").slice(0, 140),
    });
  }
  await cdp.detach();
  return out;
}

const NAMED_ROLES = new Set(["button", "link", "checkbox", "radio", "slider", "spinbutton", "switch", "tab", "menuitem", "option", "combobox", "textbox", "searchbox", "region", "DisclosureTriangle"]);

/** Problems with the current page's controls: unreachable by Tab, no accessible name, or no role. */
async function controlProblems(page: Page): Promise<{ problems: string[]; controls: AxControl[] }> {
  const count = await tagControls(page);
  const controls = await accessibleControls(page);
  const reached = await tabWalk(page, count);
  const problems: string[] = [];
  for (const c of controls) {
    if (!reached.has(c.group)) problems.push(`not reachable with Tab: ${c.html}`);
    if (!c.name) problems.push(`no accessible name (role ${c.role || "none"}): ${c.html}`);
    if (!NAMED_ROLES.has(c.role)) problems.push(`not exposed as a control (role ${c.role || "none"}): ${c.html}`);
  }
  return { problems, controls };
}

// ---- tests -----------------------------------------------------------------------------------

test.describe("axe: no serious or critical violations", () => {
  for (const s of STATES) {
    test(s.name, async ({ page }) => {
      await s.reach(page);
      expect(await blockingViolations(page), "serious/critical axe violations").toEqual([]);
    });
  }
});

test.describe("every interactive control is reachable with Tab and has an accessible name", () => {
  for (const s of STATES) {
    test(s.name, async ({ page }) => {
      await s.reach(page);
      const { problems, controls } = await controlProblems(page);
      const inventory = controls.map((c) => `${c.role} | ${c.name}`).join("\n");
      await test.info().attach("controls (role | accessible name)", { body: inventory, contentType: "text/plain" });
      if (process.env.A11Y_PRINT) console.log(`## ${s.name} (${test.info().project.name})\n${inventory}`);
      expect(controls.length, "the inventory found the controls").toBeGreaterThan(5);
      expect(problems).toEqual([]);
    });
  }
});

test.describe("accessible names carry their meaning", () => {
  test("'Do not touch' toggles are announced inside a named group", async ({ page }) => {
    await afterTruck(page);
    const group = page.getByRole("group", { name: "Do not touch" });
    await expect(group.getByRole("button", { name: "Soundcheck" })).toHaveAttribute("aria-pressed", "false");
  });

  test("agent trace summary reads as separate words", async ({ page }) => {
    await optionsListed(page);
    await expect(page.locator("summary").filter({ hasText: "tool calls" })).toHaveText(/^Simulated agent \d+ tool calls$/);
  });

  test("a refused run's trace does not keep saying 'Starting…'", async ({ page }) => {
    await aiRefused(page);
    const summary = page.locator("summary").filter({ hasText: "tool calls" });
    await expect(summary).toHaveText(/^Agent did not start 0 tool calls$/);
  });
});

test.describe("the gates themselves catch regressions", () => {
  test("axe fails a low-contrast, unnamed control", async ({ page }) => {
    await firstScreen(page);
    await page.evaluate(() => {
      const b = document.createElement("button");
      b.style.cssText = "color:#20262c;background:#090d13;width:40px;height:20px";
      b.textContent = "";
      document.querySelector("main")?.append(b);
      const t = document.createElement("p");
      t.style.cssText = "color:#20262c;background:#090d13";
      t.textContent = "barely visible";
      document.querySelector("main")?.append(t);
    });
    const ids = (await blockingViolations(page)).join("\n");
    expect(ids).toContain("button-name");
    expect(ids).toContain("color-contrast");
  });

  test("the control inventory flags unreachable, unnamed and role-less controls", async ({ page }) => {
    await firstScreen(page);
    await page.evaluate(() => {
      const main = document.querySelector("main");
      const unreachable = document.createElement("div");
      unreachable.setAttribute("role", "button");
      unreachable.textContent = "Unreachable fake";
      const unnamed = document.createElement("button");
      unnamed.style.cssText = "width:20px;height:20px";
      const roleless = document.createElement("div");
      roleless.tabIndex = 0;
      roleless.textContent = "Clickable div";
      main?.append(unreachable, unnamed, roleless);
    });
    const { problems } = await controlProblems(page);
    expect(problems.some((p) => p.startsWith("not reachable with Tab") && p.includes("Unreachable fake"))).toBe(true);
    expect(problems.some((p) => p.startsWith("no accessible name (role button)"))).toBe(true);
    expect(problems.some((p) => p.startsWith("not exposed as a control") && p.includes("Clickable div"))).toBe(true);
  });
});

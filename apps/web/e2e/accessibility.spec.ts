import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

const consoleTabs = [
  { tab: "Overview", heading: "Overview" },
  { tab: "Backtest", heading: "Backtest Studio" },
  { tab: "Strategy Lab", heading: "Strategy Lab" },
  { tab: "Compare", heading: "Strategy Compare" },
  { tab: "History", heading: "Run History" },
  { tab: "Universe", heading: "Universe & Data Health" },
  { tab: "Reports", heading: "Reports & Exports" },
] as const;

type AxeViolation = {
  id: string;
  impact?: string;
  help: string;
  nodes: { target: string[]; failureSummary?: string }[];
};

async function openConsoleTab(page: Page, name: string): Promise<void> {
  const tab = page.getByRole("tablist", { name: "Console views" }).getByRole("tab", { name });
  await tab.scrollIntoViewIfNeeded();
  await tab.click();
}

async function expectNoColorContrastViolations(page: Page, label: string): Promise<void> {
  await page.addScriptTag({ content: axeSource });
  const violations = await page.evaluate(async () => {
    const axe = (
      window as Window & {
        axe: {
          run: (
            context: Document,
            options: { runOnly: { type: "rule"; values: string[] } },
          ) => Promise<{ violations: AxeViolation[] }>;
        };
      }
    ).axe;
    const result = await axe.run(document, {
      runOnly: { type: "rule", values: ["color-contrast"] },
    });
    return result.violations;
  });
  expect(violations, `${label}: ${JSON.stringify(violations, null, 2)}`).toEqual([]);
}

test.describe("research console keyboard accessibility", () => {
  test("skip link moves focus to the main content", async ({ page }) => {
    await page.goto("/");

    const skipLink = page.getByRole("link", { name: "Skip to content" });
    await page.keyboard.press("Tab");
    await expect(skipLink).toBeFocused();
    await page.keyboard.press("Enter");

    await expect(page.locator("#main-content")).toBeFocused();
  });

  test("console tablist supports arrow, Home, and End keyboard navigation", async ({ page }) => {
    await page.goto("/");
    const tablist = page.getByRole("tablist", { name: "Console views" });
    const overview = tablist.getByRole("tab", { name: "Overview" });

    await overview.focus();
    await page.keyboard.press("ArrowRight");
    await expect(tablist.getByRole("tab", { name: "Backtest" })).toBeFocused();
    await expect(page.getByRole("heading", { name: "Backtest Studio" })).toBeVisible();

    await page.keyboard.press("End");
    await expect(tablist.getByRole("tab", { name: "Reports" })).toBeFocused();
    await expect(page.getByRole("heading", { name: "Reports & Exports" })).toBeVisible();

    await page.keyboard.press("Home");
    await expect(overview).toBeFocused();
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  });

  test("new report dialog traps focus and restores the trigger", async ({ page }) => {
    await page.goto("/");
    await openConsoleTab(page, "Reports");
    const trigger = page.getByRole("button", { name: "+ NEW REPORT" });
    await trigger.click();

    const dialog = page.getByRole("dialog", { name: "New report" });
    const close = dialog.getByRole("button", { name: "Close new report" });
    const generate = dialog.getByRole("button", { name: "Generate" });
    await expect(dialog).toBeVisible();
    await expect(close).toBeFocused();

    await page.keyboard.press("Shift+Tab");
    await expect(generate).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(close).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
  });
});

test.describe("research console color contrast", () => {
  for (const { tab, heading } of consoleTabs) {
    test(`${tab} has no browser axe color-contrast violations`, async ({ page }) => {
      await page.goto("/");
      await openConsoleTab(page, tab);
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      await expectNoColorContrastViolations(page, tab);
    });
  }
});

import { expect, test, type Page } from "@playwright/test";

const viewports = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "small desktop", width: 1024, height: 768 },
] as const;

const consoleTabs = [
  { tab: "Overview", heading: "Overview" },
  { tab: "Backtest", heading: "Backtest Studio" },
  { tab: "Compare", heading: "Strategy Compare" },
  { tab: "History", heading: "Run History" },
  { tab: "Universe", heading: "Universe & Data Health" },
  { tab: "Reports", heading: "Reports & Exports" },
] as const;

async function openConsoleTab(page: Page, name: string): Promise<void> {
  const tab = page.getByRole("tablist", { name: "Console views" }).getByRole("tab", { name });
  await tab.scrollIntoViewIfNeeded();
  await tab.click();
}

async function expectNoPageHorizontalOverflow(page: Page, label: string): Promise<void> {
  const overflow = await page.evaluate(() => {
    const html = document.documentElement;
    const body = document.body;
    const viewportWidth = window.innerWidth;
    const offenders = Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          className: element.className.toString(),
          text: element.textContent?.trim().slice(0, 80) ?? "",
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        };
      })
      .filter((item) => item.right > viewportWidth + 1 || item.left < -1)
      .slice(0, 5);
    return {
      viewportWidth,
      documentWidth: html.scrollWidth,
      bodyWidth: body.scrollWidth,
      offenders,
    };
  });

  expect(overflow.documentWidth, `${label}: ${JSON.stringify(overflow, null, 2)}`).toBeLessThanOrEqual(
    overflow.viewportWidth + 1,
  );
  expect(overflow.bodyWidth, `${label}: ${JSON.stringify(overflow, null, 2)}`).toBeLessThanOrEqual(
    overflow.viewportWidth + 1,
  );
}

test.describe("research console responsive smoke", () => {
  for (const viewport of viewports) {
    test(`renders all console tabs without page overflow at ${viewport.width}px`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/");
      await expect(page.getByRole("tablist", { name: "Console views" })).toBeVisible();

      for (const { tab, heading } of consoleTabs) {
        await openConsoleTab(page, tab);
        await expect(page.getByRole("heading", { name: heading })).toBeVisible();
        await expectNoPageHorizontalOverflow(page, `${viewport.name} ${tab}`);
      }
    });
  }
});

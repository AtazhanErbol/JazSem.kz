import { test, expect } from "@playwright/test";

test("refreshed landing, responsive layout and language switch", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Продолжайте учиться.");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.getByRole("button", { name: "Русский / Қазақша" }).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Оқуды жалғастырыңыз.");
  await page.getByRole("link", { name: "Оқуға өту", exact: true }).first().click();
  await expect(page).toHaveURL(/\/login$/);
});

test("3D scene renders and respects reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const canvas = page.locator("canvas");
  await expect(canvas).toHaveAttribute("data-ready", "true");
  const before = await canvas.screenshot();
  await page.mouse.move(1100, 400);
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const after = await canvas.screenshot();
  expect(before.equals(after)).toBe(true);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.mouse.move(1200, 500);
  await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
});

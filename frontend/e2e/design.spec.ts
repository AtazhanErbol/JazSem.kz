import { test, expect } from "@playwright/test";

test("refreshed landing, responsive layout and language switch", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [320, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Продолжайте учиться.");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.getByRole("button", { name: "Қазақша" }).first().click();
  await expect(page.getByRole("button", { name: "Қазақша" }).first()).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.getByRole("button", { name: "Қазақша" }).first()).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("html")).toHaveAttribute("lang", "kk");
  await expect(page.getByRole("heading", { level: 1 })).toHaveCSS("font-family", '"Noto Sans Variable", Arial, sans-serif');
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Оқуды жалғастырыңыз.");
  await page.getByRole("link", { name: "Оқуға өту", exact: true }).first().click();
  await expect(page).toHaveURL(/\/login$/);
});

test("book follows the pointer and respects reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const scene = page.locator(".book-scene");
  const book = page.locator(".book-turntable");
  await expect(book).toBeVisible();
  const initial = await book.evaluate(el => getComputedStyle(el).transform);
  await page.mouse.move(1100, 400);
  expect(await book.evaluate(el => getComputedStyle(el).transform)).toBe(initial);
  expect(await page.locator(".book-levitate").evaluate(el => getComputedStyle(el).animationName)).toBe("none");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const box = (await scene.boundingBox())!;
  await page.mouse.move(box.x + box.width * .85, box.y + box.height * .3);
  await expect.poll(() => scene.evaluate(el => parseFloat((el as HTMLElement).style.getPropertyValue("--book-x")))).toBeGreaterThan(.2);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect.poll(() => book.evaluate(el => getComputedStyle(el).transform)).toBe(initial);
});

test("fixed header stays visible and section links clear it", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    const header = page.locator(".landing-header");
    const height = (await header.boundingBox())!.height;
    const logo = (await header.locator(".logo").boundingBox())!;
    const language = (await header.locator(".language-switch").boundingBox())!;
    const login = (await header.getByRole("link", { name: "Войти", exact: true }).boundingBox())!;
    expect(logo.x + logo.width).toBeLessThanOrEqual(language.x);
    expect(language.x + language.width).toBeLessThanOrEqual(login.x);
    expect(login.x + login.width).toBeLessThanOrEqual(width);
    expect((await page.getByRole("heading", { level: 1 }).boundingBox())!.y).toBeGreaterThan(height);
    await page.evaluate(() => window.scrollTo(0, 1200));
    await expect(header).toHaveClass(/is-scrolled/);
    expect((await header.boundingBox())!.y).toBe(0);
    await expect(header.getByRole("link", { name: "Войти", exact: true })).toBeVisible();
  }
  await page.locator(".landing-header").getByRole("link", { name: "Как это работает" }).click();
  const target = await page.locator("#how").boundingBox();
  expect(target!.y).toBeGreaterThanOrEqual(88);
  expect(target!.y).toBeLessThan(200);
});

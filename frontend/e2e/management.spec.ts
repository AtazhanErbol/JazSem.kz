import { test, expect } from "@playwright/test";
const password = process.env.DEV_SEED_PASSWORD;
test.skip(!password, "Requires separate seeded QA database.");
test("profile security card and detail dialog remain usable on a short screen", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await page.getByRole("link", { name: "Профиль", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Безопасность", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Установить новый пароль" }),
  ).toHaveClass(/button/);
  await expect(page.getByText(/инфраструктуры задаются/)).toHaveCount(0);
  await page.setViewportSize({ width: 809, height: 400 });
  await page.goto("/app/submissions");
  await page
    .getByRole("button", { name: "Подробнее", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.locator("dt").filter({ hasText: /^Задание$/ }),
  ).toBeVisible();
  await expect(dialog).not.toContainText("created_at");
  const before = await dialog.locator(".modal-head").boundingBox();
  const metrics = await dialog.locator(".modal-body").evaluate((el) => {
    el.scrollTop = el.scrollHeight;
    return {
      scroll: getComputedStyle(el).overflowY,
      height: el.clientHeight,
      content: el.scrollHeight,
    };
  });
  expect(metrics.scroll).toBe("auto");
  expect(metrics.content).toBeGreaterThan(metrics.height);
  const after = await dialog.locator(".modal-head").boundingBox();
  expect(after?.y).toBe(before?.y);
  await dialog.getByRole("button", { name: "Закрыть" }).click();
  await expect(dialog).not.toBeVisible();
  await page.goto("/app/assignments");
  await expect(page.getByRole("link", { name: "Выбрать курс" })).toBeVisible();
});

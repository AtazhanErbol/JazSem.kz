import { test, expect } from "@playwright/test";

test("logout followed by another login keeps the new session", async ({
  page,
}) => {
  const password = process.env.DEV_SEED_PASSWORD;
  if (!password)
    throw new Error("DEV_SEED_PASSWORD is required for real API tests");
  await page.goto("/login");
  for (const email of ["student@example.test", "teacher@example.test"]) {
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Пароль", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Войти", exact: true }).click();
    await expect(page).toHaveURL(/\/app$/);
    if (email.startsWith("student")) {
      await page.getByRole("link", { name: "Тесты", exact: true }).click();
      await page.getByRole("button", { name: "Выйти", exact: true }).click();
      await expect(page).toHaveURL(/\/login$/);
    }
  }
  await page.getByRole("link", { name: "Проверка работ", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Проверка работ", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Проверка работ", exact: true }),
  ).toBeVisible();
});

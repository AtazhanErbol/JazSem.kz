import { test, expect } from "@playwright/test";

test("forms preserve input on errors, reject duplicate submits, guard Escape and restore focus", async ({
  page,
}) => {
  if (!process.env.DEV_SEED_PASSWORD)
    throw new Error("Seed password is mandatory");
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.test");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.DEV_SEED_PASSWORD);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  await page.goto("/app/users?role=TEACHER");
  const opener = page.getByRole("button", {
    name: "Добавить преподавателя",
    exact: true,
  });
  await opener.click();
  const modal = page.getByRole("dialog");
  const email = modal.locator('input[name="email"]');
  const save = modal.getByRole("button", { name: "Сохранить", exact: true });
  await expect(modal).toBeVisible();
  expect(
    await modal.evaluate((el) => el.contains(document.activeElement)),
  ).toBe(true);
  await save.click();
  await expect(email).toHaveAttribute("aria-invalid", "true");
  const description = await email.getAttribute("aria-describedby");
  expect(description).toBeTruthy();
  await expect(page.locator(`[id="${description}"]`)).toHaveText(
    "Заполните поле",
  );
  await expect(email).toBeFocused();
  await email.fill("form-regression@example.test");
  await modal.locator('input[name="first_name"]').fill("Қазақша ӘҒҚҢӨҰҮҺІ");
  await modal
    .locator('input[name="last_name"]')
    .fill("Длинное название для проверки формы");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.keyboard.press("Escape");
  await expect(modal).toBeVisible();
  await expect(email).toHaveValue("form-regression@example.test");
  let requests = 0;
  let nextStatus = 400;
  let releaseResponse = () => {};
  await page.route("**/api/v1/users/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    requests++;
    await new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await route.fulfill({
      status: nextStatus,
      json: {
        code: "synthetic_form_failure",
        message: `Synthetic ${nextStatus}`,
        errors:
          nextStatus === 400 ? { email: ["Синтетическая ошибка поля"] } : {},
      },
    });
  });
  for (const status of [400, 403, 409, 429, 503]) {
    nextStatus = status;
    const previous = requests;
    await save.click({ clickCount: 2 });
    await expect(save).toBeDisabled();
    await expect.poll(() => requests).toBe(previous + 1);
    await page.keyboard.press("Escape");
    await expect(modal).toBeVisible();
    if (status === 400) {
      page.once("dialog", (dialog) => dialog.dismiss());
      await page.evaluate(() => window.history.back());
      await expect(page).toHaveURL(/\/app\/users/);
      await expect(email).toHaveValue("form-regression@example.test");
    }
    releaseResponse();
    await expect(save).toBeEnabled();
    expect(requests).toBe(previous + 1);
    await expect(email).toHaveValue("form-regression@example.test");
    if (status === 400) {
      await expect(email).toBeFocused();
      await expect(email).toHaveAttribute("aria-invalid", "true");
    }
  }
  page.once("dialog", (dialog) => dialog.accept());
  await page.keyboard.press("Escape");
  await expect(modal).not.toBeVisible();
  await expect(opener).toBeFocused();
  await opener.click();
  await expect(email).toHaveValue("");
  await page.keyboard.press("Escape");
  await expect(opener).toBeFocused();
});

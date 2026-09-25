import { test, expect } from "@playwright/test";

const password = process.env.DEV_SEED_PASSWORD;
test.skip(!password, "Run seed_dev and set DEV_SEED_PASSWORD before E2E.");
test("student studies, submits, takes a test; teacher grades", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("student@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(
    page.getByRole("heading", { name: /Здравствуйте/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Мои курсы", exact: true }).click();
  await page.getByRole("link", { name: "Продолжить обучение" }).first().click();
  await page
    .getByRole("button", { name: "Конспект: Линейные уравнения" })
    .click();
  const complete = page.getByRole("button", { name: "Отметить как изучено" });
  if (await complete.count()) {
    await complete.click();
    await expect(
      page.getByRole("button", { name: "Изучено", exact: true }),
    ).toBeDisabled();
  }
  await page.goto("/app/assignments");
  await page
    .getByRole("link", { name: "Отправить работу", exact: true })
    .first()
    .click();
  await page.getByLabel("Ваш ответ").fill("x = 3. Проверка: 3 × 3 − 9 = 0.");
  await page
    .getByRole("button", { name: "Отправить работу", exact: true })
    .click();
  await expect(page.getByText("Сохранено", { exact: true })).toBeVisible();
  await page.goto("/app/tests");
  await page
    .getByRole("link", { name: "Начать тест", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Начать тест / Продолжить обучение" })
    .click();
  const option = page.getByRole("radio", { name: "−2", exact: true });
  if (await option.isEnabled()) {
    await option.check();
    await expect(page.getByText("Сохранено", { exact: true })).toBeVisible();
    await page
      .getByRole("button", { name: "Завершить тест", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Подтвердить", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Результат", exact: true }),
    ).toBeVisible();
  }
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await page.getByLabel("Email").fill("teacher@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await page.getByRole("link", { name: "Проверка работ", exact: true }).click();
  await page
    .getByRole("link", { name: "Оценить", exact: true })
    .first()
    .click();
  await page.getByLabel("Балл", { exact: true }).fill("85");
  await page.getByLabel("Комментарий преподавателя").fill("Решение верное.");
  await page.getByRole("button", { name: "Оценить", exact: true }).click();
  await expect(page.getByText("Сохранено", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await page.getByLabel("Email").fill("student@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await page.getByRole("link", { name: "Оценки", exact: true }).click();
  await expect(page.getByText(/Задания \(60%\)/)).toBeVisible();
});

test("landing is usable at mobile and desktop widths", async ({ page }) => {
  for (const width of [390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await page.getByRole("button", { name: "Русский / Қазақша" }).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Өзіңізбенқалатынбілім.",
  );
});

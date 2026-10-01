import { test, expect } from "@playwright/test";
const password = process.env.DEV_SEED_PASSWORD;
test.skip(!password, "Requires a separate seeded QA database.");
test("teacher authors assignments and tests manually, publishes and assigns a course", async ({
  page,
}) => {
  test.setTimeout(180000);
  await page.goto("/login");
  await page.getByLabel("Email").fill("teacher@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await page.getByRole("link", { name: "Мои курсы", exact: true }).click();
  await page
    .getByRole("button", { name: "Создать курс", exact: true })
    .first()
    .click();
  const title = "Manual course " + Date.now();
  const dialog = page.getByRole("dialog");
  const save = async () => {
    await dialog
      .getByRole("button", { name: "Сохранить", exact: true })
      .click();
    await expect(dialog).not.toBeVisible();
  };
  await dialog
    .getByLabel("Дисциплина", { exact: true })
    .selectOption({ label: "Прикладная математика" });
  await dialog.getByLabel("Название", { exact: true }).fill(title);
  await dialog
    .getByRole("button", { name: "Создать и перейти к наполнению" })
    .click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Добавить неделю" }).first().click();
  await dialog.getByLabel("Название", { exact: true }).fill("First week");
  await save();
  await page.getByRole("button", { name: "Добавить тему" }).first().click();
  await dialog.getByLabel("Название", { exact: true }).fill("First topic");
  await save();
  await page.getByRole("button", { name: "+ Материалы", exact: true }).click();
  await dialog.getByLabel("Название", { exact: true }).fill("First material");
  await dialog.getByLabel("Контент", { exact: true }).fill("Read this lesson.");
  await save();
  await page.getByRole("button", { name: "+ Задания", exact: true }).click();
  await dialog
    .getByLabel("Название", { exact: true })
    .fill("Manual assignment");
  await dialog
    .getByLabel("Инструкция", { exact: true })
    .fill("Solve x + 1 = 2 and explain your answer.");
  await save();
  await page.getByRole("button", { name: "+ Тесты", exact: true }).click();
  await dialog.getByLabel("Название", { exact: true }).fill("Manual quiz");
  await save();
  await page
    .getByRole("button", { name: "Тесты Manual quiz", exact: true })
    .click();
  await page
    .getByRole("button", { name: "+ Добавить вопрос", exact: true })
    .click();
  await dialog.getByLabel("Текст", { exact: true }).fill("1 + 1 = ?");
  await save();
  await expect(page.getByRole("heading", { name: "1 + 1 = ?" })).toBeVisible();
  for (const [text, correct] of [
    ["2", true],
    ["3", false],
  ] as const) {
    await page
      .getByRole("button", { name: "+ Добавить вариант", exact: true })
      .click();
    await dialog.getByLabel("Текст", { exact: true }).fill(text);
    if (correct)
      await dialog.getByLabel("Правильный ответ", { exact: true }).check();
    await save();
  }
  await expect(page.getByText("✓ 2", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Настроить оценивание", exact: true })
    .click();
  await dialog.getByLabel("Задания (%)", { exact: true }).fill("50");
  await dialog.getByLabel("Тесты (%)", { exact: true }).fill("50");
  await save();
  await expect(page.locator("#course-grading .grading-total")).toHaveText(
    "Сумма весов: 100 из 100%",
  );
  await page.getByRole("button", { name: "Опубликовать", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Подтвердить", exact: true })
    .click();
  await expect(page.getByText(/Опубликован.*v1/)).toBeVisible();
  await page
    .getByLabel("Студент", { exact: true })
    .selectOption({ label: "Алихан Омаров · student@example.test" });
  await page
    .getByRole("button", { name: "Назначить", exact: true })
    .first()
    .click();
  await expect(
    page.getByText("Курс назначен студенту.", { exact: true }),
  ).toBeVisible();
});

import { test, expect } from "@playwright/test";
const password = process.env.DEV_SEED_PASSWORD;
test.skip(!password, "Requires a separate seeded QA database.");

test("admin creates course, assignment and test from quick actions without AI", async ({
  page,
}) => {
  test.setTimeout(180000);
  await page.setViewportSize({ width: 1440, height: 1080 });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Кабинет администратора" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../.runtime/admin-workspace-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: /Создать курс Программа/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Дисциплина", { exact: true })
    .selectOption({ label: "Прикладная математика" });
  await dialog
    .getByLabel("Ответственный преподаватель", { exact: true })
    .selectOption({ label: "Айдана Серикова · teacher@example.test" });
  const course = `Admin manual ${Date.now()}`;
  await dialog.getByLabel("Название", { exact: true }).fill(course);
  await dialog
    .getByRole("button", { name: "Создать и перейти к наполнению" })
    .click();
  await expect(
    page.getByRole("heading", { name: course }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Назначить", exact: true }).first(),
  ).toBeDisabled();
  await page.goto("/app");
  await page.getByRole("link", { name: /Создать задание Инструкция/ }).click();
  await dialog
    .getByLabel("Выберите курс", { exact: true })
    .selectOption({ label: course });
  await dialog.getByRole("button", { name: /Добавить неделю/ }).click();
  await dialog.getByLabel("Название", { exact: true }).fill("Основы");
  await dialog.getByRole("button", { name: "Сохранить", exact: true }).click();
  await dialog.getByRole("button", { name: /Добавить тему/ }).click();
  await dialog.getByLabel("Название", { exact: true }).fill("Уравнения");
  await dialog.getByRole("button", { name: "Сохранить", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Далее: содержание и настройки" })
    .click();
  await dialog
    .getByLabel("Название", { exact: true })
    .fill("Самостоятельная работа");
  await dialog
    .getByLabel("Инструкция", { exact: true })
    .fill("Решите x + 1 = 2 и объясните ответ.");
  await dialog
    .getByRole("button", { name: "Создать задание", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/courses\/.+activity=/);
  await expect(
    page.getByRole("heading", { name: "Самостоятельная работа", level: 2 }),
  ).toBeVisible();
  await page.goto("/app");
  await page.getByRole("link", { name: /Создать тест Вопросы/ }).click();
  await dialog
    .getByLabel("Выберите курс", { exact: true })
    .selectOption({ label: course });
  await dialog
    .getByLabel("Выберите тему", { exact: true })
    .selectOption({ label: "Уравнения" });
  await dialog
    .getByRole("button", { name: "Далее: содержание и настройки" })
    .click();
  await dialog.getByLabel("Название", { exact: true }).fill("Проверочный тест");
  await dialog
    .getByRole("button", { name: "Создать тест", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Добавьте первый вопрос" }),
  ).toBeVisible();
  const save = async () => {
    await dialog
      .getByRole("button", { name: "Сохранить", exact: true })
      .click();
    await expect(dialog).not.toBeVisible();
  };
  await page.getByRole("button", { name: /Добавить вопрос/ }).click();
  await dialog.getByLabel("Текст", { exact: true }).fill("1 + 1 = ?");
  await save();
  for (const [answer, correct] of [
    ["2", true],
    ["3", false],
  ] as const) {
    await page.getByRole("button", { name: /Добавить вариант/ }).click();
    await dialog.getByLabel("Текст", { exact: true }).fill(answer);
    if (correct)
      await dialog.getByLabel("Правильный ответ", { exact: true }).check();
    await save();
  }
  await page.getByRole("button", { name: "Распределить поровну" }).click();
  await expect(
    page.getByText("Сумма весов: 100 из 100%", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../.runtime/admin-workspace-builder.png",
    fullPage: true,
  });
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
  await page.goto("/app/tests?create=1");
  await dialog
    .getByLabel("Выберите курс", { exact: true })
    .selectOption({ label: course });
  await expect(
    dialog.getByRole("heading", {
      name: "Для изменений нужна версия-черновик",
    }),
  ).toBeVisible();
  await dialog.getByRole("link", { name: "Открыть редактор курса" }).click();
  await expect(
    page.getByRole("heading", { name: course }).first(),
  ).toBeVisible();
  await page.goto("/app/users?role=TEACHER&create=1");
  await expect(dialog.getByLabel("Роль", { exact: true })).toHaveValue(
    "TEACHER",
  );
  await page.goto("/app");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Қазақша" }).click();
  await expect(
    page.getByRole("heading", { name: "Әкімші кабинеті" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../.runtime/admin-workspace-mobile-kk.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Мәзірді ашу" }).click();
  await page
    .getByRole("link", { name: "Қалай қолдануға болады", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Қалай қолдануға болады" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Мәзірді ашу" }),
  ).toHaveAttribute("aria-expanded", "false");
  expect(errors).toEqual([]);
});

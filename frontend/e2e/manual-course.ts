import { expect, type Page } from "@playwright/test";
import type { Tree } from "../src/entities/types";
export async function manualCourse(
  page: Page,
  discipline: string,
  title: string,
) {
  await page.getByRole("link", { name: "Мои курсы", exact: true }).click();
  await page
    .getByRole("button", { name: "Создать курс", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  const save = async () => {
    await dialog
      .getByRole("button", { name: "Сохранить", exact: true })
      .click();
    await expect(dialog).not.toBeVisible();
  };
  await dialog
    .getByLabel("Дисциплина", { exact: true })
    .selectOption({ label: discipline });
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
  await dialog.getByLabel("Контент", {exact: true}).fill("Synthetic introduction to equations.");
  await save();
  await page.getByRole("button", { name: "+ Материалы", exact: true }).click();
  await dialog.getByLabel("Название", { exact: true }).fill("First material");
  await dialog.getByLabel("Контент", { exact: true }).fill("Read this lesson.");
  await dialog
    .locator('input[type="file"]')
    .setInputFiles({
      name: "lesson.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Synthetic course material"),
    });
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
  await page.getByRole("button", { name: "Manual quiz", exact: true }).click();
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
    .getByRole("button", { name: "+ Схема оценивания", exact: true })
    .click();
  await dialog.getByLabel("Название", { exact: true }).fill("Balanced grading");
  await save();
  for (const kind of ["ASSIGNMENTS", "TESTS"]) {
    await page
      .getByRole("button", { name: "+ Добавить компонент", exact: true })
      .click();
    await dialog.getByRole("combobox").selectOption(kind);
    await dialog.getByRole("spinbutton").fill("50");
    await save();
  }
  await page.getByRole("button", { name: "Опубликовать", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Подтвердить", exact: true })
    .click();
  await expect(page.getByText(/Опубликован.*v1/)).toBeVisible();

  const courseId = new URL(page.url()).pathname.split("/").at(-1)!;
  const response = await page.request.get(`/api/v1/courses/${courseId}/tree/`);
  expect(response.ok()).toBe(true);
  const tree: Tree = await response.json();
  return {
    courseId,
    versionId: tree.version.id,
    topicId: tree.weeks[0].topics[0].id,
    materialId: tree.weeks[0].topics[0].materials[0].id,
    assignmentId: tree.weeks[0].topics[0].assignments[0].id,
    testId: tree.weeks[0].topics[0].tests[0].id,
  };
}

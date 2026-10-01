import { test, expect } from "@playwright/test";

test("AI source/history pagination restores URL state and keeps RU/KK controls localized", async ({
  page,
}) => {
  const requested: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname;
    let data: unknown = { count: 0, results: [], next: null, previous: null };
    if (path.endsWith("/auth/me/"))
      data = {
        id: "paging-teacher",
        email: "paging@example.test",
        role: "TEACHER",
        must_change_password: false,
        preferred_language: "ru",
      };
    else if (path.endsWith("/ai-status/"))
      data = {
        enabled: true,
        configured: true,
        worker_available: true,
        model: "synthetic-ui",
        daily_budget: "0.25",
      };
    else if (path.endsWith("/courses/"))
      data = {
        count: 1,
        results: [{ id: "course", title: "Пагинация / Беттеу ӘҒҚҢӨҰҮҺІ" }],
        next: null,
        previous: null,
      };
    else if (path.endsWith("/sources/") || path.endsWith("/ai-jobs/")) {
      const number = Number(url.searchParams.get("page") || 1),
        source = path.endsWith("/sources/");
      requested.push(`${source ? "source" : "job"}:${number}`);
      const results = Array.from({ length: number === 1 ? 25 : 1 }, (_, n) =>
        source
          ? {
              id: `s${(number - 1) * 25 + n}`,
              filename: `source ${(number - 1) * 25 + n}.txt`,
              processing_status: "COMPLETED",
            }
          : {
              id: `j${(number - 1) * 25 + n}`,
              course: "course",
              created_at: "2026-10-01T00:00:00Z",
              status: number === 1 && n === 0 ? "QUEUED" : "FAILED",
            },
      );
      data = {
        count: 26,
        results,
        next: number === 1 ? "?page=2" : null,
        previous: number === 2 ? "?page=1" : null,
      };
    } else if (path.includes("/ai-jobs/j"))
      data = {
        id: path.split("/").at(-2),
        course: "course",
        status: path.endsWith("/j0/") ? "QUEUED" : "FAILED",
        current_step: path.endsWith("/j0/") ? "RECOVERING" : "FAILED",
        progress: 0,
      };
    await route.fulfill({ status: 200, json: data });
  });
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/app/ai?course=course");
  await expect(
    page.getByText("Восстановление обработки", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("checkbox", { name: "source 0.txt", exact: true })
    .check();
  await page
    .getByRole("navigation", { name: "Учебные источники", exact: true })
    .getByRole("button", { name: "Далее", exact: true })
    .click();
  await expect(
    page.getByRole("checkbox", { name: "source 25.txt", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/sourcePage=2/);
  await page
    .getByRole("navigation", { name: "История генераций", exact: true })
    .getByRole("button", { name: "Далее", exact: true })
    .click();
  await expect(page).toHaveURL(/jobPage=2/);
  await page.reload();
  await expect(
    page.getByRole("checkbox", { name: "source 25.txt", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Қазақша", exact: true }).click();
  await expect(
    page.getByRole("option", { name: "Орташа", exact: true }),
  ).toHaveAttribute("value", "intermediate");
  expect(new URL(page.url()).searchParams.get("jobPage")).toBe("2");
  await page.getByRole("button", { name: "Русский", exact: true }).click();
  await page
    .getByRole("navigation", { name: "Учебные источники", exact: true })
    .getByRole("button", { name: "Назад", exact: true })
    .click();
  await expect(
    page.getByRole("checkbox", { name: "source 0.txt", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("checkbox", { name: "source 25.txt", exact: true }),
  ).toBeVisible();
  expect(requested).toEqual(
    expect.arrayContaining(["source:1", "source:2", "job:1", "job:2"]),
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
});

test("AI wizard reviews and imports a draft without a real provider call", async ({
  page,
}) => {
  const user = {
    id: "teacher",
    email: "teacher@example.test",
    first_name: "Teacher",
    last_name: "Test",
    role: "TEACHER",
    must_change_password: false,
    preferred_language: "ru",
  };
  const draft = {
    title: "AI course",
    description: "Grounded draft",
    source_gaps: [],
    weeks: [
      {
        title: "Week one",
        topics: [
          {
            title: "Equations",
            content: "x + 1 = 2",
            source_chunks: ["chunk"],
            assignments: [
              {
                title: "Solve",
                instructions: "Solve the equation",
                source_chunks: ["chunk"],
              },
            ],
            questions: [],
          },
        ],
      },
    ],
  };
  let generated = false;
  let imported = false;
  let savedTitle = "";
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let data: unknown = { count: 0, results: [], next: null, previous: null };
    if (path.endsWith("/ai-status/"))
      data = {
        enabled: true,
        configured: true,
        worker_available: true,
        daily_budget: "0.25",
        model: "test-model",
      };
    else if (path.endsWith("/auth/me/")) data = user;
    else if (path.endsWith("/auth/login/")) data = { csrfToken: "test-csrf" };
    else if (path.endsWith("/courses/"))
      data = {
        count: 1,
        results: [{ id: "course", title: "My course" }],
        next: null,
        previous: null,
      };
    else if (path.endsWith("/sources/"))
      data = {
        count: 1,
        results: [
          {
            id: "source",
            filename: "lesson.txt",
            processing_status: "COMPLETED",
          },
        ],
        next: null,
        previous: null,
      };
    else if (
      path.endsWith("/ai-jobs/") &&
      route.request().method() === "POST"
    ) {
      generated = true;
      data = { id: "job", status: "COMPLETED" };
    } else if (path.endsWith("/ai-jobs/"))
      data = {
        count: generated ? 1 : 0,
        results: generated ? [{ id: "job", status: "COMPLETED" }] : [],
        next: null,
        previous: null,
      };
    else if (path.endsWith("/ai-jobs/job/"))
      data = {
        id: "job",
        course: "course",
        status: "COMPLETED",
        progress: 100,
        current_step: "DRAFT_READY",
      };
    else if (path.endsWith("/ai-jobs/job/draft/"))
      data = {
        id: "draft",
        data: draft,
        imported_version: imported ? "version" : null,
      };
    else if (
      path.endsWith("/ai-drafts/draft/") &&
      route.request().method() === "PATCH"
    ) {
      const body = route.request().postDataJSON();
      savedTitle = body.data.title;
      draft.title = savedTitle;
      data = { id: "draft", data: draft };
    } else if (path.endsWith("/ai-drafts/draft/confirm/")) {
      imported = true;
      data = { id: "version", status: "DRAFT" };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
  await page.goto("/app/ai");
  await page
    .getByRole("combobox", { name: "Курс", exact: true })
    .selectOption("course");
  await page.getByRole("checkbox", { name: "lesson.txt", exact: true }).check();
  await page
    .getByRole("button", { name: "Создать черновик", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "05 / Проверка черновика" }),
  ).toBeVisible();
  await page
    .getByLabel("Название", { exact: true })
    .first()
    .fill("Reviewed course");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect.poll(() => savedTitle).toBe("Reviewed course");
  await page
    .getByRole("button", { name: "Подтвердить черновик", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Подтвердить", exact: true })
    .click();
  await expect.poll(() => imported).toBe(true);
  await expect(
    page.getByRole("link", { name: "Редактор курса → Опубликовать" }),
  ).toBeVisible();
});

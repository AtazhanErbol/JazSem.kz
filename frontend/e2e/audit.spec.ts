import { test, expect } from "@playwright/test";
const password = process.env.DEV_SEED_PASSWORD;
test.skip(!password, "Requires an isolated audit database.");
const routes = {
  admin: [
    "/app",
    "/app/courses",
    "/app/users",
    "/app/groups",
    "/app/disciplines",
    "/app/assignments",
    "/app/submissions",
    "/app/tests",
    "/app/grades",
    "/app/progress",
    "/app/content",
    "/app/audit",
    "/app/ai-usage",
    "/app/notifications",
    "/app/settings",
    "/app/ai",
  ],
  teacher: [
    "/app",
    "/app/courses",
    "/app/users",
    "/app/groups",
    "/app/disciplines",
    "/app/assignments",
    "/app/submissions",
    "/app/tests",
    "/app/grades",
    "/app/progress",
    "/app/notifications",
    "/app/settings",
    "/app/ai",
  ],
  student: [
    "/app",
    "/app/courses",
    "/app/assignments",
    "/app/tests",
    "/app/grades",
    "/app/progress",
    "/app/notifications",
    "/app/settings",
  ],
};
for (const role of ["admin", "teacher", "student"] as const)
  test(`${role}: every permitted screen on desktop/mobile and RU/KZ`, async ({
    page,
  }) => {
    test.setTimeout(180000);
    const crashes: string[] = [];
    page.on("pageerror", (e) => crashes.push(e.message));
    await page.goto("/login");
    await page.getByLabel("Email").fill(role + "@example.test");
    await page.getByLabel("Пароль", { exact: true }).fill(password!);
    await page.getByRole("button", { name: "Войти", exact: true }).click();
    await expect(page).toHaveURL(/\/app$/);
    for (const [width, language] of [
      [1280, "Русский"],
      [390, "Қазақша"],
    ] as const) {
      await page.setViewportSize({ width, height: 844 });
      await page.getByRole("button", { name: language, exact: true }).click();
      for (const route of routes[role]) {
        await page.goto(route);
        await expect(page.locator("main.page h1")).toBeVisible();
        await page.waitForLoadState("networkidle");
        await expect(page.locator("main.page")).not.toContainText("undefined");
        await expect(page.getByRole("alert")).toHaveCount(0);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
          route,
        ).toBe(true);
        if (route === "/app" || route === "/app/settings")
          await page.screenshot({
            path: `test-results/audit-${role}-${width}-${route.endsWith("settings") ? "settings" : "dashboard"}.png`,
            fullPage: true,
          });
      }
    }
    if (role === "student") {
      await page.goto("/app/ai");
      await expect(
        page.getByRole("heading", { name: "Қолжетімсіз" }),
      ).toBeVisible();
      await page.goto("/app/audit");
      await expect(
        page.getByRole("heading", { name: "Қолжетімсіз" }),
      ).toBeVisible();
    }
    expect(crashes).toEqual([]);
  });

test("test answers survive refresh, completed attempts remain accessible", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("student@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  await page.goto("/app/tests");
  await page
    .getByRole("article")
    .filter({
      has: page.getByRole("heading", {
        name: "Проверка знаний 2",
        exact: true,
      }),
    })
    .getByRole("link", { name: "Начать тест", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Начать тест / Продолжить обучение" })
    .click();
  await page.getByLabel("−2", { exact: true }).check();
  await expect(page.getByText("Ответ сохранён", { exact: true })).toBeVisible();
  const names = await page.locator(".answer-option").allTextContents();
  await page.reload();
  await expect(page.getByLabel("−2", { exact: true })).toBeChecked();
  expect(await page.locator(".answer-option").allTextContents()).toEqual(names);
  await page
    .getByRole("button", { name: "Завершить тест", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Подтвердить", exact: true })
    .click();
  await expect(page.getByText("100.00 / 100", { exact: true })).toBeVisible();
  await page.goto("/app/tests");
  await page
    .getByRole("article")
    .filter({
      has: page.getByRole("heading", {
        name: "Проверка знаний 2",
        exact: true,
      }),
    })
    .getByRole("link", { name: "Начать тест", exact: true })
    .click();
  await page.getByRole("button", { name: /Номер попытки 1/ }).click();
  await expect(page.getByText("100.00 / 100", { exact: true })).toBeVisible();
});

test("admin preserves multiple teachers when editing a discipline", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  const csrf = (await page.context().cookies()).find(
    (cookie) => cookie.name === "csrftoken",
  )!.value;
  const added = await page.request.post("/api/v1/users/", {
    headers: { "X-CSRFToken": csrf },
    data: {
      email: `audit-teacher-${Date.now()}@example.test`,
      first_name: "Audit",
      last_name: "Teacher",
      role: "TEACHER",
      preferred_language: "ru",
    },
  });
  expect(added.ok()).toBe(true);
  const addedTeacher = await added.json();
  await page.goto("/app/disciplines");
  await page
    .getByRole("article")
    .filter({
      has: page.getByRole("heading", {
        name: "Прикладная математика",
        exact: true,
      }),
    })
    .getByRole("button", { name: "Редактировать", exact: true })
    .click();
  const select = page
    .getByRole("dialog")
    .getByLabel("Преподаватели", { exact: true });
  await expect(select).toHaveAttribute("multiple", "");
  await expect(select).toBeEnabled();
  await expect
    .poll(() => select.locator("option:checked").count())
    .toBeGreaterThan(0);
  const chosen = await select
    .locator("option:checked")
    .evaluateAll((items) =>
      items.map((item) => (item as HTMLOptionElement).value),
    );
  expect(chosen.length).toBeGreaterThan(0);
  await select.selectOption([...chosen, addedTeacher.id]);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Сохранить", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("article")
    .filter({
      has: page.getByRole("heading", {
        name: "Прикладная математика",
        exact: true,
      }),
    })
    .getByRole("button", { name: "Редактировать", exact: true })
    .click();
  await expect
    .poll(async () =>
      select
        .locator("option:checked")
        .evaluateAll((items) =>
          items.map((item) => (item as HTMLOptionElement).value).sort(),
        ),
    )
    .toEqual([...chosen, addedTeacher.id].sort());
});

test("grade results beyond the first page are reachable", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("teacher@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  await page.route("**/api/v1/enrollments/summaries/?*", (route) => {
    const second =
      new URL(route.request().url()).searchParams.get("page") === "2";
    return route.fulfill({
      json: {
        count: 26,
        next: second ? null : "?page=2",
        previous: second ? "?page=1" : null,
        results: Array.from({ length: second ? 1 : 25 }, (_, index) => ({
          id: `audit-${second ? 26 : index + 1}`,
          course_title: `Audit course ${second ? 26 : index + 1}`,
          student_name: "Audit student",
          course: `course-${index}`,
          grades: { score: 75, components: [] },
          progress: { percent: 25, completed: 1, total: 4 },
        })),
      },
    });
  });
  await page.goto("/app/grades");
  await expect(
    page.getByRole("heading", { name: "Audit course 1", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Страницы" })
    .getByRole("button", { name: "Далее", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Audit course 26", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Audit course 1", exact: true }),
  ).toHaveCount(0);
});

import { test, expect, type Page } from "@playwright/test";
import { manualCourse } from "./manual-course";

const seedPassword = process.env.DEV_SEED_PASSWORD;
test.skip(
  !seedPassword,
  "Requires isolated fixtures and the synthetic SMTP sink.",
);
const sink = process.env.E2E_MAIL_URL || "http://127.0.0.1:8025";
async function mail(recipient: string, pattern: RegExp) {
  let result = "";
  await expect
    .poll(
      async () => {
        const response = await fetch(
          `${sink}/messages?recipient=${encodeURIComponent(recipient)}`,
        );
        if (!response.ok) return false;
        const messages: { text: string; subject: string }[] =
          await response.json();
        result =
          messages.findLast((row) =>
            pattern.test(row.subject + "\n" + row.text),
          )?.text || "";
        return !!result;
      },
      { timeout: 90000, intervals: [500, 1000, 2000] },
    )
    .toBe(true);
  return result;
}
async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$|change-temporary-password/);
}
async function logout(page: Page) {
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
}
async function firstLogin(page: Page, email: string, password: string) {
  const body = await mail(email, /Временный пароль:/);
  const temporary = body.match(/Временный пароль:\s*(\S+)/)?.[1];
  if (!temporary)
    throw new Error("Synthetic account mail is missing its temporary password");
  await login(page, email, temporary);
  await expect(page).toHaveURL(/change-temporary-password/);
  await page.getByLabel("Текущий пароль", { exact: true }).fill(temporary);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page
    .getByLabel("Повторите новый пароль", { exact: true })
    .fill(password);
  await page
    .getByRole("button", { name: "Установить новый пароль", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app$/);
  await mail(email, /пароль изменён/);
}

test("real lifecycle: admin people, SMTP first login/reset, teaching, revision, grades and immutable history", async ({
  page,
}) => {
  test.setTimeout(480000);
  page.setDefaultTimeout(15000);
  const stamp = Date.now().toString();
  const teacherEmail = `rc-teacher-${stamp}@example.test`;
  const studentEmail = `rc-student-${stamp}@example.test`;
  const teacherPassword = "Synthetic-tutor-9731!";
  const studentPassword = "Synthetic-learner-8492!";
  const resetPassword = "Synthetic-reset-6492!";
  const discipline = `RC mathematics ${stamp}`;
  const groupName = `RC group ${stamp}`;
  const dialog = page.getByRole("dialog");
  await login(page, "admin@example.test", seedPassword!);

  async function createPerson(
    role: "TEACHER" | "STUDENT",
    email: string,
    first: string,
    owner?: string,
  ) {
    await page.goto(`/app/users?role=${role}&create=1`);
    await dialog.getByLabel("Email", { exact: true }).fill(email);
    await dialog.getByLabel("Имя", { exact: true }).fill(first);
    await dialog.getByLabel("Фамилия", { exact: true }).fill(stamp);
    if (owner)
      await dialog
        .getByLabel("Ответственный преподаватель", { exact: true })
        .selectOption(owner);
    const response = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/users/") &&
        response.request().method() === "POST",
    );
    await dialog
      .getByRole("button", { name: "Сохранить", exact: true })
      .click();
    const saved = await response;
    expect(saved.status()).toBe(201);
    await expect(dialog).not.toBeVisible();
    return (await saved.json()).id as string;
  }
  const teacherId = await createPerson("TEACHER", teacherEmail, "Tutor");
  await page.goto(
    `/app/users?role=TEACHER&search=${encodeURIComponent(teacherEmail)}`,
  );
  await page
    .getByRole("button", { name: "Редактировать", exact: true })
    .click();
  await expect(dialog.getByLabel("Роль", { exact: true })).toHaveCount(0);
  await dialog.getByLabel("Имя", { exact: true }).fill("Professor");
  await dialog.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await page.goto("/app/disciplines?create=1");
  await dialog.getByLabel("Название", { exact: true }).fill(discipline);
  await dialog.getByLabel("Код", { exact: true }).fill(`RC-${stamp}`);
  await dialog
    .getByLabel("Преподаватели", { exact: true })
    .selectOption(teacherId);
  await dialog.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  const studentId = await createPerson(
    "STUDENT",
    studentEmail,
    "Learner",
    teacherId,
  );
  await page.goto("/app/groups?create=1");
  await dialog.getByLabel("Название", { exact: true }).fill(groupName);
  await dialog
    .getByLabel("Преподаватель", { exact: true })
    .selectOption(teacherId);
  const groupResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/groups/") &&
      response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "Сохранить", exact: true }).click();
  const group = await (await groupResponse).json();
  await expect(dialog).not.toBeVisible();
  await page.goto(`/app/groups/${group.id}`);
  await page.getByLabel("Студент", { exact: true }).selectOption(studentId);
  await page
    .getByRole("button", { name: "Добавить студента", exact: true })
    .click();
  await expect(page.locator(".record-row")).toContainText(studentEmail);
  await logout(page);

  await firstLogin(page, teacherEmail, teacherPassword);
  const course = await manualCourse(page, discipline, `RC learning ${stamp}`);
  await page.getByLabel("Группы", { exact: true }).selectOption(group.id);
  await page
    .locator("#course-sharing")
    .getByRole("button", { name: "Назначить", exact: true })
    .last()
    .click();
  await expect(
    page.getByText("Курс назначен группе.", { exact: true }),
  ).toBeVisible();
  await logout(page);
  await firstLogin(page, studentEmail, studentPassword);
  await logout(page);

  await page.getByRole("link", { name: "Забыли пароль?", exact: true }).click();
  await page.getByLabel("Email", { exact: true }).fill(studentEmail);
  await page
    .getByRole("button", { name: "Восстановить пароль", exact: true })
    .click();
  const resetMail = await mail(studentEmail, /Восстановить пароль:/);
  const resetUrl = resetMail.match(
    /https?:\/\/\S+\/reset-password\?[^\s]+/,
  )?.[0];
  if (!resetUrl) throw new Error("Synthetic password-reset link missing");
  await page.goto(new URL(resetUrl).pathname + new URL(resetUrl).search);
  await page.getByLabel("Пароль", { exact: true }).fill(resetPassword);
  await page
    .getByLabel("Повторите новый пароль", { exact: true })
    .fill(resetPassword);
  await page
    .getByRole("button", { name: "Установить новый пароль", exact: true })
    .click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, studentEmail, resetPassword);

  expect(
    (
      await page.request.get(`/api/v1/questions/?test=${course.testId}`)
    ).status(),
  ).toBe(403);
  expect((await page.request.get("/api/v1/operations/")).status()).toBe(403);
  expect((await page.request.get("/api/v1/mail-outbox/")).status()).toBe(403);
  await page.goto(`/app/courses/${course.courseId}`);
  await page.getByRole("button", { name: "First topic", exact: true }).click();
  await page
    .getByRole("button", { name: "Отметить как изучено", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Изучено", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "First material", exact: true })
    .click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "First material", exact: true }),
  ).toBeVisible();
  const download = await page.request.get(
    `/api/v1/materials/${course.materialId}/download/`,
  );
  expect(download.ok()).toBe(true);
  expect(download.headers()["cache-control"]).toContain("no-store");
  expect(await download.text()).toBe("Synthetic course material");
  await page
    .getByRole("button", { name: "Отметить как изучено", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Изучено", exact: true }),
  ).toBeDisabled();
  await page.goto(`/app/assignments/${course.assignmentId}`);
  await page.getByLabel("Ваш ответ").fill("Synthetic first solution.");
  await page.locator('input[type="file"]').setInputFiles({
    name: "answer.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Synthetic answer attachment"),
  });
  const sent = page.waitForResponse(
    (response) =>
      response.url().includes(`/assignments/${course.assignmentId}/submit/`) &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Отправить работу", exact: true })
    .click();
  const submissionId = (await (await sent).json()).id;
  await expect(page.getByText("Сохранено", { exact: true })).toBeVisible();
  await logout(page);
  await login(page, teacherEmail, teacherPassword);
  await page.goto(`/app/submissions/${submissionId}`);
  await expect(
    page.getByRole("link", { name: "answer.txt", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Комментарий преподавателя")
    .fill("Please explain the equation.");
  await page.getByRole("button", { name: "На доработку", exact: true }).click();
  await expect(
    page.getByText("Ожидается доработка студента.", { exact: true }),
  ).toBeVisible();
  await logout(page);
  await login(page, studentEmail, resetPassword);
  await page.goto(`/app/assignments/${course.assignmentId}`);
  await expect(
    page.getByText("Please explain the equation.").first(),
  ).toBeVisible();
  await page.getByLabel("Ваш ответ").fill("Synthetic revised solution: x = 1.");
  const revised = page.waitForResponse(
    (response) =>
      response.url().includes(`/assignments/${course.assignmentId}/submit/`) &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Отправить работу", exact: true })
    .click();
  const revisedId = (await (await revised).json()).id;
  expect(revisedId).not.toBe(submissionId);
  await expect(page.getByText("Сохранено", { exact: true })).toBeVisible();
  await page.goto(`/app/tests/${course.testId}`);
  await page
    .getByRole("button", { name: "Начать тест / Продолжить обучение" })
    .click();
  await page.getByRole("radio", { name: "2", exact: true }).check();
  await expect(page.getByText("Ответ сохранён", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("radio", { name: "2", exact: true }),
  ).toBeChecked();
  await page
    .getByRole("button", { name: "Завершить тест", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Подтвердить", exact: true })
    .click();
  await expect(page.getByText("100.00 / 100", { exact: true })).toBeVisible();
  await logout(page);
  await login(page, teacherEmail, teacherPassword);
  await page.goto(`/app/submissions/${revisedId}`);
  await page.getByLabel("Балл", { exact: true }).fill("80");
  await page
    .getByLabel("Комментарий преподавателя")
    .fill("Accepted synthetic solution.");
  await page.getByRole("button", { name: "Оценить", exact: true }).click();
  await expect(page.getByText("Сохранено", { exact: true })).toBeVisible();
  await page.goto(`/app/courses/${course.courseId}`);
  await page
    .getByRole("button", {
      name: "Редактировать опубликованный курс",
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(/version=/);
  await expect(page.getByText(/Черновик.*v2/)).toBeVisible();
  await page.getByRole("button", { name: "Опубликовать", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Подтвердить", exact: true })
    .click();
  await expect(page.getByText(/Опубликован.*v2/)).toBeVisible();
  await logout(page);
  await login(page, studentEmail, resetPassword);
  const tree = await (
    await page.request.get(`/api/v1/courses/${course.courseId}/tree/`)
  ).json();
  expect(tree.version.id).toBe(course.versionId);
  const summaries = await (
    await page.request.get(
      `/api/v1/enrollments/summaries/?course=${course.courseId}`,
    )
  ).json();
  expect(summaries.results[0].grades.score).toBe(90);
  expect(summaries.results[0].progress.percent).toBe(100);
  await page.goto(`/app/grades?course=${course.courseId}`);
  await expect(page.getByText("90 / 100", { exact: true })).toBeVisible();
});

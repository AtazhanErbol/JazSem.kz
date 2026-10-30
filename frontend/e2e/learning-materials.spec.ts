import { test, expect, type Page } from "@playwright/test";
import type { Tree } from "../src/entities/types";

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.DEV_SEED_PASSWORD!);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
}
async function post(page: Page, path: string, data: unknown) {
  const csrf = (await page.context().cookies()).find(
    (cookie) => cookie.name === "csrftoken",
  )!.value;
  const result = await page.request.post(`/api/v1/${path}`, {
    data,
    headers: { "X-CSRFToken": csrf },
  });
  expect(result.ok(), await result.text()).toBe(true);
  return result.json();
}

test("teacher authors lecture/files/videos/test and AI draft; students read only published materials", async ({
  page,
  browser,
}) => {
  test.setTimeout(240000);
  if (!process.env.DEV_SEED_PASSWORD || process.env.E2E_FAKE_PROVIDER !== "1")
    throw new Error("Isolated synthetic services required");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page, "teacher@example.test");
  await page.goto("/app/courses?create=1");
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Дисциплина", { exact: true })
    .selectOption({ label: "Прикладная математика" });
  await dialog
    .getByLabel("Название", { exact: true })
    .fill(`Authoring materials ${Date.now()}`);
  await dialog
    .getByRole("button", { name: "Создать и перейти к наполнению" })
    .click();
  await expect(dialog).not.toBeVisible();
  const course = new URL(page.url()).pathname.split("/").pop()!;
  const save = async () => {
    await dialog
      .getByRole("button", { name: "Сохранить", exact: true })
      .click();
    await expect(dialog).not.toBeVisible();
  };
  const tab = (name: string) =>
    dialog.getByRole("button", { name, exact: true }).click();
  await page.getByRole("button", { name: "Добавить неделю" }).first().click();
  await dialog.getByLabel("Название", { exact: true }).fill("Authoring week");
  await save();
  await page.getByRole("button", { name: "Добавить тему" }).first().click();
  await dialog
    .getByLabel("Название", { exact: true })
    .fill("Equations · Ә Ғ Қ Ң Ө Ұ Ү Һ І");
  await tab("Содержание и инструкция");
  const original =
    "## Introduction\n\nУчебный текст. Қазақша мәтін. English text.\n\n### Example\n\n- First\n  - Nested\n\n| Step | Value |\n| --- | --- |\n| 1 | $x=2$ |\n\n## Conclusion\n\nCheck the answer.";
  await dialog
    .getByRole("textbox", { name: "Контент", exact: true })
    .fill(original);
  await tab("Прикреплённые материалы");
  await dialog
    .getByRole("button", { name: "Сохранить черновик и продолжить" })
    .click();
  await expect(dialog.locator('input[type="file"]')).toBeEnabled();
  await dialog.locator('input[type="file"]').setInputFiles([
    {
      name: "first.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("First educational file"),
    },
    {
      name: "second.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Second educational file"),
    },
  ]);
  await expect(dialog.locator(".attachment-row")).toHaveCount(2);
  const first = dialog
    .locator(".attachment-row")
    .filter({ hasText: "first.txt" });
  await first.getByRole("button", { name: /^Редактировать:/ }).click();
  await first.getByLabel("Отображаемое название").fill("Renamed resource");
  await first.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(
    first.getByText("Renamed resource", { exact: true }),
  ).toBeVisible();
  await tab("Глазами студента");
  await expect(dialog.getByRole("table")).toBeVisible();
  await page.screenshot({
    path: "../.runtime/authoring-materials-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "../.runtime/authoring-materials-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1080 });
  await tab("ИИ-ассистент");
  await expect(
    dialog.getByRole("button", { name: "Создать лекцию с ИИ", exact: true }),
  ).toBeEnabled();
  await dialog
    .getByRole("button", { name: "Создать лекцию с ИИ", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Использовать в редакторе" }),
  ).toBeEnabled({ timeout: 45000 });
  const aiText = dialog.getByRole("textbox", { name: "Контент", exact: true });
  const generated = await aiText.inputValue();
  expect(generated.split(/\s+/).length).toBeGreaterThan(1200);
  await aiText.fill(generated + "\n\nManual instructor correction.");
  await dialog.getByRole("button", { name: "Сохранить AI-черновик" }).click();
  page.once("dialog", (confirmation) => confirmation.accept());
  await dialog
    .getByRole("button", { name: "Использовать в редакторе" })
    .click();
  await expect(
    dialog.getByRole("textbox", { name: "Контент", exact: true }),
  ).toHaveValue(/Manual instructor correction/);
  await dialog.getByRole("button", { name: "Отменить замену текста" }).click();
  await expect(
    dialog.getByRole("textbox", { name: "Контент", exact: true }),
  ).toHaveValue(original);
  await tab("ИИ-ассистент");
  page.once("dialog", (confirmation) => confirmation.accept());
  await dialog
    .getByRole("button", { name: "Использовать в редакторе" })
    .click();
  await save();
  await page.getByRole("button", { name: "+ Задания", exact: true }).click();
  await dialog.getByLabel("Название", { exact: true }).fill("Video assignment");
  await tab("Содержание и инструкция");
  await dialog
    .getByRole("textbox", { name: "Инструкция", exact: true })
    .fill("Watch both videos and explain the equivalent transformations.");
  await tab("Видеоматериалы");
  await dialog
    .getByRole("button", { name: "Сохранить черновик и продолжить" })
    .click();
  // Produce a real browser-playable WebM locally; no remote media or paid provider.
  const videoBytes = await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 180;
    const context = canvas.getContext("2d")!;
    const stream = canvas.captureStream(10),
      recorder = new MediaRecorder(stream, {
        mimeType: "video/webm;codecs=vp8",
      });
    const chunks: Blob[] = [];
    const done = new Promise<number[]>((resolve) => {
      recorder.ondataavailable = (event) => chunks.push(event.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        resolve(
          Array.from(new Uint8Array(await new Blob(chunks).arrayBuffer())),
        );
      };
    });
    recorder.start();
    let frame = 0;
    const timer = setInterval(() => {
      context.fillStyle = frame++ % 2 ? "#ed1935" : "#172033";
      context.fillRect(0, 0, 320, 180);
    }, 60);
    setTimeout(() => {
      clearInterval(timer);
      recorder.stop();
    }, 650);
    return done;
  });
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "native-demo.webm",
    mimeType: "video/webm",
    buffer: Buffer.from(videoBytes),
  });
  await expect(dialog.locator(".attachment-row")).toHaveCount(1);
  await dialog
    .getByRole("button", { name: "Добавить YouTube", exact: true })
    .click();
  await dialog.getByLabel("Отображаемое название").fill("YouTube example");
  await dialog
    .getByLabel("Ссылка на YouTube")
    .fill("https://evil.example/video");
  await dialog.getByRole("button", { name: "Добавить", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("YouTube");
  await dialog
    .getByLabel("Ссылка на YouTube")
    .fill("https://youtube.com/shorts/dQw4w9WgXcQ");
  await dialog.getByRole("button", { name: "Добавить", exact: true }).click();
  await expect(dialog.locator(".attachment-row")).toHaveCount(2);
  await tab("Прикреплённые материалы");
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "assignment.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Assignment resource"),
  });
  await expect(dialog.locator(".attachment-row")).toHaveCount(1);
  await dialog
    .locator(".form-actions")
    .getByRole("button", { name: "Отмена", exact: true })
    .click();
  await page.getByRole("button", { name: "+ Тесты", exact: true }).click();
  await dialog.getByLabel("Название", { exact: true }).fill("Materials quiz");
  await tab("Прикреплённые материалы");
  await dialog
    .getByRole("button", { name: "Сохранить черновик и продолжить" })
    .click();
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "reference.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("symbol,value\nx,2\n"),
  });
  await expect(dialog.locator(".attachment-row")).toHaveCount(1);
  await dialog
    .locator(".form-actions")
    .getByRole("button", { name: "Отмена", exact: true })
    .click();
  const tree: Tree = await (
    await page.request.get(`/api/v1/courses/${course}/tree/`)
  ).json();
  const topic = tree.weeks[0].topics[0],
    assignment = topic.assignments[0],
    quiz = topic.tests[0];
  expect(topic.content).toContain("Manual instructor correction");
  const question = await post(page, "questions/", {
    test: quiz.id,
    text: "1 + 1 = ?",
    type: "SINGLE_CHOICE",
    score: 1,
  });
  await post(page, "options/", {
    question: question.id,
    text: "2",
    is_correct: true,
  });
  await post(page, "options/", {
    question: question.id,
    text: "3",
    is_correct: false,
  });
  await post(page, `courses/${course}/grading-weights/`, {
    version: tree.version.id,
    weights: { ASSIGNMENTS: 50, TESTS: 50 },
  });
  await page.reload();
  await page.getByRole("button", { name: "Опубликовать", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Подтвердить", exact: true })
    .click();
  await expect(page.getByText(/Опубликован.*v1/)).toBeVisible();
  const students = await (
    await page.request.get(
      "/api/v1/users/?role=STUDENT&search=student@example.test",
    )
  ).json();
  await post(page, `courses/${course}/assign/`, {
    student: students.results.find(
      (student: { email: string }) => student.email === "student@example.test",
    ).id,
  });
  const context = await browser.newContext();
  const studentPage = await context.newPage();
  await login(studentPage, "student@example.test");
  await studentPage.goto(`/app/courses/${course}`);
  await studentPage
    .getByRole("button", { name: topic.title, exact: true })
    .click();
  await expect(
    studentPage.getByRole("heading", {
      name: "Дополнительные материалы",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    studentPage.getByText("Renamed resource", { exact: true }),
  ).toBeVisible();
  const download = studentPage.getByRole("link", {
    name: "Скачать файл: Renamed resource",
    exact: true,
  });
  const downloaded = await studentPage.request.get(
    (await download.getAttribute("href"))!,
  );
  expect(await downloaded.text()).toBe("First educational file");
  await studentPage.goto(`/app/assignments/${assignment.id}`);
  const uploaded = studentPage
    .locator(".attachment-row")
    .filter({ hasText: "native-demo" });
  await uploaded
    .getByRole("button", { name: "Предпросмотр", exact: true })
    .click();
  await expect
    .poll(() =>
      uploaded
        .locator("video")
        .evaluate((element: HTMLVideoElement) => element.readyState),
    )
    .toBeGreaterThanOrEqual(2);
  await uploaded
    .locator("video")
    .evaluate(async (element: HTMLVideoElement) => {
      element.muted = true;
      await element.play();
    });
  await expect
    .poll(() =>
      uploaded
        .locator("video")
        .evaluate((element: HTMLVideoElement) => element.currentTime),
    )
    .toBeGreaterThan(0);
  expect(await studentPage.locator(".attachment-actions .danger").count()).toBe(
    0,
  );
  await studentPage.goto(`/app/tests/${quiz.id}`);
  await expect(
    studentPage.getByText("reference.csv", { exact: false }),
  ).toBeVisible();
  const testJson = await (
    await studentPage.request.get(`/api/v1/tests/${quiz.id}/`)
  ).json();
  expect(JSON.stringify(testJson)).not.toMatch(
    /is_correct|explanation|source_chunks/,
  );
  await studentPage.getByRole("button", { name: /Начать.*Продолжить/ }).click();
  await expect(
    studentPage.getByText("1 + 1 = ?", { exact: false }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  await context.close();
});

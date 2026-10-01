import { test, expect } from "@playwright/test";

test("real AI HTTP/outbox/Redis/worker flow: sources, review, reload, regenerate, import and publish", async ({
  page,
}) => {
  test.setTimeout(300000);
  if (!process.env.DEV_SEED_PASSWORD || process.env.E2E_FAKE_PROVIDER !== "1")
    throw new Error(
      "Isolated fake-provider services are mandatory; never use a paid provider",
    );
  await page.goto("/login");
  await page.getByLabel("Email").fill("teacher@example.test");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.DEV_SEED_PASSWORD);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  const status = await (await page.request.get("/api/v1/ai-status/")).json();
  expect(status).toMatchObject({
    enabled: true,
    configured: true,
    model: "synthetic-no-network",
  });
  await page.goto("/app/courses?create=1");
  const modal = page.getByRole("dialog");
  await modal
    .getByLabel("Дисциплина", { exact: true })
    .selectOption({ label: "Прикладная математика" });
  await modal
    .getByLabel("Название", { exact: true })
    .fill(`AI integration ${Date.now()}`);
  await modal
    .getByRole("button", { name: "Создать и перейти к наполнению" })
    .click();
  await expect(modal).not.toBeVisible();
  const course = new URL(page.url()).pathname.split("/").pop()!;
  await page.goto(`/app/ai?course=${course}`);
  // A failed upload and cancelled navigation must preserve the actual File.
  const retainedFile = page.locator('input[type="file"]');
  await retainedFile.setInputFiles({name: "retained.txt", mimeType: "text/plain", buffer: Buffer.from("Synthetic retained selection")});
  await page.route("**/api/v1/sources/", async route => {
    if (route.request().method() === "POST") await route.abort("failed");
    else await route.continue();
  });
  await page.getByRole("button", {name: "Загрузить", exact: true}).click();
  await expect(page.getByRole("button", {name: "Загрузить", exact: true})).toBeEnabled();
  await page.unroute("**/api/v1/sources/");
  expect(await retainedFile.evaluate(el => (el as HTMLInputElement).files?.[0]?.name)).toBe("retained.txt");
  page.once("dialog", dialog => dialog.dismiss());
  await page.locator(".help-card").getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/app/ai\\?course=${course}`));
  expect(await retainedFile.evaluate(el => (el as HTMLInputElement).files?.[0]?.name)).toBe("retained.txt");
  const upload = async (name: string, body: string) => {
    await page
      .locator('input[type="file"]')
      .setInputFiles({
        name,
        mimeType: "text/plain",
        buffer: Buffer.from(body),
      });
    const saved = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/v1/sources/") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Загрузить", exact: true }).click();
    const response = await saved;
    expect(response.status()).toBe(201);
    return (await response.json()).id as string;
  };
  await upload("empty-source.txt", "     \n    ");
  const failed = page
    .locator(".source-row")
    .filter({ hasText: "empty-source.txt" });
  await expect(
    failed.getByRole("button", { name: "Повторить", exact: true }),
  ).toBeVisible({ timeout: 45000 });
  await failed.getByRole("button", { name: "Повторить", exact: true }).click();
  await expect(
    failed.getByRole("button", { name: "Повторить", exact: true }),
  ).toBeVisible({ timeout: 45000 });
  await failed.getByRole("button", { name: "Исключить", exact: true }).click();
  await expect(failed.getByRole("checkbox")).toBeDisabled();
  const source = await upload(
    "synthetic-lesson.txt",
    "One plus one equals two. Бірге бірді қосқанда екі болады. Один плюс один равно двум.",
  );
  const selected = page.getByRole("checkbox", {
    name: "synthetic-lesson.txt",
    exact: true,
  });
  await expect(selected).toBeEnabled({ timeout: 45000 });
  await selected.check();
  await page.getByLabel("Недели", { exact: true }).fill("1");
  const create = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/ai-jobs/") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Создать черновик", exact: true })
    .click();
  const created = await create;
  expect(created.status()).toBe(202);
  const job = await created.json();
  expect(job).not.toHaveProperty("source_snapshot");
  await expect(page.locator(".draft-editor")).toBeVisible({ timeout: 60000 });
  await expect(page).toHaveURL(new RegExp(`job=${job.id}`));
  const draftTitle = page
    .locator(".draft-editor")
    .getByLabel("Название", { exact: true })
    .first();
  await draftTitle.fill("Reviewed synthetic course");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Сохранить", exact: true }),
  ).toBeDisabled();
  await page.reload();
  await expect(draftTitle).toHaveValue("Reviewed synthetic course");
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
  }
  await page.getByRole("button", { name: "Қазақша", exact: true }).click();
  await expect(draftTitle).toHaveCount(0); // Labels translate without losing the selected job.
  expect(new URL(page.url()).searchParams.get("job")).toBe(job.id);
  await page.getByRole("button", { name: "Русский", exact: true }).click();
  await expect(draftTitle).toHaveValue("Reviewed synthetic course");
  await page.locator(".draft-topic summary").click();
  await page
    .locator(".draft-topic")
    .getByLabel("Инструкция · AI", { exact: true })
    .fill("Уточните объяснение по источнику");
  const regeneration = page.waitForResponse(
    (r) => r.url().endsWith("/regenerate/") && r.request().method() === "POST",
  );
  await page
    .locator(".draft-topic")
    .getByRole("button", { name: "↻ Создать черновик", exact: true })
    .click();
  const regenerated = await regeneration;
  expect(regenerated.status()).toBe(202);
  await expect(page.locator(".draft-topic summary")).toHaveText(
    "Обновлённая тема / Жаңартылған тақырып",
    { timeout: 60000 },
  );
  const activeId = new URL(page.url()).searchParams.get("job");
  const draft = await (
    await page.request.get(`/api/v1/ai-jobs/${activeId}/draft/`)
  ).json();
  const chunks = await (
    await page.request.get(`/api/v1/sources/${source}/chunks/`)
  ).json();
  expect(draft.data.weeks[0].topics[0].source_chunks).toEqual([
    chunks.results[0].id,
  ]);
  await page
    .getByRole("button", { name: "Подтвердить черновик", exact: true })
    .click();
  await modal.getByRole("button", { name: "Подтвердить", exact: true }).click();
  await expect(modal).not.toBeVisible();
  const confirmed = await (
    await page.request.get(`/api/v1/ai-drafts/${draft.id}/`)
  ).json();
  const csrf = (await (await page.request.get("/api/v1/auth/login/")).json())
    .csrfToken;
  const repeat = await page.request.post(
    `/api/v1/ai-drafts/${draft.id}/confirm/`,
    { data: {}, headers: { "X-CSRFToken": csrf } },
  );
  expect((await repeat.json()).id).toBe(confirmed.imported_version);
  await page
    .getByRole("link", { name: "Редактор курса → Опубликовать" })
    .click();
  await page.getByRole("button", { name: "Опубликовать", exact: true }).click();
  await modal.getByRole("button", { name: "Подтвердить", exact: true }).click();
  await expect(modal).not.toBeVisible();
  const tree = await (
    await page.request.get(`/api/v1/courses/${course}/tree/`)
  ).json();
  expect(tree.version.id).toBe(confirmed.imported_version);
  expect(tree.version.status).toBe("PUBLISHED");
});

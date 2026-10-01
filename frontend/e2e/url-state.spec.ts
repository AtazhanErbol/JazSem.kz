import { test, expect } from "@playwright/test";

test("real server pagination/search, Back/Forward, remote options and keyboard mobile navigation", async ({
  page,
}) => {
  test.setTimeout(120000);
  if (!process.env.DEV_SEED_PASSWORD)
    throw new Error("Synthetic fixtures required");
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.test");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.DEV_SEED_PASSWORD);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  const csrf = (await (await page.request.get("/api/v1/auth/login/")).json())
    .csrfToken;
  const teachers = await (
    await page.request.get(
      "/api/v1/users/?role=TEACHER&search=teacher%40example.test",
    )
  ).json();
  const prefix = `Paging-${Date.now()}`;
  const rows: { id: string; name: string }[] = [];
  for (let index = 0; index < 26; index++) {
    const response = await page.request.post("/api/v1/disciplines/", {
      headers: { "X-CSRFToken": csrf },
      data: {
        name: `${prefix} ${String(index).padStart(2, "0")} Ә Ғ Қ Ң Ө Ұ Ү Һ І ұзақ атау`,
        code: `${prefix}-${index}`,
        teachers: [teachers.results[0].id],
      },
    });
    expect(response.status()).toBe(201);
    rows.push(await response.json());
  }
  await page.goto(`/app/disciplines?search=${prefix}`);
  await expect(page.locator(".record-row")).toHaveCount(25);
  await page
    .getByRole("navigation", { name: "Страницы" })
    .getByRole("button", { name: "Далее", exact: true })
    .click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.locator(".record-row")).toHaveCount(1);
  const second = (await page.locator(".record-row").textContent())!;
  await page.reload();
  await expect(page.locator(".record-row")).toHaveText(second);
  await page.goBack();
  await expect(page.locator(".record-row")).toHaveCount(25);
  await page.goForward();
  await expect(page.locator(".record-row")).toHaveText(second);
  await page.getByLabel("Поиск", { exact: true }).fill(rows[0].name);
  await expect
    .poll(() => new URL(page.url()).searchParams.get("page"))
    .toBeNull();
  await expect(page.locator(".record-row")).toHaveCount(1);
  await expect(page.locator(".record-row")).toContainText(rows[0].name);
  await page.goto("/app/courses?create=1");
  const dialog = page.getByRole("dialog");
  const selector = dialog.locator(".remote-select").first();
  await selector.getByRole("searchbox").fill(prefix);
  await expect(selector.getByRole("option")).toHaveCount(26); // placeholder + page 1
  await selector.getByRole("button", { name: "Далее", exact: true }).click();
  await expect(selector.getByRole("option")).toHaveCount(2);
  const lastId = await selector
    .getByRole("option")
    .last()
    .getAttribute("value");
  await selector.getByRole("combobox").selectOption(lastId!);
  await selector.getByRole("searchbox").fill("Прикладная математика");
  await expect(selector.getByRole("combobox")).toHaveValue(lastId!);
  await expect(selector.locator("option:checked")).not.toHaveText("—");
  await dialog.getByRole("button", { name: "Закрыть", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByRole("button", { name: "Қазақша", exact: true }).click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    if (width <= 768) {
      const menu = page.locator("button[aria-controls='workspace-navigation']");
      await menu.focus();
      await page.keyboard.press("Enter");
      await expect(menu).toHaveAttribute("aria-expanded", "true");
      expect(
        await page
          .locator("aside")
          .evaluate((el) => el.contains(document.activeElement)),
      ).toBe(true);
      await page.keyboard.press("Shift+Tab");
      expect(
        await page
          .locator("aside")
          .evaluate((el) => el.contains(document.activeElement)),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(menu).toBeFocused();
    }
    await page.getByRole("button", { name: "Русский", exact: true }).click();
  }
  // 200% text zoom/reflow at desktop effective width 640 CSS px.
  await page.setViewportSize({ width: 640, height: 450 });
  await page.locator("html").evaluate((el) => (el.style.fontSize = "200%"));
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
});

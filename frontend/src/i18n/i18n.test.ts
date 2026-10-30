import { kkLearningDisplay } from "./learningDisplay";
import { expect, it } from "vitest";
import i18n from "./index";
import { kkUX } from "./ux";
import { kkWorkspace } from "./workspace";
import { ruAIRecovery, kkAIRecovery } from "./operations";

it("Kazakh interface extensions override the Russian fallback", () => {
  for (const [key, value] of Object.entries(kkUX))
    expect(i18n.t(key, { lng: "kk" }), key).toBe(value);
  for (const [key, value] of Object.entries(kkWorkspace))
    expect(i18n.t(`workspace.${key}`, { lng: "kk" }), key).toBe(value);
});

it("Kazakh result explanations do not fall back to Russian", () => {
  for (const [key, value] of Object.entries(kkLearningDisplay))
    expect(
      i18n.t(`learningDisplay.${key}`, { lng: "kk", skipInterpolation: true }),
      key,
    ).toBe(value);
});

it("AI failure messages explain billing and request errors in both languages", () => {
  expect(Object.keys(kkAIRecovery.errors)).toEqual(
    Object.keys(ruAIRecovery.errors),
  );
  for (const code of Object.keys(ruAIRecovery.errors)) {
    const key = code as keyof typeof ruAIRecovery.errors;
    expect(i18n.t(`aiRecovery.errors.${code}`, { lng: "ru" })).toBe(
      ruAIRecovery.errors[key],
    );
    expect(i18n.t(`aiRecovery.errors.${code}`, { lng: "kk" })).toBe(
      kkAIRecovery.errors[key],
    );
  }
  expect(ruAIRecovery.errors.AI_CREDITS_EXHAUSTED).toContain(
    "пополнить баланс",
  );
  expect(ruAIRecovery.errors.AI_RATE_LIMITED).toContain("частоту запросов");
});

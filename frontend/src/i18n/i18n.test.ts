import { kkLearningDisplay } from "./learningDisplay";
import { expect, it } from "vitest";
import i18n from "./index";
import { kkUX } from "./ux";
import { kkWorkspace } from "./workspace";

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

import { expect, it } from "vitest";
import i18n from "./index";
import { kkUX } from "./ux";

it("Kazakh interface extensions override the Russian fallback", () => {
  for (const [key, value] of Object.entries(kkUX))
    expect(i18n.t(key, { lng: "kk" }), key).toBe(value);
});

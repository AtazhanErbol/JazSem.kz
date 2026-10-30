import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "../../i18n";
import {
  ContentEditor,
  LearningContent,
  lectureSections,
} from "./LearningContent";

describe("learning content", () => {
  it("renders multilingual headings, nested lists, tables and math", () => {
    const { container } = render(
      <LearningContent
        language="kk"
        content={
          "## Ә Ғ Қ Ң Ө Ұ Ү Һ І\n\nҚазақша мәтін. Русский текст. English text.\n\n### Example\n\n- One\n  - Two\n\n| A | B |\n| --- | --- |\n| $x^2$ | 4 |"
        }
      />,
    );
    expect(screen.getByRole("heading", { level: 2 }).textContent).toContain(
      "Ә Ғ Қ",
    );
    expect(container.querySelectorAll("ul")).toHaveLength(2);
    expect(screen.getByRole("table")).toBeTruthy();
    expect(container.querySelector(".katex")).toBeTruthy();
    expect(
      container.querySelector(".learning-prose")?.getAttribute("lang"),
    ).toBe("kk");
  });
  it("does not execute HTML, iframe, image or unsafe math links", () => {
    const { container } = render(
      <LearningContent
        content={
          '<script>window.compromised = true</script>\n\n<iframe src="https://evil.test"></iframe>\n\n![tracking](https://evil.test/pixel)\n\n[click](javascript:alert(1))\n\n$\\href{javascript:alert(1)}{x}$'
        }
      />,
    );
    expect(container.querySelector("script,iframe,img,object")).toBeNull();
    expect(
      Array.from(container.querySelectorAll("a")).some((link) =>
        link.getAttribute("href")?.startsWith("javascript:"),
      ),
    ).toBe(false);
  });
  it("keeps external references isolated from the opener", () => {
    render(<LearningContent content="[Python](https://docs.python.org/3/)" />);
    expect(screen.getByRole("link").getAttribute("rel")).toBe(
      "noopener noreferrer",
    );
  });
  it("selects real H2 sections rather than headings in fenced examples", () => {
    const content =
      "## One 😀\n\n```python\n## Example comment\n```\n\n## Two\n\nFinal";
    const sections = lectureSections(content);
    expect(sections.map((section) => section.heading)).toEqual([
      "One 😀",
      "Two",
    ]);
    expect(content.slice(sections[1].start, sections[1].end)).toBe("\nFinal");
  });
  it("inserts a selected phrase as a formatted heading without losing surrounding text", () => {
    const onChange = vi.fn();
    render(
      <ContentEditor
        label="Lecture"
        value="Before selected after"
        onChange={onChange}
      />,
    );
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    textarea.setSelectionRange(7, 15);
    fireEvent.click(screen.getByRole("button", { name: "Подзаголовок" }));
    expect(onChange).toHaveBeenCalledWith("Before \n\n## selected\n\n after");
  });
});

import { useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

export function LearningContent({
  content,
  language,
}: {
  content: string;
  language?: string;
}) {
  return (
    <div className="learning-prose" lang={language}>
      <Markdown
        skipHtml
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[
          [
            rehypeKatex,
            { trust: false, throwOnError: false, maxExpand: 1000, maxSize: 20 },
          ],
        ]}
        disallowedElements={[
          "iframe",
          "script",
          "style",
          "input",
          "form",
          "object",
          "embed",
          "img",
        ]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="learning-table-scroll" tabIndex={0}>
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </Markdown>
    </div>
  );
}

export function lectureSections(content: string) {
  const result: { heading: string; start: number; end: number }[] = [];
  let offset = 0,
    fence = "";
  for (const line of content.match(/[^\n]*\n|[^\n]+$/g) || []) {
    const marker = line.match(/^\s{0,3}(`{3,}|~{3,})/)?.[1][0];
    if (marker) fence = fence === marker ? "" : fence || marker;
    if (!fence && /^##\s+\S/.test(line)) {
      if (result.length) result[result.length - 1].end = offset;
      result.push({
        heading: line.replace(/^##\s+/, "").trim(),
        start: offset + line.length,
        end: content.length,
      });
    }
    offset += line.length;
  }
  return result;
}

export function ContentEditor({
  value,
  onChange,
  label,
  language,
  invalid,
  onSelectSection,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  language?: string;
  invalid?: boolean;
  onSelectSection?: (index: number) => void;
}) {
  const { t } = useTranslation();
  const [preview, setPreview] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);
  const helpId = useId();
  const insert = (template: string) => {
    const textarea = ref.current;
    if (!textarea) return;
    const { selectionStart: start, selectionEnd: end } = textarea;
    const text = template.replace(
      "{text}",
      value.slice(start, end) || t("authoring.content"),
    );
    onChange(value.slice(0, start) + text + value.slice(end));
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + text.length, start + text.length);
    });
  };
  return (
    <div className="content-editor">
      <div
        className="editor-tabs"
        role="group"
        aria-label={`${t("authoring.editText")}: ${label}`}
      >
        <button
          type="button"
          aria-pressed={!preview}
          onClick={() => setPreview(false)}
        >
          {t("authoring.editText")}
        </button>
        <button
          type="button"
          aria-pressed={preview}
          onClick={() => setPreview(true)}
        >
          {t("authoring.renderText")}
        </button>
        <small>
          {t("authoring.words", {
            count: value.trim() ? value.trim().split(/\s+/).length : 0,
          })}
        </small>
      </div>
      {preview ? (
        <LearningContent content={value} language={language} />
      ) : (
        <>
          <div
            className="editor-toolbar"
            role="group"
            aria-label={t("authoring.editText")}
          >
            {[
              ["heading", "\n\n## {text}\n\n"],
              ["subheading", "\n\n### {text}\n\n"],
              ["list", "\n\n- {text}\n- \n"],
              ["table", "\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"],
              ["formula", "\n\n$$\nE = mc^2\n$$\n\n"],
            ].map(([key, text]) => (
              <button key={key} type="button" onClick={() => insert(text)}>
                {t(`authoring.${key}`)}
              </button>
            ))}
          </div>
          <textarea
            ref={ref}
            className="lecture-textarea"
            aria-label={label}
            aria-invalid={invalid}
            aria-describedby={helpId}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            rows={18}
            lang={language}
            onSelect={(event) => {
              const position = event.currentTarget.selectionStart;
              const index = lectureSections(value).findIndex(
                (section) =>
                  position >= section.start && position <= section.end,
              );
              if (index >= 0) onSelectSection?.(index);
            }}
          />
        </>
      )}
      <small id={helpId} className="muted">
        {t("authoring.markdownHelp")}
      </small>
    </div>
  );
}

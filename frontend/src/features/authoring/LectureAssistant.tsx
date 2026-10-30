import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { api } from "../../services/api";
import { useAction } from "../../hooks/useAction";
import { Badge, ErrorState, Loading, ProgressBar } from "../../components/UI";
import { Pagination } from "../../components/Pagination";
import type { AIJob, AIDraft, SourceDocument } from "../../entities/ai";
import type { Page } from "../../entities/types";
import { ContentEditor, lectureSections } from "./LearningContent";

export interface LectureReview {
  kind: "lecture";
  title: string;
  language: "ru" | "kk" | "en";
  content: string;
  source_gaps: string[];
}
function DraftEditor({
  draft,
  applyDraft,
  dirty,
}: {
  draft: AIDraft<LectureReview>;
  applyDraft: (draft: LectureReview) => void;
  dirty: (value: boolean) => void;
}) {
  const { t } = useTranslation(),
    action = useAction(),
    cache = useQueryClient();
  const [content, setContent] = useState(draft.data.content),
    [savedContent, setSavedContent] = useState(draft.data.content);
  useEffect(() => {
    dirty(content !== savedContent);
    return () => dirty(false);
  }, [content, savedContent, dirty]);
  async function save(apply = false) {
    const data = { ...draft.data, content };
    if (content !== savedContent) {
      const result = await action.run<AIDraft<LectureReview>>(
        `ai-drafts/${draft.id}/`,
        { data },
        "PATCH",
      );
      if (!result.ok) return;
      setSavedContent(content);
      cache.setQueryData(["lecture-draft", draft.job], result.data);
    }
    if (apply) applyDraft(data);
  }
  return (
    <section
      className="lecture-ai-draft"
      data-dirty={content !== savedContent}
      data-pending={action.pending}
    >
      <h3>{draft.data.title}</h3>
      <p className="muted">{t("authoring.draftHint")}</p>
      {draft.data.source_gaps.length > 0 && (
        <details>
          <summary>{t("authoring.gaps")}</summary>
          <ul>
            {draft.data.source_gaps.map((gap, i) => (
              <li key={i}>{gap}</li>
            ))}
          </ul>
        </details>
      )}
      <ContentEditor
        value={content}
        onChange={setContent}
        label={t("content")}
        language={draft.data.language}
      />
      {action.feedback}
      <div className="row-actions">
        <button
          type="button"
          disabled={action.pending || content === savedContent}
          onClick={() => void save()}
        >
          {t("authoring.saveAIDraft")}
        </button>
        <button
          type="button"
          className="primary"
          disabled={action.pending}
          onClick={() => void save(true)}
        >
          {t("authoring.useDraft")}
        </button>
      </div>
    </section>
  );
}

export function LectureAssistant({
  topic,
  title,
  content,
  course,
  selectedSection,
  onSelectSection,
  onUse,
  onDirtyChange,
}: {
  topic: string;
  title: string;
  content: string;
  course?: string;
  selectedSection: number;
  onSelectSection: (index: number) => void;
  onUse: (draft: LectureReview) => void;
  onDirtyChange: (value: boolean) => void;
}) {
  const { t, i18n } = useTranslation(),
    action = useAction(),
    cache = useQueryClient();
  const [language, setLanguage] = useState(
    i18n.language === "kk" ? "kk" : "ru",
  );
  const [audience, setAudience] = useState(""),
    [complexity, setComplexity] = useState("intermediate");
  const [objective, setObjective] = useState(""),
    [outcomes, setOutcomes] = useState(""),
    [instruction, setInstruction] = useState("");
  const [detail, setDetail] = useState("detailed"),
    [sources, setSources] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState(""),
    [page, setPage] = useState(1);
  const status = useQuery({
    queryKey: ["ai-status"],
    queryFn: () =>
      api<{ enabled: boolean; configured: boolean; worker_available: boolean }>(
        "ai-status/",
      ),
    staleTime: 30000,
  });
  const history = useQuery({
    queryKey: ["lecture-jobs", topic, page],
    queryFn: () =>
      api<Page<AIJob>>(
        `ai-jobs/?type=LECTURE&topic=${topic}&ordering=-created_at&page=${page}`,
      ),
  });
  const sourceList = useQuery({
    queryKey: ["lecture-sources", course],
    enabled: !!course,
    queryFn: () =>
      api<Page<SourceDocument>>(
        `sources/?course=${course}&processing_status=COMPLETED&excluded=false`,
      ),
  });
  const activeId = selectedId || history.data?.results[0]?.id || "";
  const job = useQuery({
    queryKey: ["lecture-job", activeId],
    enabled: !!activeId,
    queryFn: () => api<AIJob>(`ai-jobs/${activeId}/`),
    refetchInterval: (query) =>
      ["QUEUED", "PROCESSING"].includes(query.state.data?.status || "") &&
      !query.state.error
        ? 2000
        : false,
  });
  const draft = useQuery({
    queryKey: ["lecture-draft", activeId],
    enabled: job.data?.status === "COMPLETED",
    queryFn: () => api<AIDraft<LectureReview>>(`ai-jobs/${activeId}/draft/`),
  });
  const waiting = ["QUEUED", "PROCESSING"].includes(job.data?.status || "");
  const ready =
    status.data?.enabled &&
    status.data.configured &&
    status.data.worker_available;
  const choices = lectureSections(content);
  async function start(operation: string) {
    if (!ready) return;
    const result = await action.run<AIJob>("ai-jobs/lecture/", {
      topic,
      title,
      language,
      audience: audience || t("students"),
      complexity,
      objective,
      outcomes,
      instruction,
      detail,
      sources,
      operation,
      existing_content: content,
      ...(["EXPAND", "REGENERATE_SECTION"].includes(operation)
        ? { section_index: selectedSection }
        : {}),
    });
    if (result.ok) {
      setSelectedId(result.data.id);
      cache.setQueryData(["lecture-job", result.data.id], result.data);
      await cache.invalidateQueries({ queryKey: ["lecture-jobs", topic] });
    }
  }
  return (
    <div className="lecture-assistant">
      {status.isPending ? (
        <Loading />
      ) : status.error ? (
        <ErrorState error={status.error} />
      ) : (
        !ready && (
          <p className="notice" role="status">
            {t("authoring.providerMissing")}
          </p>
        )
      )}
      <div className="authoring-grid">
        <label>
          {t("authoring.language")}
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
          >
            <option value="ru">Русский</option>
            <option value="kk">Қазақша</option>
            <option value="en">English</option>
          </select>
        </label>
        <label>
          {t("authoring.complexity")}
          <select
            value={complexity}
            onChange={(event) => setComplexity(event.target.value)}
          >
            {["beginner", "intermediate", "advanced"].map((value) => (
              <option key={value} value={value}>
                {t(value === "beginner" ? "authoring.beginner" : value)}
              </option>
            ))}
          </select>
        </label>
        <label className="full-field">
          {t("authoring.audience")}
          <input
            value={audience}
            maxLength={1000}
            onChange={(event) => setAudience(event.target.value)}
          />
        </label>
        <label>
          {t("authoring.objective")}
          <textarea
            value={objective}
            rows={3}
            maxLength={3000}
            onChange={(event) => setObjective(event.target.value)}
          />
        </label>
        <label>
          {t("authoring.outcomes")}
          <textarea
            value={outcomes}
            rows={3}
            maxLength={4000}
            onChange={(event) => setOutcomes(event.target.value)}
          />
        </label>
        <label>
          {t("authoring.detail")}
          <select
            value={detail}
            onChange={(event) => setDetail(event.target.value)}
          >
            {["standard", "detailed", "comprehensive"].map((value) => (
              <option key={value} value={value}>
                {t(`authoring.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("authoring.section")}
          <select
            value={choices[selectedSection] ? selectedSection : ""}
            onChange={(event) => onSelectSection(Number(event.target.value))}
          >
            <option value="" disabled>
              {t("authoring.selectSection")}
            </option>
            {choices.map((section, index) => (
              <option key={index} value={index}>
                {section.heading}
              </option>
            ))}
          </select>
        </label>
        <label className="full-field">
          {t("authoring.instruction")}
          <textarea
            value={instruction}
            rows={3}
            maxLength={4000}
            onChange={(event) => setInstruction(event.target.value)}
          />
        </label>
      </div>
      {!!sourceList.data?.results.length && (
        <details>
          <summary>{t("authoring.sources")}</summary>
          {sourceList.data.results.map((source) => (
            <label className="check-label" key={source.id}>
              <input
                type="checkbox"
                checked={sources.includes(source.id)}
                onChange={(event) =>
                  setSources((old) =>
                    event.target.checked
                      ? [...old, source.id]
                      : old.filter((id) => id !== source.id),
                  )
                }
              />
              {source.filename}
            </label>
          ))}
        </details>
      )}
      {!sources.length && <p className="muted">{t("authoring.noSources")}</p>}
      <div className="row-actions">
        {[
          ["GENERATE", "createAI"],
          ["IMPROVE", "improve"],
          ["EXPAND", "expand"],
          ["REGENERATE_SECTION", "regenerate"],
        ].map(([operation, label]) => (
          <button
            key={operation}
            type="button"
            disabled={
              !ready ||
              action.pending ||
              waiting ||
              (operation !== "GENERATE" && !content.trim()) ||
              (["EXPAND", "REGENERATE_SECTION"].includes(operation) &&
                !choices[selectedSection])
            }
            onClick={() => void start(operation)}
          >
            <Sparkles size={16} />
            {t(`authoring.${label}`)}
          </button>
        ))}
      </div>
      {action.feedback}
      {job.error && <ErrorState error={job.error} />}
      {job.data && (
        <section className="lecture-job" aria-live="polite">
          <Badge>{job.data.status}</Badge>
          {waiting && (
            <>
              <p>{t("authoring.inQueue")}</p>
              <ProgressBar value={job.data.progress} />
              <button
                type="button"
                disabled={action.pending}
                onClick={async () => {
                  const result = await action.run(
                    `ai-jobs/${activeId}/cancel/`,
                  );
                  if (result.ok) await job.refetch();
                }}
              >
                {t("cancel")}
              </button>
            </>
          )}
          {job.data.status === "FAILED" && (
            <p className="field-error" role="alert">
              {job.data.error === "AI_LECTURE_TOO_SHORT"
                ? t("authoring.aiShort")
                : t("authoring.aiFailed", { code: job.data.error })}
            </p>
          )}
        </section>
      )}
      {job.data?.status === "COMPLETED" &&
        (draft.isPending ? (
          <Loading />
        ) : draft.error ? (
          <ErrorState error={draft.error} />
        ) : (
          draft.data && (
            <DraftEditor
              key={draft.data.id}
              draft={draft.data}
              applyDraft={onUse}
              dirty={onDirtyChange}
            />
          )
        ))}
      <details className="lecture-history">
        <summary>{t("authoring.history")}</summary>
        {history.error && <ErrorState error={history.error} />}
        {history.data?.results.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={item.id === activeId}
            onClick={() => {
              if (!window.confirm(t("ux.unsavedConfirm"))) return;
              setSelectedId(item.id);
            }}
          >
            {new Date(item.created_at).toLocaleString()} · {t(item.status)}
          </button>
        ))}
        <Pagination
          page={page}
          count={history.data?.count || 0}
          onChange={setPage}
        />
      </details>
    </div>
  );
}

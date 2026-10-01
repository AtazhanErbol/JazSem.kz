import { RemoteSelect } from "../../components/RemoteSelect";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { DraftEditor, type DraftData } from "./DraftEditor";
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { Upload, Sparkles, Eye, Trash2 } from "lucide-react";
import { SourcePreview } from "./SourcePreview";
import { api } from "../../services/api";
import type { Page, Row } from "../../entities/types";
import type { SourceDocument, AIJob, AIDraft } from "../../entities/ai";
import {
  Badge,
  ErrorState,
  Modal,
  ProgressBar,
  Loading,
} from "../../components/UI";
import { useAction } from "../../hooks/useAction";

export function AIWizard() {
  const [params] = useSearchParams();
  const course = params.get("course") || "";
  return <AIWorkspace key={course} course={course} />;
}
function AIWorkspace({ course }: { course: string }) {
  const { t, i18n } = useTranslation();
  const action = useAction();
  const [params, setParams] = useSearchParams();
  const updateParam = (key: string, value: string) =>
    setParams((p) => {
      if (value) p.set(key, value);
      else p.delete(key);
      return p;
    });
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const sourcePage = Math.max(1, Number(params.get("sourcePage")) || 1);
  const jobPage = Math.max(1, Number(params.get("jobPage")) || 1);
  const setSourcePage = (change: (page: number) => number) =>
    updateParam("sourcePage", String(change(sourcePage)));
  const setJobPage = (change: (page: number) => number) =>
    updateParam("jobPage", String(change(jobPage)));
  const [file, setFile] = useState<File>();
  const [previewSource, setPreviewSource] = useState<SourceDocument>();
  const [deleteSource, setDeleteSource] = useState<SourceDocument>();
  const [deleteFilename, setDeleteFilename] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const [weeks, setWeeks] = useState(1);
  const [mode, setMode] = useState("APPEND");
  const [baseVersion, setBaseVersion] = useState("");
  const [instruction, setInstruction] = useState("");
  const [pageFrom, setPageFrom] = useState("");
  const [pageTo, setPageTo] = useState("");
  const versions = useQuery({
    queryKey: ["versions", course],
    queryFn: () =>
      api<{ id: string; version_number: number; status: string }[]>(
        `courses/${course}/versions/`,
      ),
    enabled: !!course,
  });
  const appendInfo = useQuery({
    queryKey: ["ai-append-context", course, baseVersion],
    queryFn: () =>
      api<{ version_number: number; start_week: number; base_status: string }>(
        `ai-jobs/append-context/?course=${course}&version=${baseVersion}`,
      ),
    enabled: !!course && mode === "APPEND" && !!baseVersion,
  });
  const [language, setLanguage] = useState(i18n.language);
  const [complexity, setComplexity] = useState("intermediate");
  const [assignments, setAssignments] = useState(true);
  const [tests, setTests] = useState(true);
  const job = params.get("job") || "";
  const setJob = (value: string) => updateParam("job", value);
  const [draftText, setDraftText] = useState("");
  const allowNavigation = useUnsavedChanges(
    !!draftText || !!file || !!instruction,
  );
  const [confirm, setConfirm] = useState(false);
  const [imported, setImported] = useState("");
  const availability = useQuery({
    queryKey: ["ai-status"],
    queryFn: () =>
      api<{
        enabled: boolean;
        configured: boolean;
        worker_available: boolean;
        daily_budget: string;
        model: string;
      }>("ai-status/"),
    refetchInterval: 30000,
    retry: false,
  });
  const canGenerate =
    availability.data?.enabled &&
    availability.data.configured &&
    availability.data.worker_available;
  const sources = useQuery({
    queryKey: ["sources", course, sourcePage],
    queryFn: () =>
      api<Page<SourceDocument>>(`sources/?course=${course}&page=${sourcePage}`),
    enabled: !!course,
    refetchInterval: (q) =>
      !q.state.error &&
      q.state.data?.results.some((s) =>
        ["QUEUED", "PROCESSING"].includes(String(s.processing_status)),
      )
        ? 4000
        : false,
  });
  const jobs = useQuery({
    queryKey: ["jobs", course, jobPage],
    queryFn: () =>
      api<Page<AIJob>>(`ai-jobs/?course=${course}&page=${jobPage}`),
    enabled: !!course,
    refetchInterval: (q) =>
      !q.state.error &&
      q.state.data?.results.some((j) =>
        ["QUEUED", "PROCESSING"].includes(String(j.status)),
      )
        ? 4000
        : false,
  });
  const activeId = job || jobs.data?.results[0]?.id || "";
  const active = useQuery({
    queryKey: ["job", activeId],
    queryFn: async ({ signal }) => {
      const result = await api<AIJob>(
        `ai-jobs/${activeId}/`,
        "GET",
        undefined,
        signal,
      );
      if (result.course !== course)
        throw new Error(t("ux.selectedUnavailable"));
      return result;
    },
    enabled: !!activeId && !!course,
    refetchInterval: (q) =>
      !q.state.error &&
      q.state.data &&
      ["QUEUED", "PROCESSING"].includes(String(q.state.data.status))
        ? 3000
        : false,
  });
  const draft = useQuery({
    queryKey: ["draft", activeId],
    queryFn: () => api<AIDraft<DraftData>>(`ai-jobs/${activeId}/draft/`),
    enabled: active.data?.status === "COMPLETED",
  });
  const step = draft.data
    ? 4
    : active.data &&
        ["QUEUED", "PROCESSING"].includes(String(active.data.status))
      ? 3
      : sources.data?.results.length
        ? 2
        : course
          ? 1
          : 0;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">JAZSEM AI</span>
          <h1>{t("ai")}</h1>
          <p className="muted">{t("aiHint")}</p>
        </div>
        <Sparkles size={32} />
      </div>
      <section className="help-card" aria-live="polite">
        <div>
          <strong>{t("aiStatusTitle")}</strong>
          {availability.isPending && <Loading />}
          {availability.error && (
            <ErrorState
              error={availability.error}
              retry={() => void availability.refetch()}
            />
          )}
          {availability.data && (
            <>
              {!availability.data.enabled && <p>{t("aiDisabled")}</p>}
              {availability.data.enabled && !availability.data.configured && (
                <p>{t("aiUnconfigured")}</p>
              )}
              {availability.data.enabled &&
                !availability.data.worker_available && (
                  <p>{t("aiWorkerUnavailable")}</p>
                )}
              {canGenerate && (
                <p>
                  {t("aiReady")} · {availability.data.model}
                </p>
              )}
              <small>
                {t("aiBudget")}: ${availability.data.daily_budget}
              </small>
            </>
          )}
        </div>
        <Link className="button" to="/app/courses">
          {t("openCourseBuilder")}
        </Link>
      </section>
      <ol className="wizard-steps">
        {[
          "course",
          "sources",
          "generationSettings",
          "progress",
          "draft",
          "publish",
        ].map((label, i) => (
          <li className={i <= step ? "active" : ""} key={label}>
            <span>{i + 1}</span>
            {t(label)}
          </li>
        ))}
      </ol>
      {action.feedback}
      <div className="wizard-grid ai-workspace-grid">
        <div className="ai-source-column">
          <section className="panel">
            <h2>01 / {t("course")}</h2>
            <RemoteSelect
              source="courses/?active=true"
              label={t("course")}
              value={course}
              onChange={(value) => {
                setParams(value ? { course: String(value) } : {});
              }}
            />
            <Link
              className="button contextual-action"
              to="/app/courses?create=1"
            >
              + {t("createCourse")}
            </Link>
          </section>
          <section className="panel ai-sources-panel">
            <h2>02 / {t("sources")}</h2>
            <p className="muted">{t("aiLayout.sourceHint")}</p>
            <label className="upload-area">
              <Upload />
              <strong>{t("upload")}</strong>
              <span>{t("sourceHint")}</span>
              <input
                ref={fileInput}
                type="file"
                accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg"
                onChange={(e) => setFile(e.target.files?.[0])}
              />
            </label>
            <button
              disabled={
                !course ||
                !file ||
                action.pending ||
                !availability.data?.worker_available
              }
              onClick={async () => {
                const body = new FormData();
                body.append("course", course);
                body.append("file", file!);
                const uploaded = await action.run("sources/", body);
                if (uploaded.ok) {
                  setFile(undefined);
                  if (fileInput.current) fileInput.current.value = "";
                }
              }}
            >
              {t("upload")}
            </button>
            {course && sources.isPending && <Loading />}
            {sources.isError && (
              <ErrorState
                error={sources.error}
                retry={() => void sources.refetch()}
              />
            )}
            {sources.data && !sources.data.results.length && (
              <p>{t("aiRecovery.noSources")}</p>
            )}
            {sources.data?.results.map((s) => (
              <div className="source-row" key={s.id}>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={selectedSources.includes(s.id)}
                    disabled={
                      s.processing_status !== "COMPLETED" || Boolean(s.excluded)
                    }
                    onChange={(event) =>
                      setSelectedSources((ids) =>
                        event.target.checked
                          ? [...ids, s.id]
                          : ids.filter((id) => id !== s.id),
                      )
                    }
                  />
                  {String(s.filename)}
                </label>
                <Badge>{String(s.processing_status)}</Badge>
                <button
                  type="button"
                  onClick={() => setPreviewSource(s)}
                  aria-label={`${t("sourcePreview.open")}: ${s.filename}`}
                >
                  <Eye size={16} />
                  {t("sourcePreview.open")}
                </button>
                <button
                  type="button"
                  disabled={
                    action.pending ||
                    ["QUEUED", "PROCESSING"].includes(s.processing_status)
                  }
                  onClick={() => {
                    setDeleteSource(s);
                    setDeleteFilename("");
                  }}
                  aria-label={`${t("delete")}: ${s.filename}`}
                >
                  <Trash2 size={16} />
                  {t("delete")}
                </button>
                {Boolean(s.error) && (
                  <small>
                    {t(`aiRecovery.errors.${s.error}`, {
                      defaultValue: t("aiRecovery.errors.EXTRACTION_FAILED"),
                    })}
                  </small>
                )}
                {s.processing_status === "FAILED" && (
                  <button
                    disabled={action.pending}
                    onClick={() => void action.run(`sources/${s.id}/retry/`)}
                  >
                    {t("retry")}
                  </button>
                )}
                {s.excluded ? (
                  <small>{t("aiRecovery.excluded")}</small>
                ) : (
                  <button
                    disabled={action.pending}
                    onClick={async () => {
                      const result = await action.run(
                        `sources/${s.id}/exclude/`,
                      );
                      if (result.ok)
                        setSelectedSources((ids) =>
                          ids.filter((id) => id !== s.id),
                        );
                    }}
                  >
                    {t("aiRecovery.exclude")}
                  </button>
                )}
              </div>
            ))}
            {sources.data && (
              <nav className="pagination" aria-label={t("sources")}>
                <button
                  disabled={!sources.data.previous}
                  onClick={() => setSourcePage((p) => p - 1)}
                >
                  {t("previous")}
                </button>
                <span>{sourcePage}</span>
                <button
                  disabled={!sources.data.next}
                  onClick={() => setSourcePage((p) => p + 1)}
                >
                  {t("next")}
                </button>
              </nav>
            )}
          </section>
        </div>
        <section className="panel ai-settings-panel">
          <h2>03 / {t("generationSettings")}</h2>
          <div className="ai-settings-group">
            <label>
              {t("aiAppend.mode")}
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="APPEND">{t("aiAppend.append")}</option>
                <option value="NEW">{t("aiAppend.new")}</option>
              </select>
            </label>
            {mode === "APPEND" && (
              <>
                <label>
                  {t("aiAppend.version")}
                  <select
                    value={baseVersion}
                    onChange={(e) => setBaseVersion(e.target.value)}
                  >
                    <option value="">{t("aiAppend.choose")}</option>
                    {versions.data
                      ?.filter((v) =>
                        ["DRAFT", "REVIEW", "PUBLISHED"].includes(v.status),
                      )
                      .map((v) => (
                        <option key={v.id} value={v.id}>
                          v{v.version_number} · {t(v.status)}
                        </option>
                      ))}
                  </select>
                </label>
                {versions.isError && <ErrorState error={versions.error} />}
                {appendInfo.isError && <ErrorState error={appendInfo.error} />}
                {appendInfo.data && (
                  <p className="muted">
                    {t("aiAppend.target", {
                      version: appendInfo.data.version_number,
                      start: appendInfo.data.start_week,
                      end: appendInfo.data.start_week + weeks - 1,
                    })}{" "}
                    {t(
                      appendInfo.data.base_status === "PUBLISHED"
                        ? "aiAppend.copy"
                        : "aiAppend.draft",
                    )}
                  </p>
                )}
              </>
            )}
            {mode === "NEW" && <p className="muted">{t("aiAppend.newHint")}</p>}
            <label>
              {t(mode === "APPEND" ? "aiAppend.count" : "weeks")}
              <input
                type="number"
                min="1"
                max="16"
                value={weeks}
                onChange={(e) => setWeeks(Number(e.target.value))}
              />
            </label>
          </div>
          <div className="ai-settings-group">
            <label>
              {t("aiAppend.instruction")}
              <textarea
                rows={4}
                maxLength={2000}
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder={t("aiAppend.example")}
              />
            </label>
            <details className="ai-help">
              <summary>{t("aiLayout.instructionHelp")}</summary>
              <p className="muted">{t("aiAppend.instructionHint")}</p>
            </details>
            <details className="ai-help">
              <summary>{t("aiLayout.pageHelp")}</summary>
              <p className="muted">{t("aiAppend.pagesHint")}</p>
            </details>
            <div className="ai-page-range">
              <label>
                {t("aiAppend.from")}
                <input
                  type="number"
                  min="1"
                  value={pageFrom}
                  onChange={(e) => setPageFrom(e.target.value)}
                />
              </label>
              <label>
                {t("aiAppend.to")}
                <input
                  type="number"
                  min="1"
                  value={pageTo}
                  onChange={(e) => setPageTo(e.target.value)}
                />
              </label>
            </div>
          </div>
          <div className="ai-settings-group">
            <div className="ai-options-grid">
              <label>
                {t("language")}
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <option value="ru">RU</option>
                  <option value="kk">KZ</option>
                </select>
              </label>
              <label>
                {t("complexity")}
                <select
                  value={complexity}
                  onChange={(e) => setComplexity(e.target.value)}
                >
                  {["basic", "intermediate", "advanced"].map((v) => (
                    <option key={v} value={v}>
                      {t(v)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="ai-output-options">
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={assignments}
                  onChange={(e) => setAssignments(e.target.checked)}
                />
                {t("assignments")}
              </label>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={tests}
                  onChange={(e) => setTests(e.target.checked)}
                />
                {t("tests")}
              </label>
            </div>
          </div>
          <p className="muted ai-selection-count">
            {t("aiLayout.selected", { count: selectedSources.length })}
          </p>
          <button
            className="primary ai-generate-button"
            disabled={
              !canGenerate ||
              !course ||
              (mode === "APPEND" &&
                (!baseVersion ||
                  !appendInfo.data ||
                  appendInfo.isError ||
                  appendInfo.isFetching)) ||
              !Number.isInteger(weeks) ||
              weeks < 1 ||
              weeks > 16 ||
              ((!!pageFrom || !!pageTo) &&
                (!pageFrom ||
                  !pageTo ||
                  !Number.isInteger(Number(pageFrom)) ||
                  !Number.isInteger(Number(pageTo)) ||
                  Number(pageFrom) < 1 ||
                  Number(pageTo) < Number(pageFrom) ||
                  selectedSources.length !== 1)) ||
              action.pending ||
              !selectedSources.length ||
              (!assignments && !tests) ||
              jobs.data?.results.some((j) =>
                ["QUEUED", "PROCESSING"].includes(String(j.status)),
              )
            }
            onClick={async () => {
              const result = await action.run<Row>("ai-jobs/", {
                course,
                mode,
                ...(mode === "APPEND" ? { base_version: baseVersion } : {}),
                instruction,
                ...(pageFrom && pageTo
                  ? { page_from: Number(pageFrom), page_to: Number(pageTo) }
                  : {}),
                sources: selectedSources,
                weeks,
                language,
                complexity,
                assignments,
                tests,
              });
              if (result.ok) {
                allowNavigation();
                setJob(result.data.id);
                setDraftText("");
              }
            }}
          >
            <Sparkles size={18} />
            {t("generate")}
          </button>
          {!assignments && !tests && (
            <p role="alert">{t("aiRecovery.gradingRequired")}</p>
          )}
          {jobs.isError && (
            <ErrorState error={jobs.error} retry={() => void jobs.refetch()} />
          )}
          {active.isError && (
            <ErrorState
              error={active.error}
              retry={() => void active.refetch()}
            />
          )}
          {draft.isError && (
            <ErrorState
              error={draft.error}
              retry={() => void draft.refetch()}
            />
          )}
          {active.data && (
            <div className="job-progress">
              <Badge>{String(active.data.status)}</Badge>
              <p>
                {t(String(active.data.current_step), {
                  defaultValue: t(String(active.data.status)),
                })}
              </p>
              <ProgressBar value={Number(active.data.progress)} />
              {Boolean(active.data.error) && (
                <ErrorState
                  error={t(`aiRecovery.errors.${active.data.error}`, {
                    defaultValue: t(
                      "aiRecovery.errors.GENERATION_VALIDATION_FAILED",
                    ),
                  })}
                />
              )}{" "}
              {["QUEUED", "PROCESSING"].includes(
                String(active.data.status),
              ) && (
                <button
                  onClick={() => void action.run(`ai-jobs/${activeId}/cancel/`)}
                >
                  {t("cancel")}
                </button>
              )}
            </div>
          )}
        </section>
      </div>
      {!!course && (
        <section className="panel">
          <h2>{t("aiRecovery.history")}</h2>
          {jobs.isPending && <Loading />}
          {jobs.data?.results.map((j) => (
            <div className="source-row" key={j.id}>
              <button
                disabled={Boolean(draftText)}
                onClick={() => {
                  setJob(j.id);
                  setDraftText("");
                }}
              >
                {new Date(String(j.created_at)).toLocaleString(
                  i18n.language === "kk" ? "kk-KZ" : "ru-RU",
                )}
              </button>
              <Badge>{String(j.status)}</Badge>
              <span>
                {j.estimated_cost != null
                  ? `$${j.estimated_cost}`
                  : t("aiRecovery.costUnknown")}
              </span>
            </div>
          ))}
          {jobs.data && !jobs.data.results.length && (
            <p>{t("aiRecovery.noJobs")}</p>
          )}
          {jobs.data && (
            <nav className="pagination" aria-label={t("aiRecovery.history")}>
              <button
                disabled={!jobs.data.previous}
                onClick={() => setJobPage((p) => p - 1)}
              >
                {t("previous")}
              </button>
              <span>{jobPage}</span>
              <button
                disabled={!jobs.data.next}
                onClick={() => setJobPage((p) => p + 1)}
              >
                {t("next")}
              </button>
            </nav>
          )}
        </section>
      )}
      {draft.data && (
        <section className="panel">
          <h2>05 / {t("draft")}</h2>
          <DraftEditor
            preserveCourse={active.data?.parameters?.mode === "APPEND"}
            startWeek={active.data?.parameters?.append_context?.start_week || 1}
            disabled={action.pending || Boolean(draft.data.imported_version)}
            data={
              (draftText ? JSON.parse(draftText) : draft.data.data) as DraftData
            }
            onChange={(value) => setDraftText(JSON.stringify(value))}
            onRegenerate={async (week, topic, instruction) => {
              if (draftText) {
                const saved = await action.run<Row>(
                  `ai-drafts/${draft.data!.id}/`,
                  { data: JSON.parse(draftText) },
                  "PATCH",
                );
                if (!saved.ok) return;
              }
              const result = await action.run<Row>(
                `ai-drafts/${draft.data!.id}/regenerate/`,
                { week_index: week, topic_index: topic, instruction },
              );
              if (result.ok) {
                allowNavigation();
                setJob(result.data.id);
                setDraftText("");
              }
            }}
          />
          <div className="form-actions">
            <button
              disabled={
                action.pending ||
                !draftText ||
                Boolean(draft.data.imported_version)
              }
              onClick={async () => {
                const saved = await action.run<Row>(
                  `ai-drafts/${draft.data!.id}/`,
                  { data: JSON.parse(draftText) },
                  "PATCH",
                );
                if (saved.ok) setDraftText("");
              }}
            >
              {t("save")}
            </button>
            <button
              className="primary"
              disabled={
                action.pending ||
                !!draftText ||
                Boolean(draft.data.imported_version)
              }
              onClick={() => setConfirm(true)}
            >
              {t("importDraft")}
            </button>
            {Boolean(imported || draft.data.imported_version) && (
              <Link
                className="button"
                to={`/app/courses/${course}?version=${imported || draft.data.imported_version}`}
              >
                {t("builder")} → {t("publish")}
              </Link>
            )}
          </div>
        </section>
      )}
      {previewSource && (
        <SourcePreview
          key={previewSource.id}
          source={previewSource}
          onClose={() => setPreviewSource(undefined)}
        />
      )}
      {deleteSource && (
        <Modal
          title={t("sourcePreview.deleteTitle")}
          onClose={() => {
            if (!action.pending) setDeleteSource(undefined);
          }}
        >
          <p>{t("sourcePreview.deleteHint")}</p>
          <p>
            <strong>{deleteSource.filename}</strong>
          </p>
          <label>
            {t("sourcePreview.confirmName")}
            <input
              value={deleteFilename}
              disabled={action.pending}
              onChange={(e) => setDeleteFilename(e.target.value)}
            />
          </label>
          {action.error != null && (
            <ErrorState title={t("actionFailed")} error={action.error} />
          )}
          <div className="form-actions">
            <button
              disabled={action.pending}
              onClick={() => setDeleteSource(undefined)}
            >
              {t("cancel")}
            </button>
            <button
              className="danger"
              disabled={
                action.pending || deleteFilename !== deleteSource.filename
              }
              onClick={async () => {
                const result = await action.run(
                  `sources/${deleteSource.id}/delete-file/`,
                  { filename: deleteFilename },
                );
                if (result.ok) {
                  setSelectedSources((ids) =>
                    ids.filter((id) => id !== deleteSource.id),
                  );
                  setDeleteSource(undefined);
                  setSourcePage(() => 1);
                }
              }}
            >
              {t("delete")}
            </button>
          </div>
        </Modal>
      )}
      {confirm && draft.data && (
        <Modal title={t("confirm")} onClose={() => setConfirm(false)}>
          <p>
            {active.data?.parameters?.mode === "APPEND"
              ? t("aiAppend.confirm", {
                  version:
                    active.data.parameters.append_context?.version_number,
                  start: active.data.parameters.append_context?.start_week,
                  count: draft.data.data.weeks.length,
                })
              : t("confirmImport")}
          </p>
          {active.data?.parameters?.mode === "APPEND" && (
            <p className="muted">{t("aiAppend.after")}</p>
          )}
          {action.error != null && (
            <ErrorState error={action.error} title={t("actionFailed")} />
          )}
          <button
            className="primary"
            disabled={action.pending}
            onClick={async () => {
              const result = await action.run<Row>(
                `ai-drafts/${draft.data!.id}/confirm/`,
              );
              if (result.ok) {
                setImported(result.data.id);
                setConfirm(false);
              }
            }}
          >
            {t("confirm")}
          </button>
        </Modal>
      )}
    </>
  );
}

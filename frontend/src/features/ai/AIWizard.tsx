import { DraftEditor, type DraftData } from "./DraftEditor";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Upload, Sparkles } from "lucide-react";
import { api, allRows } from "../../services/api";
import type { Page, Row } from "../../entities/types";
import { Badge, ErrorState, Modal, ProgressBar } from "../../components/UI";
import { useAction } from "../../hooks/useAction";

export function AIWizard() {
  const { t, i18n } = useTranslation();
  const action = useAction();
  const [course, setCourse] = useState("");
  const [file, setFile] = useState<File>();
  const [weeks, setWeeks] = useState(4);
  const [language, setLanguage] = useState(i18n.language);
  const [complexity, setComplexity] = useState("intermediate");
  const [assignments, setAssignments] = useState(true);
  const [tests, setTests] = useState(true);
  const [job, setJob] = useState("");
  const [draftText, setDraftText] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [imported, setImported] = useState("");
  const courses = useQuery({
    queryKey: ["options", "courses"],
    queryFn: () => allRows("courses/"),
  });
  const sources = useQuery({
    queryKey: ["sources", course],
    queryFn: () => api<Page<Row>>(`sources/?course=${course}`),
    enabled: !!course,
    refetchInterval: 4000,
  });
  const jobs = useQuery({
    queryKey: ["jobs", course],
    queryFn: () => api<Page<Row>>(`ai-jobs/?course=${course}`),
    enabled: !!course,
    refetchInterval: 4000,
  });
  const activeId = job || jobs.data?.results[0]?.id || "";
  const active = useQuery({
    queryKey: ["job", activeId],
    queryFn: () => api<Row>(`ai-jobs/${activeId}/`),
    enabled: !!activeId,
    refetchInterval: 3000,
  });
  const draft = useQuery({
    queryKey: ["draft", activeId],
    queryFn: () => api<Row>(`ai-jobs/${activeId}/draft/`),
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
      <div className="wizard-grid">
        <section className="panel">
          <h2>01 / {t("course")}</h2>
          <label>
            {t("course")}
            <select
              value={course}
              onChange={(e) => {
                setCourse(e.target.value);
                setJob("");
                setDraftText("");
                setImported("");
              }}
            >
              <option value="">{t("noSelection")}</option>
              {courses.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {String(c.title)}
                </option>
              ))}
            </select>
          </label>
          <Link to="/app/courses">+ {t("createCourse")}</Link>
          <h2>02 / {t("sources")}</h2>
          <label className="upload-area">
            <Upload />
            <strong>{t("upload")}</strong>
            <span>{t("sourceHint")}</span>
            <input
              type="file"
              accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files?.[0])}
            />
          </label>
          <button
            disabled={!course || !file || action.pending}
            onClick={async () => {
              const body = new FormData();
              body.append("course", course);
              body.append("file", file!);
              await action.run("sources/", body);
              setFile(undefined);
            }}
          >
            {t("upload")}
          </button>
          {sources.data?.results.map((s) => (
            <div className="source-row" key={s.id}>
              <span>{String(s.filename)}</span>
              <Badge>{String(s.processing_status)}</Badge>
              {s.error != null && <small>{String(s.error)}</small>}
            </div>
          ))}
        </section>
        <section className="panel">
          <h2>03 / {t("generationSettings")}</h2>
          <label>
            {t("weeks")}
            <input
              type="number"
              min="1"
              max="16"
              value={weeks}
              onChange={(e) => setWeeks(Number(e.target.value))}
            />
          </label>
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
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
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
          <button
            className="primary"
            disabled={
              !course ||
              action.pending ||
              !sources.data?.results.length ||
              sources.data.results.some(
                (s) => s.processing_status !== "COMPLETED",
              )
            }
            onClick={async () => {
              const result = await action.run<Row>("ai-jobs/", {
                course,
                weeks,
                language,
                complexity,
                assignments,
                tests,
              });
              if (result) {
                setJob(result.id);
                setDraftText("");
              }
            }}
          >
            <Sparkles size={18} />
            {t("generate")}
          </button>
          {active.data && (
            <div className="job-progress">
              <Badge>{String(active.data.status)}</Badge>
              <p>{t(String(active.data.current_step))}</p>
              <ProgressBar value={Number(active.data.progress)} />
              {Boolean(active.data.error) && (
                <ErrorState error={String(active.data.error)} />
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
      {draft.data && (
        <section className="panel">
          <h2>05 / {t("draft")}</h2>
          <DraftEditor
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
                if (!saved) return;
              }
              const result = await action.run<Row>(
                `ai-drafts/${draft.data!.id}/regenerate/`,
                { week_index: week, topic_index: topic, instruction },
              );
              if (result) {
                setJob(result.id);
                setDraftText("");
              }
            }}
          />
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
              if (saved) setDraftText("");
            }}
          >
            {t("save")}
          </button>
          <button
            className="primary"
            disabled={!!draftText || Boolean(draft.data.imported_version)}
            onClick={() => setConfirm(true)}
          >
            {t("importDraft")}
          </button>
          {Boolean(imported || draft.data.imported_version) && (
            <Link className="button" to={"/app/courses/" + course}>
              {t("builder")} → {t("publish")}
            </Link>
          )}
        </section>
      )}
      {confirm && draft.data && (
        <Modal title={t("confirm")} onClose={() => setConfirm(false)}>
          <p>{t("confirmImport")}</p>
          <button
            className="primary"
            disabled={action.pending}
            onClick={async () => {
              const result = await action.run<Row>(
                `ai-drafts/${draft.data!.id}/confirm/`,
              );
              if (result) setImported(result.id);
              setConfirm(false);
            }}
          >
            {t("confirm")}
          </button>
        </Modal>
      )}
    </>
  );
}

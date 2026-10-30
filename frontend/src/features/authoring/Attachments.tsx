import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ArrowDown,
  ArrowUp,
  Download,
  FileText,
  Pencil,
  Play,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api, ApiError } from "../../services/api";
import { directUpload } from "../../services/directUpload";
import { ErrorState, Loading, ProgressBar } from "../../components/UI";
import { Pagination } from "../../components/Pagination";
import type { Page } from "../../entities/types";

export type AttachmentOwner = "topic" | "assignment" | "test" | "question";
export function ActivityAttachments({
  type,
  id,
}: {
  type: string;
  id: string;
}) {
  const owner = (
    { topic: "topic", assignments: "assignment", tests: "test" } as Record<
      string,
      AttachmentOwner
    >
  )[type];
  return owner ? (
    <>
      {owner === "assignment" && (
        <Attachments owner={owner} ownerId={id} mode="videos" />
      )}
      <Attachments owner={owner} ownerId={id} />
    </>
  ) : null;
}
export interface Attachment {
  id: string;
  title: string;
  description: string;
  kind: "FILE" | "VIDEO" | "YOUTUBE";
  file: boolean;
  external_url: string;
  embed_url: string;
  original_filename: string;
  mime_type: string;
  size: number | null;
  order: number;
  created_at: string;
  uploaded_at?: string;
}
interface UploadConfig {
  max_document_bytes: number;
  max_video_bytes: number;
  document_types: Record<string, string>;
  video_types: Record<string, string>;
  direct_uploads: boolean;
}
function fileSize(size: number | null) {
  return size === null
    ? ""
    : size < 1024 * 1024
      ? `${Math.ceil(size / 1024)} KB`
      : `${(size / 1024 / 1024).toFixed(1)} MB`;
}
function safeEmbed(value: string) {
  return /^https:\/\/www\.youtube-nocookie\.com\/embed\/[A-Za-z0-9_-]{11}$/.test(
    value,
  )
    ? value
    : undefined;
}

function AttachmentPreview({ item }: { item: Attachment }) {
  const source = `/api/v1/attachments/${item.id}/preview/`;
  if (item.kind === "YOUTUBE") {
    const url = safeEmbed(item.embed_url);
    return url ? (
      <iframe
        className="attachment-video"
        src={url}
        title={item.title}
        loading="lazy"
        sandbox="allow-scripts allow-same-origin allow-presentation"
        allow="encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
        referrerPolicy="strict-origin-when-cross-origin"
      />
    ) : null;
  }
  if (item.kind === "VIDEO") return <VideoPlayer item={item} />;
  if (item.mime_type.startsWith("image/"))
    return (
      <img
        className="attachment-image"
        src={source}
        alt={item.title}
        loading="lazy"
      />
    );
  if (item.mime_type === "application/pdf")
    return (
      <iframe
        className="attachment-pdf"
        src={source}
        title={item.title}
        sandbox="allow-same-origin"
      />
    );
  return null;
}

function VideoPlayer({ item }: { item: Attachment }) {
  const { t } = useTranslation();
  const [revision, setRevision] = useState(0),
    [failed, setFailed] = useState(false);
  const video = useRef<HTMLVideoElement>(null),
    position = useRef(0);
  return (
    <div>
      <video
        key={revision}
        ref={video}
        className="attachment-video"
        controls
        preload="metadata"
        playsInline
        onError={() => setFailed(true)}
        onLoadedMetadata={(event) => {
          const player = event.currentTarget;
          if (position.current > 0 && Number.isFinite(player.duration))
            player.currentTime = Math.min(
              position.current,
              Math.max(0, player.duration - 0.05),
            );
        }}
      >
        <source
          src={`/api/v1/attachments/${item.id}/preview/?refresh=${revision}`}
          type={item.mime_type}
        />
      </video>
      <small className="muted">{t("authoring.playFallback")}</small>
      {failed && (
        <button
          type="button"
          onClick={() => {
            position.current = video.current?.currentTime || 0;
            setFailed(false);
            setRevision((old) => old + 1);
          }}
        >
          {t("authoring.refreshVideo")}
        </button>
      )}
    </div>
  );
}

function AttachmentItem({
  item,
  editable,
  disabled,
  first,
  last,
  mutate,
  replace,
  dirty,
}: {
  item: Attachment;
  editable: boolean;
  disabled: boolean;
  first: boolean;
  last: boolean;
  mutate: (path: string, method: string, body?: unknown) => Promise<boolean>;
  replace: (item: Attachment, file: File) => void;
  dirty: (id: string, value: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const [editing, setEditing] = useState(false),
    [preview, setPreview] = useState(false);
  const [title, setTitle] = useState(item.title),
    [description, setDescription] = useState(item.description);
  const [url, setUrl] = useState(item.external_url);
  const changed =
    editing &&
    (title !== item.title ||
      description !== item.description ||
      url !== item.external_url);
  useEffect(() => {
    dirty(item.id, changed);
    return () => dirty(item.id, false);
  }, [item.id, changed, dirty]);
  const canPreview =
    item.kind !== "FILE" ||
    item.mime_type.startsWith("image/") ||
    item.mime_type === "application/pdf";
  return (
    <article className="attachment-row" data-dirty={changed}>
      <div className="attachment-summary">
        {item.kind === "FILE" ? (
          <FileText aria-hidden size={21} />
        ) : (
          <Play aria-hidden size={21} />
        )}
        <div className="attachment-copy">
          <strong>{item.title}</strong>
          <small>
            {item.kind === "YOUTUBE"
              ? t("authoring.youtubeSource")
              : `${item.original_filename} · ${fileSize(item.size)} · ${item.mime_type}`}
          </small>
          <small>
            {new Date(item.uploaded_at || item.created_at).toLocaleDateString(
              i18n.language === "kk" ? "kk-KZ" : "ru-RU",
            )}
          </small>
          {item.description && <p>{item.description}</p>}
        </div>
        <div className="attachment-actions">
          {canPreview && (
            <button
              type="button"
              className="icon-button"
              aria-expanded={preview}
              aria-label={t(
                preview ? "authoring.closePreview" : "authoring.openPreview",
              )}
              onClick={() => setPreview(!preview)}
            >
              <Play size={17} />
            </button>
          )}
          {item.file && (
            <a
              className="icon-button"
              href={`/api/v1/attachments/${item.id}/download/`}
              aria-label={`${t("download")}: ${item.title}`}
            >
              <Download size={17} />
            </a>
          )}
          {editable && (
            <>
              <button
                type="button"
                className="icon-button"
                disabled={disabled || first}
                aria-label={`${t("authoring.up")}: ${item.title}`}
                onClick={() => void mutate("move:up", "POST", item.id)}
              >
                <ArrowUp size={17} />
              </button>
              <button
                type="button"
                className="icon-button"
                disabled={disabled || last}
                aria-label={`${t("authoring.down")}: ${item.title}`}
                onClick={() => void mutate("move:down", "POST", item.id)}
              >
                <ArrowDown size={17} />
              </button>
              <button
                type="button"
                className="icon-button"
                disabled={disabled}
                aria-label={`${t("edit")}: ${item.title}`}
                onClick={() => {
                  if (changed && !window.confirm(t("ux.unsavedConfirm")))
                    return;
                  setTitle(item.title);
                  setDescription(item.description);
                  setUrl(item.external_url);
                  setEditing(!editing);
                }}
              >
                <Pencil size={17} />
              </button>
              <button
                type="button"
                className="icon-button danger"
                disabled={disabled}
                aria-label={`${t("delete")}: ${item.title}`}
                onClick={() => {
                  if (window.confirm(t("authoring.removeConfirm")))
                    void mutate(`attachments/${item.id}/`, "DELETE");
                }}
              >
                <Trash2 size={17} />
              </button>
            </>
          )}
        </div>
      </div>
      {editing && (
        <div className="attachment-edit">
          <label>
            {t("authoring.title")}
            <input
              value={title}
              maxLength={240}
              disabled={disabled}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label>
            {t("authoring.description")}
            <textarea
              value={description}
              maxLength={4000}
              rows={2}
              disabled={disabled}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          {item.kind === "YOUTUBE" && (
            <label>
              {t("authoring.youtubeUrl")}
              <input
                type="url"
                value={url}
                disabled={disabled}
                onChange={(event) => setUrl(event.target.value)}
              />
            </label>
          )}
          <div className="row-actions">
            <button
              type="button"
              disabled={disabled || !title.trim()}
              onClick={async () => {
                if (
                  await mutate(`attachments/${item.id}/`, "PATCH", {
                    title,
                    description,
                    ...(item.kind === "YOUTUBE" ? { external_url: url } : {}),
                  })
                )
                  setEditing(false);
              }}
            >
              {t("save")}
            </button>
            {item.file && (
              <label className="button attachment-file-input">
                {t("authoring.replace")}
                <input
                  type="file"
                  disabled={disabled}
                  accept={
                    item.kind === "VIDEO"
                      ? ".mp4,.webm"
                      : ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.csv,.png,.jpg,.jpeg,.webp,.gif,.odt,.odp,.ods"
                  }
                  onChange={(event) => {
                    const selected = event.target.files?.[0];
                    event.target.value = "";
                    if (
                      selected &&
                      window.confirm(t("authoring.replaceConfirm"))
                    )
                      replace(item, selected);
                  }}
                />
              </label>
            )}
          </div>
        </div>
      )}
      {preview && <AttachmentPreview item={item} />}
    </article>
  );
}

export function Attachments({
  owner,
  ownerId,
  mode = "files",
  editable = false,
  onBusyChange,
  onDirtyChange,
  heading = true,
}: {
  owner: AttachmentOwner;
  ownerId: string;
  mode?: "files" | "videos";
  editable?: boolean;
  heading?: boolean;
  onBusyChange?: (busy: boolean) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const { t } = useTranslation(),
    cache = useQueryClient();
  const [page, setPage] = useState(1),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const [progress, setProgress] = useState(0),
    [uploadName, setUploadName] = useState(""),
    [status, setStatus] = useState("");
  const [youtube, setYoutube] = useState(false),
    [title, setTitle] = useState(""),
    [url, setUrl] = useState("");
  const [dirtyRows, setDirtyRows] = useState(new Set<string>());
  const controller = useRef<AbortController | null>(null),
    mounted = useRef(true);
  const dirty = useCallback(
    (id: string, changed: boolean) =>
      setDirtyRows((old) => {
        if (old.has(id) === changed) return old;
        const next = new Set(old);
        if (changed) next.add(id);
        else next.delete(id);
        return next;
      }),
    [],
  );
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      controller.current?.abort();
    };
  }, []);
  useEffect(() => {
    onBusyChange?.(busy);
    return () => onBusyChange?.(false);
  }, [busy, onBusyChange]);
  const isDirty = dirtyRows.size > 0 || (youtube && (!!title || !!url));
  useEffect(() => {
    onDirtyChange?.(isDirty);
    return () => onDirtyChange?.(false);
  }, [isDirty, onDirtyChange]);
  const key = ["attachments", owner, ownerId];
  const query = useQuery({
    queryKey: [...key, mode, page],
    queryFn: ({ signal }) =>
      api<Page<Attachment>>(
        `attachments/?${owner}=${ownerId}&kind__in=${mode === "videos" ? "VIDEO,YOUTUBE" : "FILE"}&ordering=order,created_at&page=${page}`,
        "GET",
        undefined,
        signal,
      ),
  });
  const config = useQuery({
    queryKey: ["attachment-config"],
    queryFn: () => api<UploadConfig>("attachments/config/"),
    enabled: editable,
    staleTime: 60000,
  });
  async function refresh() {
    // An initial list request may have taken its snapshot before the upload committed.
    // Cancel it explicitly: invalidation alone can reuse a pending initial fetch.
    await cache.cancelQueries({ queryKey: key });
    await cache.invalidateQueries({ queryKey: key });
  }
  async function mutate(path: string, method: string, body?: unknown) {
    if (busy) return false;
    setBusy(true);
    setError(undefined);
    setStatus("");
    try {
      if (path.startsWith("move:")) {
        await api("attachments/reorder/", "POST", {
          first: body,
          direction: path === "move:up" ? "UP" : "DOWN",
        });
      } else await api(path, method, body);
      if (method === "DELETE" && query.data?.results.length === 1 && page > 1)
        setPage(page - 1);
      await refresh();
      setStatus(t("authoring.updated"));
      return true;
    } catch (cause) {
      setError(cause);
      return false;
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  async function uploadFiles(files: File[], replace?: Attachment) {
    if (busy || !config.data) return;
    const limits = config.data;
    setBusy(true);
    setError(undefined);
    setStatus("");
    const abort = new AbortController();
    controller.current = abort;
    try {
      for (const [index, selected] of files.entries()) {
        const ext = "." + (selected.name.split(".").pop()?.toLowerCase() || "");
        const allowed =
          mode === "videos" ? limits.video_types : limits.document_types;
        if (!allowed[ext])
          throw new Error(
            ext === ".mov"
              ? t("authoring.fileHint", {
                  documents: limits.max_document_bytes / 1048576,
                  videos: limits.max_video_bytes / 1048576,
                })
              : t("authoring.invalidType"),
          );
        const max =
          mode === "videos"
            ? limits.max_video_bytes
            : limits.max_document_bytes;
        if (!selected.size || selected.size > max)
          throw new Error(t("authoring.tooLarge", { size: max / 1048576 }));
        const form = new FormData();
        if (!replace) form.append(owner, ownerId);
        form.append("kind", mode === "videos" ? "VIDEO" : "FILE");
        form.append(
          "title",
          replace?.title || selected.name.replace(/\.[^.]+$/, "").slice(0, 240),
        );
        if (!replace)
          form.append("order", String((query.data?.count || 0) + index));
        // Browser MIME guesses differ by OS; use the same extension allow-list as the server,
        // which additionally verifies the actual object signature after upload.
        form.append(
          "file",
          new File([selected], selected.name, { type: allowed[ext] }),
        );
        setUploadName(selected.name);
        setProgress(0);
        const target = `attachments/${replace ? replace.id + "/" : ""}`,
          method = replace ? "PATCH" : "POST";
        if (limits.direct_uploads) {
          const prepared = await directUpload(
            target,
            method,
            form,
            (metadata) => api("uploads/", "POST", metadata, abort.signal),
            abort.signal,
            setProgress,
          );
          setProgress(100);
          await api(
            target,
            method,
            { ...prepared.data, upload_ticket: prepared.tickets[0] },
            abort.signal,
          );
        } else {
          // Development storage only. Production configuration mandates signed direct uploads.
          await api(target, method, form, abort.signal);
          setProgress(100);
        }
        await refresh();
      }
      setStatus(t("authoring.updated"));
    } catch (cause) {
      await refresh().catch(() => undefined);
      if (mounted.current)
        setError(
          cause instanceof DOMException && cause.name === "AbortError"
            ? new Error(t("authoring.cancelled"))
            : cause instanceof ApiError || cause instanceof Error
              ? cause
              : new Error(t("authoring.uploadError")),
        );
    } finally {
      if (mounted.current) {
        setBusy(false);
        setUploadName("");
      }
      controller.current = null;
    }
  }
  const files = query.data?.results || [];
  if (!editable && query.isSuccess && !files.length) return null;
  const titleKey =
    mode === "videos"
      ? "videos"
      : {
          topic: "topicFiles",
          assignment: "assignmentFiles",
          test: "testFiles",
          question: "questionFiles",
        }[owner];
  return (
    <section
      className="attachments"
      aria-label={t(`authoring.${titleKey}`)}
      data-pending={busy}
      data-dirty={isDirty}
    >
      {heading && <h3>{t(`authoring.${titleKey}`)}</h3>}
      {editable && (
        <>
          <p className="muted">{t("authoring.immediate")}</p>
          {config.isPending ? (
            <Loading />
          ) : config.error ? (
            <ErrorState error={config.error} />
          ) : (
            <div
              className="attachment-drop"
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = busy ? "none" : "copy";
              }}
              onDrop={(event) => {
                event.preventDefault();
                if (!busy)
                  void uploadFiles(Array.from(event.dataTransfer.files));
              }}
            >
              <Upload aria-hidden size={25} />
              <strong>{t("authoring.drop")}</strong>
              <label className="button attachment-file-input">
                {t("authoring.choose")}
                <input
                  type="file"
                  multiple
                  disabled={busy}
                  accept={Object.keys(
                    mode === "videos"
                      ? config.data!.video_types
                      : config.data!.document_types,
                  ).join(",")}
                  onChange={(event) => {
                    const selected = Array.from(event.target.files || []);
                    event.target.value = "";
                    void uploadFiles(selected);
                  }}
                />
              </label>
              <small>
                {t("authoring.fileHint", {
                  documents: config.data!.max_document_bytes / 1048576,
                  videos: config.data!.max_video_bytes / 1048576,
                })}
              </small>
            </div>
          )}
          {mode === "videos" && (
            <button
              type="button"
              disabled={busy}
              onClick={() => setYoutube(!youtube)}
            >
              {t("authoring.youtube")}
            </button>
          )}
          {youtube && (
            <div className="attachment-edit">
              <label>
                {t("authoring.title")}
                <input
                  value={title}
                  maxLength={240}
                  disabled={busy}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </label>
              <label>
                {t("authoring.youtubeUrl")}
                <input
                  type="url"
                  value={url}
                  disabled={busy}
                  onChange={(event) => setUrl(event.target.value)}
                />
              </label>
              <small className="muted">{t("authoring.youtubeHint")}</small>
              <button
                type="button"
                disabled={busy || !title.trim() || !url.trim()}
                onClick={async () => {
                  if (
                    await mutate("attachments/", "POST", {
                      [owner]: ownerId,
                      kind: "YOUTUBE",
                      title,
                      external_url: url,
                      order: query.data?.count || 0,
                    })
                  ) {
                    setTitle("");
                    setUrl("");
                    setYoutube(false);
                  }
                }}
              >
                {t("authoring.add")}
              </button>
            </div>
          )}
        </>
      )}
      {uploadName && (
        <div className="attachment-upload" role="status">
          <strong>{t("authoring.uploading", { name: uploadName })}</strong>
          <ProgressBar value={progress} />
          <small>
            {progress < 100 ? `${progress}%` : t("authoring.processing")}
          </small>
          <button type="button" onClick={() => controller.current?.abort()}>
            <X size={16} />
            {t("authoring.cancelUpload")}
          </button>
        </div>
      )}
      {error !== undefined && <ErrorState error={error} />}
      <div role="status" className="feedback">
        {status}
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : files.length ? (
        <div className="attachment-list">
          {files.map((item, index) => (
            <AttachmentItem
              key={item.id}
              item={item}
              editable={editable}
              disabled={busy}
              first={page === 1 && index === 0}
              last={!query.data?.next && index === files.length - 1}
              mutate={mutate}
              replace={(old, selected) => void uploadFiles([selected], old)}
              dirty={dirty}
            />
          ))}
        </div>
      ) : (
        <p className="attachment-empty">{t("authoring.empty")}</p>
      )}
      <Pagination
        page={page}
        count={query.data?.count || 0}
        onChange={setPage}
      />
    </section>
  );
}

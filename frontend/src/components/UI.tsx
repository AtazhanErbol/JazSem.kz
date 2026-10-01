import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { BookOpen, LoaderCircle, X } from "lucide-react";
import { Link } from "react-router-dom";

export function Logo() {
  return (
    <Link className="logo" to="/" aria-label="JazSem.kz">
      <img
        className="logo-mark"
        src="/brand/jazsem-mark.png"
        width="40"
        height="40"
        alt=""
      />
      <span className="logo-wordmark">
        JazSem<span className="logo-domain">.kz</span>
      </span>
    </Link>
  );
}
export function Language() {
  const { i18n } = useTranslation();
  const selected = i18n.language === "kk" ? "kk" : "ru";
  function changeLanguage(language: string) {
    void i18n.changeLanguage(language);
    localStorage.setItem("language", language);
  }
  return (
    <div
      className="language-switch"
      data-language={selected}
      role="group"
      aria-label={selected === "kk" ? "Интерфейс тілі" : "Язык интерфейса"}
    >
      <span className="language-indicator" aria-hidden="true" />
      <button
        type="button"
        lang="ru"
        aria-label="Русский"
        aria-pressed={selected === "ru"}
        onClick={() => changeLanguage("ru")}
      >
        RU
      </button>
      <button
        type="button"
        lang="kk"
        aria-label="Қазақша"
        aria-pressed={selected === "kk"}
        onClick={() => changeLanguage("kk")}
      >
        KZ
      </button>
    </div>
  );
}
export function Loading() {
  const { t } = useTranslation();
  return (
    <div className="state" role="status">
      <LoaderCircle className="spin" />
      {t("loading")}
    </div>
  );
}
export function Empty({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="state">
      <BookOpen size={36} />
      <h3>{t("empty")}</h3>
      <p>{t("emptyHint")}</p>
      {children}
    </div>
  );
}
export function ErrorState({
  error,
  retry,
  title,
}: {
  title?: string;
  error: unknown;
  retry?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="error" role="alert">
      <strong>{title || t("error")}</strong>
      <p>{error instanceof Error ? error.message : String(error)}</p>
      {retry && <button onClick={retry}>{t("retry")}</button>}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const { t } = useTranslation();
  const close = () => {
    if (ref.current?.querySelector('form[data-pending="true"]')) return;
    if (
      ref.current?.querySelector('form[data-dirty="true"]') &&
      !window.confirm(t("ux.unsavedConfirm"))
    )
      return;
    ref.current
      ?.querySelector("form")
      ?.dispatchEvent(new Event("reset", { bubbles: true }));
    onClose();
  };
  useEffect(() => {
    const dialog = ref.current;
    const opener = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog?.showModal();
    return () => {
      dialog?.close();
      document.body.style.overflow = previousOverflow;
      opener?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onKeyDown={(event) => {
        // Repeated native CloseWatcher cancellation can become non-cancelable.
        // Handle Escape before its default action so pending/dirty guards hold.
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          close();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      aria-label={title}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button
          type="button"
          className="icon-button"
          onClick={close}
          aria-label={t("close")}
        >
          <X />
        </button>
      </div>
      <div className="modal-body" tabIndex={0}>
        {children}
      </div>
    </dialog>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <span className="badge">
      {typeof children === "string" ? t(children) : children}
    </span>
  );
}
export function ProgressBar({ value }: { value: number }) {
  const { t } = useTranslation();
  return (
    <div
      className="progress"
      role="progressbar"
      aria-label={t("progress")}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span style={{ width: `${value}%` }} />
    </div>
  );
}

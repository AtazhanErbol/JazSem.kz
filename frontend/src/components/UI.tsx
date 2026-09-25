import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { BookOpen, LoaderCircle, X } from "lucide-react";
import { Link } from "react-router-dom";

export function Logo() {
  return (
    <Link className="logo" to="/">
      <span className="logo-mark">J</span>JazSem
      <span className="muted">.kz</span>
    </Link>
  );
}
export function Language() {
  const { i18n } = useTranslation();
  return (
    <button
      className="language"
      onClick={() => {
        const lng = i18n.language === "ru" ? "kk" : "ru";
        void i18n.changeLanguage(lng);
        localStorage.setItem("language", lng);
        document.documentElement.lang = lng;
      }}
      aria-label="Русский / Қазақша"
    >
      {i18n.language === "ru" ? "RU" : "KZ"} <span>⌄</span>
    </button>
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
}: {
  error: unknown;
  retry?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="error" role="alert">
      <strong>{t("error")}</strong>
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
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog ref={ref} onCancel={onClose} aria-label={title}>
      <div className="modal-head">
        <h2>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Close">
          <X />
        </button>
      </div>
      {children}
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
  return (
    <div
      className="progress"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span style={{ width: `${value}%` }} />
    </div>
  );
}

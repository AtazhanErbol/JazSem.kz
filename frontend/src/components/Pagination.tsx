import { useTranslation } from "react-i18next";
export function Pagination({
  page,
  count,
  onChange,
}: {
  page: number;
  count: number;
  onChange: (page: number) => void;
}) {
  const { t } = useTranslation();
  if (count <= 25) return null;
  return (
    <nav className="pagination" aria-label={t("pages")}>
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        {t("previous")}
      </button>
      <span>
        {page} / {Math.ceil(count / 25)}
      </span>
      <button
        type="button"
        disabled={page * 25 >= count}
        onClick={() => onChange(page + 1)}
      >
        {t("next")}
      </button>
    </nav>
  );
}

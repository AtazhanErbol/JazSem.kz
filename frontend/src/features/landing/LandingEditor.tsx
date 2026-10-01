import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../../services/api";
import { ErrorState, Loading, Modal } from "../../components/UI";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { ResourcePage } from "../manage/ResourcePage";
import { defaultLandingText, type LandingContent } from "./content";
import { landingGroups } from "./editorFields";

export function LandingEditor() {
  const { i18n } = useTranslation();
  const kk = i18n.language === "kk";
  const [language, setLanguage] = useState("ru");
  const [extra, setExtra] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(false);
  useUnsavedChanges(dirty);
  const ask = () =>
    !dirty ||
    window.confirm(
      kk
        ? "Сақталмаған өзгерістерді тастау керек пе?"
        : "Отменить несохранённые изменения?",
    );
  const query = useQuery({
    queryKey: ["landing-draft", language],
    queryFn: () => api<LandingContent>(`landing/?draft=1&language=${language}`),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{kk ? "Басты бет редакторы" : "Редактор главной страницы"}</h1>
          <p>
            {kk
              ? "Мәтінді өзгертіңіз → жобаны сақтаңыз → алдын ала қарап, жариялаңыз."
              : "Измените текст → сохраните черновик → проверьте предпросмотр → опубликуйте."}
          </p>
        </div>
      </div>
      <div className="landing-editor-tabs">
        <button
          disabled={pending}
          aria-pressed={!extra}
          onClick={() => {
            if (extra && ask()) {
              setExtra(false);
              setDirty(false);
            }
          }}
        >
          {kk ? "Басты бет" : "Главная страница"}
        </button>
        <button
          disabled={pending}
          aria-pressed={extra}
          onClick={() => {
            if (!extra && ask()) {
              setExtra(true);
              setDirty(false);
            }
          }}
        >
          {kk ? "Қосымша блоктар" : "Дополнительные блоки"}
        </button>
      </div>
      {extra ? (
        <ResourcePage resource="content" />
      ) : (
        <>
          <label className="landing-language">
            {kk ? "Өңделетін тіл" : "Язык редактируемой страницы"}
            <select
              disabled={pending}
              value={language}
              onChange={(e) => {
                if (ask()) {
                  setLanguage(e.target.value);
                  setDirty(false);
                }
              }}
            >
              <option value="ru">Русский</option>
              <option value="kk">Қазақша</option>
            </select>
          </label>
          {query.isPending ? (
            <Loading />
          ) : query.error ? (
            <ErrorState
              error={query.error}
              retry={() => void query.refetch()}
            />
          ) : (
            <EditorForm
              key={language}
              language={language}
              initial={query.data}
              dirty={dirty}
              pending={pending}
              setPending={setPending}
              setDirty={setDirty}
            />
          )}
        </>
      )}
    </>
  );
}
function EditorForm({
  language,
  initial,
  pending,
  setPending,
  dirty,
  setDirty,
}: {
  language: string;
  initial: LandingContent;
  pending: boolean;
  setPending: (value: boolean) => void;
  dirty: boolean;
  setDirty: (value: boolean) => void;
}) {
  const { i18n } = useTranslation();
  const kk = i18n.language === "kk";
  const client = useQueryClient();
  const [value, setValue] = useState<LandingContent>(() => ({
    ...initial,
    texts: Object.fromEntries(
      landingGroups.flatMap((g) =>
        g.fields.map(([key]) => [
          key,
          initial.texts[key] ?? defaultLandingText(key, language),
        ]),
      ),
    ),
  }));
  const [active, setActive] = useState("hero");
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const [confirm, setConfirm] = useState(false);
  const group = landingGroups.find((g) => g.id === active)!;
  const update = (next: LandingContent) => {
    setValue(next);
    setDirty(true);
    setMessage("");
  };
  async function save(publish: boolean) {
    setPending(true);
    setError(undefined);
    setMessage("");
    try {
      await api("landing/", "POST", { ...value, language, publish });
      setDirty(false);
      setConfirm(false);
      client.setQueryData(["landing-draft", language], value);
      await client.invalidateQueries({ queryKey: ["landing-settings"] });
      setMessage(
        publish
          ? kk
            ? "Жарияланды. Өзгерістер басты бетте көрінеді."
            : "Опубликовано. Изменения видны на главной странице."
          : kk
            ? "Жоба сақталды. Келушілер бұрынғы нұсқаны көреді."
            : "Черновик сохранён. Посетители пока видят прежнюю версию.",
      );
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <div className="landing-editor-actions">
        <button disabled={pending} onClick={() => void save(false)}>
          {kk ? "Жобаны сақтау" : "Сохранить черновик"}
        </button>
        {!dirty && (
          <a
            className="button"
            href={`/?preview=1&language=${language}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {kk ? "Алдын ала қарау ↗" : "Предпросмотр ↗"}
          </a>
        )}
        <button
          className="primary"
          disabled={pending}
          onClick={() => setConfirm(true)}
        >
          {kk ? "Жариялау" : "Опубликовать"}
        </button>
        <span className="muted">
          {dirty
            ? kk
              ? "Өзгерістер сақталмаған. Алдын ала қарау үшін сақтаңыз."
              : "Есть несохранённые изменения. Для предпросмотра сохраните черновик."
            : kk
              ? "RU және KZ бөлек жарияланады."
              : "Русская и казахская версии публикуются отдельно."}
        </span>
      </div>
      {error != null && <ErrorState error={error} />}
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      <div className="landing-editor-layout">
        <nav aria-label={kk ? "Бет бөлімдері" : "Разделы страницы"}>
          {landingGroups.map((g) => (
            <button
              key={g.id}
              aria-pressed={active === g.id}
              onClick={() => setActive(g.id)}
            >
              {kk ? g.kk : g.ru}
            </button>
          ))}
        </nav>
        <section className="panel">
          <h2>{kk ? group.kk : group.ru}</h2>
          <fieldset disabled={pending}>
            {[
              "about",
              "features",
              "learning",
              "creation",
              "how",
              "teachers",
              "faq",
              "final",
            ].includes(active) && (
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={!value.hidden.includes(active)}
                  onChange={(e) =>
                    update({
                      ...value,
                      hidden: e.target.checked
                        ? value.hidden.filter((x) => x !== active)
                        : [...value.hidden, active],
                    })
                  }
                />
                {kk ? "Бөлімді көрсету" : "Показывать раздел на сайте"}
              </label>
            )}
            {active === "visual" && (
              <label>
                {kk
                  ? "Кітап орнына сурет (HTTPS сілтемесі)"
                  : "Картинка вместо 3D-книги (HTTPS-ссылка)"}
                <input
                  type="url"
                  value={value.image}
                  maxLength={2000}
                  placeholder="https://…"
                  onChange={(e) => update({ ...value, image: e.target.value })}
                />
                <small className="muted">
                  {kk
                    ? "Ашық суретке сілтеме. Бос қалдырсаңыз, 3D-кітап көрсетіледі. Құпия не уақытша сілтемелерді қолданбаңыз."
                    : "Ссылка на общедоступную картинку. Оставьте пустым, чтобы показывать 3D-книгу. Не используйте секретные или временные ссылки."}
                </small>
              </label>
            )}
            {group.fields.map(([key, ru, kz]) => (
              <label key={key}>
                {kk ? kz : ru}
                <textarea
                  rows={key.endsWith("Text") || key.endsWith("Answer") ? 4 : 2}
                  maxLength={4000}
                  value={value.texts[key] ?? ""}
                  onChange={(e) =>
                    update({
                      ...value,
                      texts: { ...value.texts, [key]: e.target.value },
                    })
                  }
                />
              </label>
            ))}
          </fieldset>
        </section>
      </div>
      {confirm && (
        <Modal
          title={
            kk ? "Өзгерістерді жариялау керек пе?" : "Опубликовать изменения?"
          }
          onClose={() => {
            if (!pending) setConfirm(false);
          }}
        >
          <p>
            {kk
              ? "Бұл тілдегі басты бет барлық келушілер үшін жаңартылады."
              : "Главная страница на выбранном языке обновится для всех посетителей."}
          </p>
          <div className="form-actions">
            <button disabled={pending} onClick={() => setConfirm(false)}>
              {kk ? "Бас тарту" : "Отмена"}
            </button>
            <button
              className="primary"
              disabled={pending}
              onClick={() => void save(true)}
            >
              {kk ? "Жариялауды растау" : "Подтвердить публикацию"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

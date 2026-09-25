import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ArrowUpRight, ArrowDown, Plus } from "lucide-react";
import { Language, Logo } from "../../components/UI";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import type { Page, Row } from "../../entities/types";
import { Sculpture } from "./Sculpture";
import "./atelier.css";

export function Landing() {
  const { t, i18n } = useTranslation();
  const kk = i18n.language === "kk";
  const words = kk
    ? {
        edition: "ЖАЗҒЫ СЕМЕСТР · БІЛІМ БЕРУ ПЛАТФОРМАСЫ",
        title: "Өзіңізбен",
        italic: "қалатын",
        end: "білім.",
        intro:
          "Жаңа тақырыпты түсіну. Тәжірибеде қолдану. Алға қадам жасау. Өз қарқыныңызбен, оқытушының қолдауымен.",
        start: "Оқуды бастау",
        explore: "Платформамен танысу",
        object: "БІЛІМ МЕН ТӘЖІРИБЕ",
        hint: "Курсорды жылжытыңыз — пішін қозғалады",
        caption:
          "Бір-бірімен байланысқан екі пішін. Білім мен тәжірибе сияқты.",
        note: "Өз қарқыныңыз. Нақты бағыт.",
        noteText:
          "JazSem оқу материалдарын, тәжірибені және оқытушының пікірін бір ортаға біріктіреді.",
        index: "ОҚУ ТӘЖІРИБЕСІ",
        section: "Бәрі өз орнында.",
        rows: [
          "Түсінуге арналған кеңістік",
          "Тәжірибе арқылы білім",
          "Маңызды кері байланыс",
        ],
        descriptions: [
          "Апталар мен тақырыптарға бөлінген курс. Қажетті материалдар бір жерде, оқу бағыты әрдайым түсінікті.",
          "Тапсырмалар мен тесттер теорияны қолдануға көмектеседі. Жауаптар сақталады, нәтижелер қолжетімді.",
          "Оқытушының пікірін алыңыз, жұмысты түзетіңіз және оқу барысын бағадан бөлек қадағалаңыз.",
        ],
        studio: "ОҚЫТУШЫҒА",
        studioTitle: "Сіздің біліміңіз.\nЖаңа мүмкіндіктер.",
        studioText:
          "Өз материалдарыңыздан курс құрастырыңыз. AI алғашқы жобаны дайындайды, ал мазмұн мен жариялау шешімі сізде қалады.",
        studioLink: "Оқытушы кабинетіне",
        steps: [
          "Материалдарыңызды қосыңыз",
          "Курсты өңдеңіз",
          "Студенттерге тағайындаңыз",
        ],
        closing: "Келесі қадам —",
        closingItalic: "сізден.",
        footer: "Білімге арналған кеңістік. Қазақстан.",
      }
    : {
        edition: "ЛЕТНИЙ СЕМЕСТР · ОБРАЗОВАТЕЛЬНАЯ ПЛАТФОРМА",
        title: "Знания,",
        italic: "которые",
        end: "остаются.",
        intro:
          "Разобраться в новом. Применить на практике. Сделать шаг вперёд. В своём ритме, с поддержкой преподавателя.",
        start: "Начать обучение",
        explore: "Знакомство с платформой",
        object: "ЗНАНИЕ И ПРАКТИКА",
        hint: "Двигайте курсор — форма откликается",
        caption: "Две формы, связанные между собой. Как знание и практика.",
        note: "Свой ритм. Ясное направление.",
        noteText:
          "JazSem объединяет учебные материалы, практику и обратную связь преподавателя в одном пространстве.",
        index: "ОПЫТ ОБУЧЕНИЯ",
        section: "Всё на своём месте.",
        rows: [
          "Пространство для понимания",
          "Знание через практику",
          "Обратная связь по существу",
        ],
        descriptions: [
          "Курс, собранный по неделям и темам. Нужные материалы рядом, а следующий шаг всегда понятен.",
          "Задания и тесты помогают перейти от теории к действию. Ответы сохраняются, результаты доступны в кабинете.",
          "Получайте комментарии преподавателя, дорабатывайте работы и следите за прогрессом отдельно от оценок.",
        ],
        studio: "ПРЕПОДАВАТЕЛЯМ",
        studioTitle: "Ваши знания.\nНовые возможности.",
        studioText:
          "Соберите курс из собственных материалов. AI подготовит первый черновик, а содержание и решение о публикации останутся за вами.",
        studioLink: "В кабинет преподавателя",
        steps: [
          "Добавьте свои материалы",
          "Отредактируйте курс",
          "Назначьте его студентам",
        ],
        closing: "Следующая глава —",
        closingItalic: "ваша.",
        footer: "Пространство для знаний. Казахстан.",
      };
  const content = useQuery({
    queryKey: ["public-content", i18n.language],
    queryFn: () => api<Page<Row>>(`public-content/?language=${i18n.language}`),
  });
  return (
    <div className="atelier">
      <header className="atelier-header">
        <Logo />
        <nav aria-label={kk ? "Негізгі навигация" : "Основная навигация"}>
          <a href="#experience">{t("features")}</a>
          <a href="#teachers">{t("forTeachers")}</a>
          <a href="#faq">{t("faq")}</a>
        </nav>
        <div className="atelier-actions">
          <Language />
          <Link className="atelier-login" to="/login">
            {t("login")} <ArrowUpRight size={16} />
          </Link>
        </div>
      </header>
      <main>
        <section className="atelier-hero">
          <div className="atelier-copy">
            <div className="atelier-kicker">
              <span />
              {words.edition}
            </div>
            <h1>
              {words.title}
              <br />
              <em>{words.italic}</em>
              <br />
              {words.end}
            </h1>
            <p>{words.intro}</p>
            <Link className="atelier-cta" to="/login">
              {words.start}
              <span>
                <ArrowUpRight size={22} />
              </span>
            </Link>
            <a className="atelier-explore" href="#experience">
              <ArrowDown size={15} />
              {words.explore}
            </a>
          </div>
          <div className="atelier-art">
            <div className="art-topline">
              <span>J / OBJECT № 01</span>
              <span>{words.object}</span>
            </div>
            <Sculpture />
            <div className="art-bottom">
              <span className="art-cross">+</span>
              <span>{words.hint}</span>
              <span>360°</span>
            </div>
            <p className="art-caption">{words.caption}</p>
          </div>
        </section>
        <section className="atelier-manifesto">
          <span className="atelier-section-id">01 / JAZSEM</span>
          <h2>{words.note}</h2>
          <p>{words.noteText}</p>
        </section>
        <section className="atelier-experience" id="experience">
          <div className="atelier-section-head">
            <span className="atelier-section-id">{words.index}</span>
            <h2>{words.section}</h2>
            <span className="atelier-small">RU / KZ</span>
          </div>
          <div className="atelier-rows">
            {words.rows.map((title, i) => (
              <article key={title}>
                <span className="atelier-row-number">0{i + 1}</span>
                <h3>{title}</h3>
                <p>{words.descriptions[i]}</p>
                <ArrowUpRight size={22} />
              </article>
            ))}
          </div>
        </section>
        <section id="teachers" className="atelier-studio">
          <div className="studio-copy">
            <span className="atelier-section-id">02 / {words.studio}</span>
            <h2>{words.studioTitle}</h2>
            <p>{words.studioText}</p>
            <Link className="studio-link" to="/login">
              {words.studioLink}
              <ArrowUpRight size={20} />
            </Link>
          </div>
          <div className="studio-paper">
            <div className="paper-meta">
              <span>JAZSEM / COURSE STUDIO</span>
              <span>↗</span>
            </div>
            <div className="paper-monogram">
              J<span>.</span>
            </div>
            <div className="paper-rule" />
            {words.steps.map((step, i) => (
              <div className="paper-step" key={step}>
                <span>0{i + 1}</span>
                {step}
                <Plus size={14} />
              </div>
            ))}
            <div className="paper-foot">
              {kk
                ? "Жақсы курс сізден басталады."
                : "Хороший курс начинается с вас."}
            </div>
          </div>
        </section>
        <section id="faq" className="atelier-faq">
          <div>
            <span className="atelier-section-id">03 / FAQ</span>
            <h2>{t("faq")}</h2>
          </div>
          <div>
            {[1, 2, 3].map((i) => (
              <details key={i}>
                <summary>
                  {t("faq" + i)}
                  <Plus size={18} />
                </summary>
                <p>{t("faq" + i + "Answer")}</p>
              </details>
            ))}
          </div>
        </section>
        {content.data?.results.map((block) => (
          <section className="atelier-cms" key={block.id}>
            <h2>{String(block.title)}</h2>
            <p>{String(block.body)}</p>
          </section>
        ))}
        <section className="atelier-closing">
          <span className="atelier-section-id">JAZSEM.KZ</span>
          <h2>
            {words.closing}
            <br />
            <em>{words.closingItalic}</em>
          </h2>
          <Link
            className="atelier-circle-link"
            to="/login"
            aria-label={words.start}
          >
            <ArrowUpRight />
          </Link>
        </section>
      </main>
      <footer className="atelier-footer">
        <Logo />
        <span>{words.footer}</span>
        <a href="#experience">{kk ? "Платформа туралы" : "О платформе"} ↗</a>
        <Language />
      </footer>
    </div>
  );
}

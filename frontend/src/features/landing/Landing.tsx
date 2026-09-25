import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  BookOpen,
  Check,
  ClipboardCheck,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { Language, Logo } from "../../components/UI";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import type { Page, Row } from "../../entities/types";
import { BookScene } from "./BookScene";
import { useLandingMotion } from "./useLandingMotion";
import "./refresh.css";

export function Landing() {
  const { t, i18n } = useTranslation();
  const { root, scrolled } = useLandingMotion();
  const content = useQuery({
    queryKey: ["public-content", i18n.language],
    queryFn: () => api<Page<Row>>(`public-content/?language=${i18n.language}`),
  });
  return (
    <div className="landing" ref={root}>
      <header className={`landing-header${scrolled ? " is-scrolled" : ""}`}>
        <Logo />
        <nav>
          <a href="#features">{t("features")}</a>
          <a href="#how">{t("how")}</a>
          <a href="#teachers">{t("forTeachers")}</a>
          <a href="#faq">FAQ</a>
        </nav>
        <div className="row-actions">
          <Language />
          <Link className="button primary" to="/login">
            {t("login")} <ArrowUpRight size={17} />
          </Link>
        </div>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <span className="pill">
              <span /> {t("heroLabel")}
            </span>
            <h1>
              {i18n.language === "kk"
                ? "Оқуды жалғастырыңыз."
                : "Продолжайте учиться."}{" "}
              <span>
                {i18n.language === "kk"
                  ? "Алға ұмтылыңыз."
                  : "Двигайтесь вперёд."}
              </span>
            </h1>
            <p>{t("heroText")}</p>
            <div className="row-actions">
              <Link className="button primary large" to="/login">
                {t("heroCta")} <ArrowUpRight size={20} />
              </Link>
              <a className="text-link" href="#how">
                {t("how")} <ArrowRight size={18} />
              </a>
            </div>
            <div className="hero-note">
              <Check size={16} /> RU / KZ <span>•</span> {t("forStudents")}{" "}
              <span>•</span> {t("forTeachers")}
            </div>
          </div>
          <div className="hero-visual hero-book">
            <div className="scene-label">
              <span className="scene-dot" /> JAZSEM /{" "}
              {i18n.language === "kk"
                ? "ЖАҢА МҮМКІНДІКТЕР"
                : "НОВЫЕ ВОЗМОЖНОСТИ"}
            </div>
            <BookScene />
            <div className="scene-tag">
              <BookOpen size={16} />
              {i18n.language === "kk"
                ? "Білімнен — тәжірибеге"
                : "От знаний — к практике"}
            </div>
            <div className="floating-card">
              <span className="check-disc">
                <Check size={20} />
              </span>
              <div>
                <strong>
                  {i18n.language === "kk"
                    ? "Сіздің қарқыныңыз. Сіздің нәтижеңіз."
                    : "Ваш темп. Ваш результат."}
                </strong>
                <small>
                  {i18n.language === "kk"
                    ? "Оқыңыз. Байқап көріңіз. Дамыңыз."
                    : "Изучайте. Пробуйте. Растите."}
                </small>
              </div>
            </div>
            <span className="scene-hint">
              {i18n.language === "kk"
                ? "Курсорды жылжытыңыз"
                : "Попробуйте подвигать курсором"}{" "}
              ↗
            </span>
          </div>
        </section>
        <section className="about-strip">
          <span>01 / JAZSEM</span>
          <h2>{t("aboutTitle")}</h2>
          <p>{t("aboutText")}</p>
        </section>
        <section id="features" className="landing-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">{t("features")}</span>
              <h2>{t("aboutTitle")}</h2>
            </div>
            <span className="section-number">01—03</span>
          </div>
          <div className="feature-grid">
            {[BookOpen, ClipboardCheck, Sparkles].map((Icon, i) => (
              <article className="feature-card" key={i}>
                <span className="feature-icon">
                  <Icon />
                </span>
                <span className="feature-number">0{i + 1}</span>
                <h3>{t("feature" + (i + 1))}</h3>
                <p>{t("feature" + (i + 1) + "Text")}</p>
              </article>
            ))}
          </div>
        </section>
        <section id="how" className="how-section landing-section">
          <span className="eyebrow">{t("how")}</span>
          <h2>
            {i18n.language === "kk"
              ? "Нәтижеге апаратын жол."
              : "Ваш путь к результату."}
          </h2>
          <div className="steps-grid">
            {[1, 2, 3].map((i) => (
              <article key={i}>
                <span className="step-number">0{i}</span>
                <h3>{t("how" + i)}</h3>
                <p>{t("how" + i + "Text")}</p>
              </article>
            ))}
          </div>
        </section>
        <section id="teachers" className="landing-section audience-grid">
          <article className="teacher-block">
            <Sparkles />
            <span className="eyebrow">{t("forTeachers")}</span>
            <h2>{t("teacherTitle")}</h2>
            <p>{t("teacherText")}</p>
            <div className="flow-line">{t("aiFlow")}</div>
            <Link className="button light" to="/login">
              {t("login")} <ArrowUpRight size={18} />
            </Link>
          </article>
          <article className="student-block">
            <BookOpen />
            <span className="eyebrow">{t("forStudents")}</span>
            <h2>{t("studentTitle")}</h2>
            <p>{t("studentText")}</p>
            <Link className="button" to="/login">
              {t("continue")} <ArrowUpRight size={18} />
            </Link>
          </article>
        </section>
        <section id="faq" className="landing-section faq-section">
          <div>
            <span className="eyebrow">FAQ</span>
            <h2>{t("faq")}</h2>
          </div>
          <div>
            {[1, 2, 3].map((i) => (
              <details key={i}>
                <summary>{t("faq" + i)}</summary>
                <p>{t("faq" + i + "Answer")}</p>
              </details>
            ))}
          </div>
        </section>
        {content.data?.results.map((block) => (
          <section className="landing-section" key={block.id}>
            <h2>{String(block.title)}</h2>
            <p>{String(block.body)}</p>
          </section>
        ))}
        <section className="final-cta">
          <span className="eyebrow">JAZSEM.KZ</span>
          <h2>{t("finalTitle")}</h2>
          <Link className="button light large" to="/login">
            {t("heroCta")} <ArrowUpRight size={20} />
          </Link>
        </section>
      </main>
      <footer>
        <Logo />
        <span>{t("copyright")}</span>
        <Language />
      </footer>
    </div>
  );
}

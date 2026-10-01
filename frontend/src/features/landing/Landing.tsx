import { defaultLandingText, type LandingContent } from "./content";
import { useEffect, useRef, useState } from "react";
import { ErrorState, Loading } from "../../components/UI";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowUpRight,
  BookOpen,
  Check,
  ClipboardCheck,
  Sparkles,
  ArrowRight,
  FileText,
  MessageSquareText,
  PencilLine,
  FileSpreadsheet,
  ShieldCheck,
  Menu,
  X,
} from "lucide-react";
import { Language, Logo } from "../../components/UI";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import type { Page, Row } from "../../entities/types";
import { BookScene } from "./BookScene";
import { useLandingMotion } from "./useLandingMotion";
import "./refresh.css";
import "./editorial.css";

export function Landing() {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigation = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (menuOpen) navigation.current?.querySelector("a")?.focus();
  }, [menuOpen]);
  const { i18n } = useTranslation();
  const [params] = useSearchParams();
  const preview = params.get("preview") === "1";
  const language =
    preview && ["ru", "kk"].includes(params.get("language") || "")
      ? params.get("language")!
      : i18n.language;
  const settings = useQuery({
    queryKey: ["landing-settings", language, preview],
    queryFn: () =>
      api<LandingContent>(
        `landing/?language=${language}${preview ? "&draft=1" : ""}`,
      ),
  });
  const t = (key: string) =>
    settings.data?.texts[key] ?? defaultLandingText(key, language);
  const shown = (key: string) => !settings.data?.hidden.includes(key);
  const { root, scrolled } = useLandingMotion(!preview || !!settings.data);
  const content = useQuery({
    queryKey: ["public-content", language],
    queryFn: () => api<Page<Row>>(`public-content/?language=${language}`),
  });
  if (preview && settings.isPending) return <Loading />;
  if (preview && settings.error) return <ErrorState error={settings.error} />;
  return (
    <div className="landing" ref={root}>
      <a className="landing-skip" href="#landing-main">
        {t("skipContent")}
      </a>
      {preview && (
        <div className="landing-preview-note">
          {language === "kk"
            ? "Алдын ала қарау — сақталған жоба, жарияланбаған өзгерістер"
            : "Предпросмотр сохранённого черновика — изменения ещё не опубликованы"}
        </div>
      )}
      <header
        className={`landing-header${scrolled ? " is-scrolled" : ""}`}
        onKeyDown={(event) => {
          if (event.key === "Escape" && menuOpen) {
            setMenuOpen(false);
            menuButton.current?.focus();
          }
        }}
      >
        <Logo />
        <nav
          id="landing-navigation"
          ref={navigation}
          className={menuOpen ? "is-open" : ""}
          aria-label={t("features")}
        >
          {shown("features") && (
            <a href="#features" onClick={() => setMenuOpen(false)}>
              {t("features")}
            </a>
          )}
          {shown("how") && (
            <a href="#how" onClick={() => setMenuOpen(false)}>
              {t("how")}
            </a>
          )}
          {shown("teachers") && (
            <a href="#teachers" onClick={() => setMenuOpen(false)}>
              {t("forTeachers")}
            </a>
          )}
          {shown("faq") && (
            <a href="#faq" onClick={() => setMenuOpen(false)}>
              FAQ
            </a>
          )}
        </nav>
        <div className="row-actions">
          {preview ? (
            <span>{language === "kk" ? "Қазақша" : "Русский"}</span>
          ) : (
            <Language />
          )}
          <Link className="button primary" to="/login">
            {t("login")} <ArrowUpRight size={17} />
          </Link>
          <button
            className="landing-menu-toggle"
            ref={menuButton}
            aria-label={t(menuOpen ? "menuClose" : "menuOpen")}
            aria-expanded={menuOpen}
            aria-controls="landing-navigation"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>
      <main id="landing-main" tabIndex={-1}>
        <section className="hero">
          <div className="hero-copy">
            <span className="pill">
              <span /> {t("heroLabel")}
            </span>
            <h1>
              {t("heroTitle")} <span>{t("heroAccent")}</span>
            </h1>
            <p>{t("heroText")}</p>
            <div className="row-actions">
              <Link className="button primary large" to="/login">
                {t("heroCta")} <ArrowUpRight size={20} />
              </Link>
              {shown("how") && (
                <a className="text-link" href="#how">
                  {t("how")} <ArrowRight size={18} />
                </a>
              )}
            </div>
            <div className="hero-note">
              <Check size={16} /> RU / KZ <span>•</span> {t("forStudents")}{" "}
              <span>•</span> {t("forTeachers")}
            </div>
          </div>
          <div className="hero-visual hero-book">
            <div className="scene-label">
              <span className="scene-dot" /> JAZSEM / {t("sceneLabel")}
            </div>
            {settings.data?.image ? (
              <img
                className="landing-custom-image"
                src={settings.data.image}
                alt={t("imageAlt")}
                referrerPolicy="no-referrer"
              />
            ) : (
              <BookScene />
            )}
            <div className="scene-tag">
              <BookOpen size={16} />
              {t("sceneTag")}
            </div>
            <div className="floating-card">
              <span className="check-disc">
                <Check size={20} />
              </span>
              <div>
                <strong>{t("sceneTitle")}</strong>
                <small>{t("sceneText")}</small>
              </div>
            </div>
            {!settings.data?.image && (
              <span className="scene-hint">{t("sceneHint")} ↗</span>
            )}
          </div>
        </section>
        {shown("about") && (
          <section className="about-strip">
            <BookOpen size={28} aria-hidden="true" />
            <h2>{t("aboutTitle")}</h2>
            <p>{t("aboutText")}</p>
          </section>
        )}
        {shown("features") && (
          <section id="features" className="landing-section">
            <div className="section-heading">
              <div>
                <span className="eyebrow">{t("features")}</span>
                <h2>{t("featuresTitle")}</h2>
              </div>
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
        )}
        {shown("learning") && (
          <section id="learning" className="landing-section learning-section">
            <div className="learning-copy">
              <span className="eyebrow">{t("learningLabel")}</span>
              <h2>{t("learningTitle")}</h2>
              <p>{t("learningText")}</p>
              <div className="learning-note">
                <ShieldCheck size={20} aria-hidden="true" />
                <p>{t("learningNote")}</p>
              </div>
            </div>
            <div className="week-preview">
              <div className="week-preview-heading">
                <span>{t("weekExample")}</span>
                <BookOpen size={24} aria-hidden="true" />
              </div>
              <h3>{t("weekTitle")}</h3>
              <ol>
                {[FileText, ClipboardCheck, MessageSquareText].map(
                  (Icon, index) => (
                    <li key={index}>
                      <span className="week-stage-icon">
                        <Icon size={21} aria-hidden="true" />
                      </span>
                      <div>
                        <h4>{t(`week${index + 1}`)}</h4>
                        <p>{t(`week${index + 1}Text`)}</p>
                      </div>
                    </li>
                  ),
                )}
              </ol>
            </div>
          </section>
        )}
        {shown("creation") && (
          <section id="creation" className="creation-section">
            <div className="landing-section">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">{t("creationLabel")}</span>
                  <h2>{t("creationTitle")}</h2>
                </div>
                <p>{t("creationText")}</p>
              </div>
              <div className="creation-methods">
                <article>
                  <span className="method-icon">
                    <PencilLine size={26} aria-hidden="true" />
                  </span>
                  <h3>{t("manualTitle")}</h3>
                  <p>{t("manualText")}</p>
                  <div className="method-note">
                    <FileSpreadsheet size={18} aria-hidden="true" />
                    <span>{t("manualImport")}</span>
                  </div>
                </article>
                <article>
                  <span className="method-icon">
                    <Sparkles size={26} aria-hidden="true" />
                  </span>
                  <h3>{t("assistedTitle")}</h3>
                  <p>{t("assistedText")}</p>
                  <div className="method-note">
                    <Check size={18} aria-hidden="true" />
                    <span>{t("assistedReview")}</span>
                  </div>
                </article>
              </div>
              <p className="creation-note">
                <ShieldCheck size={18} aria-hidden="true" />
                <span>{t("creationNote")}</span>
              </p>
            </div>
          </section>
        )}
        {shown("how") && (
          <section id="how" className="how-section landing-section">
            <span className="eyebrow">{t("how")}</span>
            <h2>{t("howTitle")}</h2>
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
        )}
        {shown("teachers") && (
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
        )}
        {shown("faq") && (
          <section id="faq" className="landing-section faq-section">
            <div>
              <span className="eyebrow">FAQ</span>
              <h2>{t("faq")}</h2>
            </div>
            <div>
              {[1, 2, 3].map((i) => (
                <details key={i}>
                  <summary>
                    {t("faq" + i)}
                    <span className="faq-plus" aria-hidden="true">
                      +
                    </span>
                  </summary>
                  <p>{t("faq" + i + "Answer")}</p>
                </details>
              ))}
            </div>
          </section>
        )}
        {content.data?.results.map((block) => (
          <section className="landing-section landing-extra" key={block.id}>
            <h2>{String(block.title)}</h2>
            <p>{String(block.body)}</p>
          </section>
        ))}
        {shown("final") && (
          <section className="final-cta">
            <span className="eyebrow">JAZSEM.KZ</span>
            <h2>{t("finalTitle")}</h2>
            <Link className="button light large" to="/login">
              {t("heroCta")} <ArrowUpRight size={20} />
            </Link>
          </section>
        )}
      </main>
      <footer>
        <Logo />
        <span>{t("copyright")}</span>
        {preview ? (
          <span>{language === "kk" ? "Қазақша" : "Русский"}</span>
        ) : (
          <Language />
        )}
      </footer>
    </div>
  );
}

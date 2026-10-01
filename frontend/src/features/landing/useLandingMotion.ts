import { useEffect, useRef, useState } from "react";

export function useLandingMotion(ready = true) {
  const root = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    let scrollFrame = 0;
    const updateScroll = () => {
      scrollFrame = 0;
      setScrolled(window.scrollY > 12);
      const progress = reduced.matches
        ? 0
        : Math.min(1, Math.max(0, window.scrollY / window.innerHeight));
      root.current?.style.setProperty("--hero-progress", progress.toFixed(3));
    };
    const scroll = () => {
      if (!scrollFrame) scrollFrame = requestAnimationFrame(updateScroll);
    };
    updateScroll();
    window.addEventListener("scroll", scroll, { passive: true });
    const elements = Array.from(
      root.current?.querySelectorAll<HTMLElement>(
        ".about-strip, .landing-section > .section-heading, .feature-card, .learning-copy, .week-preview, .creation-methods article, .how-section > h2, .steps-grid article, .audience-grid article, .faq-section, .final-cta",
      ) ?? [],
    );
    let observer: IntersectionObserver | undefined;
    const setup = () => {
      updateScroll();
      observer?.disconnect();
      elements.forEach((el) => el.classList.remove("reveal-pending"));
      if (reduced.matches) return;
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-revealed");
              observer?.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.08, rootMargin: "0px 0px -24px 0px" },
      );
      elements.forEach((el, index) => {
        el.style.setProperty("--reveal-delay", `${(index % 3) * 60}ms`);
        el.classList.add("reveal-pending");
        observer!.observe(el);
      });
    };
    setup();
    reduced.addEventListener("change", setup);
    return () => {
      window.removeEventListener("scroll", scroll);
      cancelAnimationFrame(scrollFrame);
      observer?.disconnect();
      reduced.removeEventListener("change", setup);
    };
  }, [ready]);
  return { root, scrolled };
}

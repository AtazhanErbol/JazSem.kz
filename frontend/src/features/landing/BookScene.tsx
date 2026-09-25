import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import "./book.css";

export function BookScene() {
  const ref = useRef<HTMLDivElement>(null);
  const { i18n } = useTranslation();
  useEffect(() => {
    const scene = ref.current!;
    const area = scene.closest(".hero-visual") || scene;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0,
      visible = true,
      x = 0,
      y = 0,
      targetX = 0,
      targetY = 0,
      last = 0;
    const paint = () => {
      scene.style.setProperty("--book-x", x.toFixed(4));
      scene.style.setProperty("--book-y", y.toFixed(4));
    };
    const animate = (now: number) => {
      frame = 0;
      if (!visible || document.hidden || reduced.matches) return;
      const blend = 1 - Math.exp(-Math.min(last ? now - last : 16, 64) / 115);
      last = now;
      x += (targetX - x) * blend;
      y += (targetY - y) * blend;
      paint();
      if (Math.abs(targetX - x) + Math.abs(targetY - y) > 0.001)
        frame = requestAnimationFrame(animate);
    };
    const schedule = () => {
      if (!frame && visible && !document.hidden && !reduced.matches) {
        last = 0;
        frame = requestAnimationFrame(animate);
      }
    };
    const reset = () => {
      targetX = 0;
      targetY = 0;
      schedule();
    };
    const move = (event: Event) => {
      const e = event as PointerEvent;
      if (reduced.matches || e.pointerType === "touch") return;
      const r = area.getBoundingClientRect();
      targetX = Math.max(
        -1,
        Math.min(1, ((e.clientX - r.left) / r.width) * 2 - 1),
      );
      targetY = Math.max(
        -1,
        Math.min(1, ((e.clientY - r.top) / r.height) * 2 - 1),
      );
      schedule();
    };
    const sync = () => {
      const paused = !visible || document.hidden || reduced.matches;
      scene.dataset.paused = String(paused);
      cancelAnimationFrame(frame);
      frame = 0;
      if (reduced.matches) {
        x = y = targetX = targetY = 0;
        paint();
      } else schedule();
    };
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      sync();
    });
    observer.observe(scene);
    area.addEventListener("pointermove", move);
    area.addEventListener("pointerleave", reset);
    document.addEventListener("visibilitychange", sync);
    reduced.addEventListener("change", sync);
    sync();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      area.removeEventListener("pointermove", move);
      area.removeEventListener("pointerleave", reset);
      document.removeEventListener("visibilitychange", sync);
      reduced.removeEventListener("change", sync);
    };
  }, []);
  return (
    <div className="book-scene" ref={ref} aria-hidden="true">
      <div className="book-halo" />
      <div className="book-orbit book-orbit-one" />
      <div className="book-orbit book-orbit-two" />
      <div className="book-ground-shadow" />
      <div className="book-position">
        <div className="book-levitate">
          <div className="book-turntable">
            <div className="volume-back" />
            <div className="volume-pages" />
            <div className="volume-edge volume-edge-right" />
            <div className="volume-edge volume-edge-top" />
            <div className="volume-edge volume-edge-bottom" />
            <div className="volume-spine">
              <span>JAZSEM · EDUCATION</span>
            </div>
            <div className="volume-ribbon" />
            <div className="volume-front">
              <div className="cover-grain" />
              <div className="cover-sheen" />
              <div className="cover-top">
                <span>
                  JAZSEM
                  <br />
                  EDUCATION
                </span>
                <span>01 —</span>
              </div>
              <img
                className="cover-brand"
                src="/brand/jazsem-mark.png"
                width="160"
                height="160"
                alt=""
              />
              <div className="cover-bottom">
                <span>
                  {i18n.language === "kk"
                    ? "СІЗДІҢ ЖАҢА ТАРАУЫҢЫЗ"
                    : "ВАША НОВАЯ ГЛАВА"}
                </span>
                <span>↗</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="book-page-slip">
        <span>J / NOTES</span>
        <i />
        <i />
        <i />
        <b>↗</b>
      </div>
    </div>
  );
}

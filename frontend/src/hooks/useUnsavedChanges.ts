import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useBlocker } from "react-router-dom";

// Protect normal SPA links, back/forward and refresh. Inputs stay mounted when
// navigation is rejected. Explicit form success resets dirty before leaving.
export function useUnsavedChanges(dirty: boolean) {
  const { t } = useTranslation();
  const leaving = useRef(false);
  useEffect(() => {
    if (!dirty) leaving.current = false;
  }, [dirty]);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty &&
      !leaving.current &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.search !== nextLocation.search),
  );
  useEffect(() => {
    if (blocker.state === "blocked") {
      if (window.confirm(t("ux.unsavedConfirm"))) blocker.proceed();
      else blocker.reset();
    }
  }, [blocker, t]);
  useEffect(() => {
    if (!dirty) return;
    const unload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", unload);
    return () => window.removeEventListener("beforeunload", unload);
  }, [dirty, t]);
  return () => {
    leaving.current = true;
  };
}

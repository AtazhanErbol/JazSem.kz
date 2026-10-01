import { Component, type ReactNode } from "react";
import i18n from "../i18n";

export class RouteBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <main className="state" role="alert">
          <h1>{i18n.t("error")}</h1>
          <p>{i18n.t("serviceUnavailable")}</p>
          <button onClick={() => window.location.reload()}>
            {i18n.t("retry")}
          </button>
        </main>
      );
    return this.props.children;
  }
}

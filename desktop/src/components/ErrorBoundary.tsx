import { Component, type ErrorInfo, type ReactNode } from "react";

import { reportFrontendError } from "../api/client";
import { useLanguage } from "../i18n/useLanguage";

interface Props {
  /** Clears a caught error when it changes, so switching tabs recovers. */
  resetKey?: string;
  children: ReactNode;
}

interface State {
  message: string;
}

/** Functional fallback so the class boundary can translate: class components
 *  can't call useLanguage(), so the render hands off to this subscribed view. */
function ErrorFallback({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const { t } = useLanguage();
  return (
    <div className="page-error">
      <h2>{t("error.title")}</h2>
      <div className="page-error-message">{message}</div>
      <p>{t("error.body")}</p>
      <button onClick={onRetry}>{t("error.retry")}</button>
    </div>
  );
}

/** Keeps one page's render failure from blanking the whole window. Before this
 *  existed, a single `undefined.map()` in DashboardPage tore down the entire
 *  React tree and the app looked like it had failed to boot. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { message: "" };

  static getDerivedStateFromError(error: unknown): State {
    return { message: error instanceof Error ? error.message : String(error) };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    reportFrontendError(
      error.message,
      "boundary",
      `${error.stack ?? ""}\n${info.componentStack ?? ""}`,
    ).catch(() => {});
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.message) {
      this.setState({ message: "" });
    }
  }

  render() {
    if (this.state.message) {
      return (
        <ErrorFallback
          message={this.state.message}
          onRetry={() => this.setState({ message: "" })}
        />
      );
    }
    return this.props.children;
  }
}

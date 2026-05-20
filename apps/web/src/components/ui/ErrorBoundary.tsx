import { Component, type ReactNode } from "react";

import { Button } from "./Button";
import { ErrorBanner } from "./ErrorBanner";

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: 24 }}>
          <ErrorBanner message="Unable to render this view." />
          <div>
            <Button
              variant="outline-violet"
              size="sm"
              onClick={() => {
                window.location.reload();
              }}
            >
              Reload
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

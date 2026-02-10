import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-full p-8">
          <div className="max-w-md w-full bg-[var(--color-bg-card)] border border-red-500/30 rounded-xl p-6 space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <h2 className="text-sm font-semibold text-red-400">Something went wrong</h2>
            </div>
            <pre className="text-xs text-[var(--color-text-muted)] bg-[var(--color-bg)] rounded-lg p-3 overflow-auto max-h-32 whitespace-pre-wrap">
              {this.state.error?.message || 'Unknown error'}
            </pre>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 transition-colors"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

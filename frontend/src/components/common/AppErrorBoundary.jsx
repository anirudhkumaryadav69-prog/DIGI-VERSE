import { Component } from 'react';
import { AlertTriangle, Home, RefreshCw } from 'lucide-react';

class AppErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) {
      console.error('DIGI-VERSE UI ErrorBoundary caught error:', error, info?.componentStack);
    }
  }

  handleReload = () => {
    this.setState({ hasError: false }, () => {
      if (typeof window !== 'undefined') {
        window.location.reload();
      }
    });
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="min-h-screen bg-[#EAF4FC] text-[#263445] flex items-center justify-center px-4 py-12">
        <div
          role="alert"
          className="max-w-lg w-full bg-white border border-[#D5DEE8] rounded-3xl p-8 sm:p-10 text-center space-y-5 shadow-[0_12px_32px_-8px_rgba(38,52,69,0.12)]"
        >
          <div className="w-12 h-12 mx-auto rounded-2xl bg-[#EAF4FC] border border-[#BFDBFE] text-[#2563EB] flex items-center justify-center">
            <AlertTriangle className="w-6 h-6" aria-hidden="true" />
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold text-[#2563EB]">DIGI-VERSE</p>
            <h1 className="text-2xl font-bold tracking-tight text-[#263445]">
              Unable to display this page cleanly
            </h1>
            <p className="text-sm text-[#64748B] leading-relaxed">
              Something unexpected interrupted the storefront view. Reload the page or return home
              to continue browsing.
            </p>
          </div>

          <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={this.handleReload}
              className="dv-btn-primary px-5 py-2.5 text-xs font-semibold inline-flex items-center gap-2"
            >
              <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Reload Page</span>
            </button>
            <a
              href="/"
              className="dv-btn-secondary px-5 py-2.5 text-xs font-semibold inline-flex items-center gap-2"
            >
              <Home className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Return Home</span>
            </a>
          </div>
        </div>
      </div>
    );
  }
}

export default AppErrorBoundary;

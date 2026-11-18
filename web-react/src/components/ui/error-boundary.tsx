import { Component, type ErrorInfo, type ReactNode } from 'react';
import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom';
import { AlertTriangle, Home, RotateCcw } from 'lucide-react';
import { Button } from './button';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[GSN ErrorBoundary]', error, info.componentStack);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <div
        role="alert"
        className="mx-auto my-8 max-w-lg rounded-2xl border border-rose-500/30 bg-surface p-6 text-center shadow-lg space-y-4"
      >
        <div className="mx-auto flex size-12 items-center justify-center rounded-2xl border border-rose-500/30 bg-rose-500/10 text-rose-400">
          <AlertTriangle size={22} />
        </div>
        <div className="space-y-1">
          <h2 className="font-display text-base font-bold text-fg">
            {this.props.fallbackTitle ?? 'Algo inesperado aconteceu nesta tela'}
          </h2>
          <p className="text-xs text-fg-3 leading-relaxed">
            {this.state.error.message || 'Não foi possível renderizar o componente solicitado.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
          <Button variant="primary" size="sm" onClick={this.reset} className="gap-1.5">
            <RotateCcw size={14} /> Tentar novamente
          </Button>
          <Link to="/">
            <Button variant="secondary" size="sm" onClick={this.reset} className="gap-1.5">
              <Home size={14} /> Ir para o início
            </Button>
          </Link>
        </div>
      </div>
    );
  }
}

export function RouteErrorFallback() {
  const err = useRouteError();
  let message = 'Ocorreu uma falha inesperada ao carregar esta rota.';
  if (isRouteErrorResponse(err)) {
    message = `${err.status} — ${err.statusText || 'Rota indisponível'}`;
  } else if (err instanceof Error && err.message) {
    message = err.message;
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-bg p-6">
      <div
        role="alert"
        className="w-full max-w-md rounded-2xl border border-line-strong bg-surface p-6 text-center shadow-xl space-y-4"
      >
        <div className="mx-auto flex size-12 items-center justify-center rounded-2xl border border-amber-400/30 bg-amber-400/10 text-amber-400">
          <AlertTriangle size={22} />
        </div>
        <div className="space-y-1">
          <h1 className="font-display text-lg font-bold text-fg">Falha ao abrir a página</h1>
          <p className="text-xs text-fg-3 leading-relaxed">{message}</p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
          <Button variant="primary" size="sm" onClick={() => window.location.reload()} className="gap-1.5">
            <RotateCcw size={14} /> Recarregar
          </Button>
          <Link to="/">
            <Button variant="secondary" size="sm" className="gap-1.5">
              <Home size={14} /> Início
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

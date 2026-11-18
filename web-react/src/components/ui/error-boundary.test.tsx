import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ErrorBoundary } from './error-boundary';

function BrokenWidget({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Falha simulada de renderização');
  }
  return <div>Conteúdo saudável</div>;
}

describe('ErrorBoundary', () => {
  it('captura erro de renderização sem derrubar a árvore e permite tentar novamente', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    let shouldThrow = true;

    const { rerender } = render(
      <MemoryRouter>
        <ErrorBoundary fallbackTitle="Erro no módulo">
          <BrokenWidget shouldThrow={shouldThrow} />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Erro no módulo')).toBeInTheDocument();
    expect(screen.getByText('Falha simulada de renderização')).toBeInTheDocument();

    shouldThrow = false;
    rerender(
      <MemoryRouter>
        <ErrorBoundary fallbackTitle="Erro no módulo">
          <BrokenWidget shouldThrow={shouldThrow} />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }));
    expect(screen.getByText('Conteúdo saudável')).toBeInTheDocument();
    spy.mockRestore();
  });
});

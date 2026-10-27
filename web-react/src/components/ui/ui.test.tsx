import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EmptyState, ErrorState, LoadingBlock } from './states';
import { Kpi, NumberTicker } from './kpi';

describe('ErrorState', () => {
  it('mostra a mensagem do backend e permite tentar novamente', () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Migracao documental pendente" onRetry={onRetry} />);

    expect(screen.getByText('Não foi possível carregar')).toBeInTheDocument();
    expect(screen.getByText('Migracao documental pendente')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('sem onRetry não oferece botão', () => {
    render(<ErrorState message="x" />);
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('EmptyState / LoadingBlock', () => {
  it('estado vazio explica o motivo', () => {
    render(<EmptyState title="Nenhum prazo" description="Não há prazos nos próximos 30 dias." />);
    expect(screen.getByText('Nenhum prazo')).toBeInTheDocument();
    expect(screen.getByText(/próximos 30 dias/)).toBeInTheDocument();
  });

  it('carregamento é anunciado como status', () => {
    render(<LoadingBlock label="Carregando carteira" />);
    expect(screen.getByRole('status')).toHaveTextContent('Carregando carteira');
  });
});

describe('NumberTicker', () => {
  // Regra §7.2: nunca inventar número para valor ausente.
  it('ausente vira travessão, nunca zero', () => {
    const { container } = render(<NumberTicker value={null} />);
    expect(container.textContent).toBe('—');
  });

  it('texto não numérico é exibido como veio', () => {
    const { container } = render(<NumberTicker value="Não informado" />);
    expect(container.textContent).toBe('Não informado');
  });
});

describe('Kpi', () => {
  it('renderiza rótulo, valor, unidade e contexto', () => {
    render(<Kpi label="Vagas imediatas" value="12" unit="vagas" context="em 3 concursos" />);
    expect(screen.getByText('Vagas imediatas')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('vagas')).toBeInTheDocument();
    expect(screen.getByText('em 3 concursos')).toBeInTheDocument();
  });
});

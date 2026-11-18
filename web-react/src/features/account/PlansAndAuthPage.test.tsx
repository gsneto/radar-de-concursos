import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Sidebar } from '@/app/sidebar';
import { setWorkspaceMode } from '@/lib/auth';
import { AccountPage, PlansPage } from './PlansAndAuthPage';

function renderWithClient(ui: React.ReactElement, initialEntries = ['/']) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PlansPage, AccountPage & WorkspaceMode', () => {
  beforeEach(() => {
    localStorage.clear();
    setWorkspaceMode('student');
    vi.unstubAllGlobals();
  });

  it('renderiza planos comerciais e galeria real de flashcards IA na pagina /planos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            authenticated: false,
            user: null,
            has_admin: true,
            public_mode: false,
            require_auth: false,
            checkout_url: '',
            billing_configured: false,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    renderWithClient(<PlansPage />);

    expect(await screen.findByText(/Plano Pro Aprovação TI/i)).toBeInTheDocument();
    expect(screen.getByText(/Passe Anual Fundador/i)).toBeInTheDocument();
    expect(screen.getByAltText(/Sessão x Cessão x Seção/i)).toBeInTheDocument();
  });

  it('oculta curadoria no Sidebar no modo estudante e impede estudante comum de ver painel admin', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            authenticated: true,
            user: {
              id: 'stu-1',
              email: 'aluno@teste.com',
              name: 'Aluno Comprador',
              role: 'student',
              plan: 'pro',
              plan_status: 'active',
              created_at: '2026-11-17T00:00:00Z',
              updated_at: '2026-11-17T00:00:00Z',
            },
            has_admin: true,
            public_mode: true,
            require_auth: true,
            checkout_url: '',
            billing_configured: true,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    renderWithClient(
      <>
        <Sidebar
          collapsed={false}
          onToggle={() => {}}
          onNavigate={() => {}}
          mobileOpen={false}
          onCloseMobile={() => {}}
        />
        <AccountPage />
      </>,
    );

    expect(await screen.findByText(/Olá, Aluno Comprador/i)).toBeInTheDocument();
    expect(screen.getByText('Aulas & Teoria')).toBeInTheDocument();
    expect(screen.getByText('Planos & Acesso Pro')).toBeInTheDocument();
    expect(screen.queryByText('Mesa de Validação')).not.toBeInTheDocument();
    expect(screen.queryByText(/Modo Admin & Curadoria/i)).not.toBeInTheDocument();
  });

  it('permite administrador alternar entre Modo Estudante e Modo Admin no mesmo navegador', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/auth/me')) {
          return new Response(
            JSON.stringify({
              authenticated: true,
              user: {
                id: 'adm-1',
                email: 'fundador@gsn.com',
                name: 'Gabriel Fundador',
                role: 'admin',
                plan: 'founder',
                plan_status: 'active',
                created_at: '2026-11-17T00:00:00Z',
                updated_at: '2026-11-17T00:00:00Z',
              },
              has_admin: true,
              public_mode: false,
              require_auth: false,
              checkout_url: '',
              billing_configured: false,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderWithClient(
      <>
        <Sidebar
          collapsed={false}
          onToggle={() => {}}
          onNavigate={() => {}}
          mobileOpen={false}
          onCloseMobile={() => {}}
        />
        <AccountPage />
      </>,
    );

    const adminToggle = await screen.findByRole('button', { name: /Modo Admin & Curadoria/i });
    expect(screen.queryByText('Mesa de Validação')).not.toBeInTheDocument();

    fireEvent.click(adminToggle);

    expect(await screen.findByText('Mesa de Validação')).toBeInTheDocument();
    expect(screen.getByText(/Clientes & Alunos Cadastrados/i)).toBeInTheDocument();
  });
});

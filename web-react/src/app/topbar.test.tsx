import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { ThemeToggle, Topbar } from './topbar';

function renderTopbar() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter([
    {
      path: '/',
      element: <Topbar onOpenMobile={() => {}} onOpenPalette={() => {}} />,
    },
  ]);
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe('Topbar & ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = 'dark';
    document.documentElement.setAttribute('data-theme', 'dark');
  });

  it('renderiza o botao lua e sol e alterna entre tema escuro e claro ao clicar', () => {
    renderTopbar();

    const toggleBtn = screen.getByRole('button', { name: /Alternar para tema claro/i });
    expect(toggleBtn).toBeInTheDocument();

    // Clica para mudar para o tema claro (white theme)
    fireEvent.click(toggleBtn);

    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('radar_theme')).toBe('light');

    // Clica novamente para voltar para o tema escuro
    fireEvent.click(toggleBtn);

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('radar_theme')).toBe('dark');
  });

  it('renderiza ThemeToggle isoladamente', () => {
    render(<ThemeToggle />);
    const toggleBtn = screen.getByRole('button', { name: /Alternar para tema claro/i });
    expect(toggleBtn).toBeInTheDocument();
  });
});

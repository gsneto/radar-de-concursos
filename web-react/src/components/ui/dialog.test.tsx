import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ModalDialog } from './dialog';

describe('ModalDialog', () => {
  it('renderiza diálogo acessível com título e fecha com Escape', () => {
    const onOpenChange = vi.fn();
    render(
      <ModalDialog
        open
        onOpenChange={onOpenChange}
        title="Visualizar Ficha"
        description="Detalhe em alta resolução"
      >
        <button type="button">Ação interna</button>
      </ModalDialog>,
    );
    expect(screen.getByRole('dialog', { name: 'Visualizar Ficha' })).toBeInTheDocument();
    expect(screen.getByText('Ação interna')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GlowCard } from './glow-card';

describe('GlowCard', () => {
  it('atualiza --glow-x e --glow-y no DOM ao mover o mouse sem re-renderizar filhos', () => {
    let renders = 0;
    function Child() {
      renders += 1;
      return <span>Conteúdo interno</span>;
    }

    const { container } = render(
      <GlowCard contentClassName="p-4">
        <Child />
      </GlowCard>,
    );
    expect(screen.getByText('Conteúdo interno')).toBeInTheDocument();
    const initialRenders = renders;

    const root = container.firstElementChild as HTMLElement;
    fireEvent.mouseMove(root, { clientX: 120, clientY: 80 });
    expect(root.style.getPropertyValue('--glow-x')).toBe('120px');
    expect(root.style.getPropertyValue('--glow-y')).toBe('80px');
    expect(renders).toBe(initialRenders);
  });
});

import { NavLink } from 'react-router-dom';
import { PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { navGroups } from '@/app/nav';
import { RadarMark } from './radar-mark';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onNavigate: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({
  collapsed,
  onToggle,
  onNavigate,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  return (
    <aside
      id="sidebar"
      aria-label="Navegação principal"
      className={cn(
        'fixed inset-y-0 left-0 z-50 flex w-[244px] flex-col border-r border-line bg-surface',
        'transition-[width,transform] duration-300 ease-out',
        collapsed ? 'lg:w-[72px]' : 'lg:w-[244px]',
        mobileOpen ? 'translate-x-0 shadow-float' : '-translate-x-full lg:translate-x-0',
      )}
    >
      <div
        className={cn(
          'flex h-[60px] shrink-0 items-center gap-2 border-b border-line px-3',
          collapsed && 'lg:justify-center lg:px-0',
        )}
      >
        <NavLink
          to="/"
          onClick={onNavigate}
          className="flex min-w-0 items-center gap-2.5 rounded-xs outline-offset-4"
          aria-label="GSN Concursos — início"
        >
          <RadarMark size={30} />
          <span className={cn('min-w-0 leading-none', collapsed && 'lg:hidden')}>
            <span className="block font-display text-[13px] font-semibold tracking-[-0.01em] text-fg">
              GSN
            </span>
            <span className="mt-0.5 block text-[9px] font-medium tracking-[0.16em] text-fg-3 uppercase">
              Concursos
            </span>
          </span>
        </NavLink>

        <button
          type="button"
          onClick={onToggle}
          className={cn(
            'ml-auto hidden size-7 place-items-center rounded-xs text-fg-3 transition-colors hover:bg-white/[0.06] hover:text-fg lg:grid',
            collapsed && 'lg:hidden',
          )}
          aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
          aria-expanded={!collapsed}
          aria-controls="sidebar"
          title={collapsed ? 'Expandir menu' : 'Recolher menu'}
        >
          <PanelLeftClose size={16} />
        </button>

        <button
          type="button"
          onClick={onCloseMobile}
          className="ml-auto grid size-8 place-items-center rounded-xs text-fg-3 hover:bg-white/[0.06] hover:text-fg lg:hidden"
          aria-label="Fechar menu"
        >
          <X size={17} />
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto overflow-x-hidden px-2 py-3">
        {navGroups.map((group) => (
          <div key={group.label} className="mb-4 last:mb-0">
            <p
              className={cn(
                'mb-1 px-2 text-[9px] font-semibold tracking-[0.14em] text-fg-3/70 uppercase',
                collapsed && 'lg:hidden',
              )}
            >
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      onClick={onNavigate}
                      title={collapsed ? item.label : undefined}
                      className={({ isActive }) =>
                        cn(
                          'group relative flex h-9 items-center gap-2.5 rounded-sm px-2 text-[13px] transition-colors',
                          'text-fg-2 hover:bg-white/[0.055] hover:text-fg',
                          collapsed && 'lg:justify-center lg:px-0',
                          isActive &&
                            'bg-accent-soft text-fg before:absolute before:top-2 before:-left-2 before:bottom-2 before:w-[2px] before:rounded-r before:bg-accent',
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <Icon
                            size={16}
                            strokeWidth={1.8}
                            className={cn('shrink-0', isActive ? 'text-accent' : 'text-fg-3')}
                          />
                          <span className={cn('truncate', collapsed && 'lg:hidden')}>
                            {item.label}
                          </span>
                        </>
                      )}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-line p-2">
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            'hidden h-8 w-full items-center gap-2 rounded-sm px-2 text-[11px] text-fg-3 transition-colors hover:bg-white/[0.06] hover:text-fg lg:flex',
            collapsed && 'lg:justify-center lg:px-0',
          )}
          aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
        >
          {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          <span className={cn(collapsed && 'lg:hidden')}>Recolher</span>
        </button>
        <p
          className={cn(
            'mt-1 flex items-center gap-1.5 px-2 py-1 text-[10px] text-fg-3/80',
            collapsed && 'lg:justify-center lg:px-0',
          )}
        >
          <span className="size-1.5 shrink-0 rounded-full bg-ok" aria-hidden />
          <span className={cn('truncate', collapsed && 'lg:hidden')}>Dados locais · sem conta</span>
        </p>
      </div>
    </aside>
  );
}

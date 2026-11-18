import { useEffect, useState } from 'react';

export type WorkspaceMode = 'student' | 'admin';

export interface AppUser {
  id: string;
  email: string;
  name: string;
  role: 'student' | 'admin';
  plan: 'free' | 'pro' | 'founder';
  plan_status: 'active' | 'trial' | 'past_due' | 'canceled';
  created_at: string;
  updated_at: string;
}

export interface AuthMeResponse {
  authenticated: boolean;
  user: AppUser | null;
  has_admin: boolean;
  public_mode: boolean;
  require_auth: boolean;
  checkout_url: string;
  billing_configured: boolean;
}

export interface BillingEventItem {
  id: string;
  provider: string;
  email: string;
  plan: string;
  event_type: string;
  created_at: string;
}

const MODE_KEY = 'gsn.workspace_mode';
const MODE_EVENT = 'gsn:workspace-mode';

export function readWorkspaceMode(): WorkspaceMode {
  try {
    return localStorage.getItem(MODE_KEY) === 'admin' ? 'admin' : 'student';
  } catch {
    return 'student';
  }
}

export function setWorkspaceMode(mode: WorkspaceMode): void {
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch {
    /* ignore storage failures */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent<WorkspaceMode>(MODE_EVENT, { detail: mode }));
  }
}

export function useWorkspaceMode(userRole?: string): [WorkspaceMode, (next: WorkspaceMode) => void] {
  const [mode, setModeState] = useState<WorkspaceMode>(readWorkspaceMode);

  useEffect(() => {
    const onChange = (event: Event) => {
      const detail = (event as CustomEvent<WorkspaceMode>).detail;
      setModeState(detail === 'admin' ? 'admin' : 'student');
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === MODE_KEY) {
        setModeState(readWorkspaceMode());
      }
    };
    window.addEventListener(MODE_EVENT, onChange);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(MODE_EVENT, onChange);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  // Alunos comuns nunca podem ficar presos no modo Admin
  const effectiveMode: WorkspaceMode = userRole === 'student' ? 'student' : mode;
  return [effectiveMode, setWorkspaceMode];
}

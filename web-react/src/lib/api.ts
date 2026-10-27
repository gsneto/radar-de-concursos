/**
 * Client HTTP único. Nenhum fetch fora daqui.
 * Respeita as proteções do backend: JSON, same-origin, sem CORS.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status = 0, code = 'erro_api') {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }

  /** 4xx é erro de contrato: repetir não resolve. */
  get retryable(): boolean {
    return this.status === 0 || this.status >= 500 || this.status === 429;
  }
}

const DEFAULT_TIMEOUT = 20_000;

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeout = DEFAULT_TIMEOUT,
): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      ...init,
      cache: 'no-store',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    });

    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        throw new ApiError('Resposta inválida do servidor local.', response.status, 'json_invalido');
      }
    }

    if (!response.ok) {
      const message =
        payload && typeof payload === 'object' && 'error' in payload
          ? String((payload as { error: unknown }).error)
          : `Falha na consulta (${response.status}).`;
      throw new ApiError(message, response.status, `http_${response.status}`);
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('A consulta demorou demais para responder.', 0, 'timeout');
    }
    throw new ApiError('Não foi possível falar com o servidor local.', 0, 'rede');
  } finally {
    window.clearTimeout(timer);
  }
}

export const api = {
  get<T>(path: string, signal?: AbortSignal): Promise<T> {
    return request<T>(path, { method: 'GET', signal });
  },
  post<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, { method: 'POST', body: JSON.stringify(body) });
  },
  del<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' });
  },
};

/** Monta query string ignorando valores vazios. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '' || value === false) continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

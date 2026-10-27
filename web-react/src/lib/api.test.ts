import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api, qs } from './api';

function respond(status: number, body: string) {
  return vi.fn().mockResolvedValue(new Response(body, { status }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('api client', () => {
  it('devolve o JSON em sucesso, sem cache', async () => {
    const fetchMock = respond(200, '{"ok":true}');
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.get('/api/saude')).resolves.toEqual({ ok: true });
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'GET', cache: 'no-store' });
  });

  it('POST envia JSON com Content-Type', async () => {
    const fetchMock = respond(200, '{}');
    vi.stubGlobal('fetch', fetchMock);

    await api.post('/api/estudos/disciplinas', { nome: 'Português' });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe('{"nome":"Português"}');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('erro HTTP usa a mensagem do backend e não é repetível em 4xx', async () => {
    vi.stubGlobal('fetch', respond(400, '{"error":"parametro invalido"}'));

    const error = await api.get('/api/x').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe('parametro invalido');
    expect((error as ApiError).status).toBe(400);
    expect((error as ApiError).code).toBe('http_400');
    expect((error as ApiError).retryable).toBe(false);
  });

  it('404 sem corpo gera mensagem genérica com o status', async () => {
    vi.stubGlobal('fetch', respond(404, ''));

    const error = (await api.get('/api/x').catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(404);
    expect(error.message).toContain('404');
  });

  it('5xx e 429 são repetíveis', () => {
    expect(new ApiError('x', 503).retryable).toBe(true);
    expect(new ApiError('x', 429).retryable).toBe(true);
    expect(new ApiError('x', 0).retryable).toBe(true);
  });

  it('corpo que não é JSON vira json_invalido', async () => {
    vi.stubGlobal('fetch', respond(200, '<html>'));

    const error = (await api.get('/api/x').catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe('json_invalido');
  });

  it('falha de rede vira erro de rede repetível', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    const error = (await api.get('/api/x').catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe('rede');
    expect(error.status).toBe(0);
    expect(error.retryable).toBe(true);
  });

  it('aborto vira timeout', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')),
    );

    const error = (await api.get('/api/x').catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe('timeout');
  });

  it('dispara o abort quando o servidor não responde no prazo', async () => {
    vi.useFakeTimers();
    let captured: AbortSignal | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => {
        captured = init.signal ?? undefined;
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          );
        });
      }),
    );

    const pending = api.get('/api/lento').catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(20_000);
    const error = (await pending) as ApiError;
    expect(captured?.aborted).toBe(true);
    expect(error.code).toBe('timeout');
  });
});

describe('qs', () => {
  it('ignora vazios e false; mantém zero', () => {
    expect(qs({ a: 1, b: '', c: null, d: undefined, e: false, f: 0 })).toBe('?a=1&f=0');
  });

  it('sem parâmetros não gera ?', () => {
    expect(qs({})).toBe('');
  });
});

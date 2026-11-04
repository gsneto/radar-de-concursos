# Execução e implantação local

O Radar é uma aplicação **local, de usuário único, em loopback** (`127.0.0.1`). Não há
autenticação nem rate-limit de rede: o servidor recusa `Host`/`Origin` fora de loopback
(anti DNS-rebinding/CSRF). **Não exponha a porta na rede** sem um proxy com autenticação.

## Requisitos

- Windows (notificações nativas e Agendador de Tarefas); Python 3.11+ (CI usa 3.11).
- Node 24 + npm, somente para desenvolver/rebuildar o frontend.
- `requirements.txt` (`pypdf`, `pymupdf` opcional para OCR). Tesseract é opcional.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
New-Item -ItemType Directory -Path .\data -Force
Copy-Item radar_ops.json.example radar_ops.json   # ajuste fontes/notificações/preferências
python -m radar documents-migrate --db .\data\radar.sqlite3
python -m radar collect --db .\data\radar.sqlite3
```

`data/`, `logs/` e `radar_ops.json` não são versionados.

## Servir a interface (produção local)

O servidor entrega o build versionado em `web-react/dist` (com fallback SPA):

```powershell
python -m radar serve --db .\data\radar.sqlite3 --port 8000   # ou serve-dev.bat
```

Abra `http://127.0.0.1:8000/`. Verificação: `python -m radar prontidao --db .\data\radar.sqlite3`
e `GET /api/saude`.

## Desenvolvimento do frontend

```powershell
cd web-react
npm ci
npm run dev        # http://localhost:5173, proxy /api -> 127.0.0.1:8000
npm test           # vitest
npm run build      # gera web-react/dist (COMMITAR o resultado)
```

O CI falha se `web-react/dist` estiver desatualizado; rebuilde no **Windows** antes do commit.

## Modelo de Ameaça e Hardening do Servidor Local (`radar/server.py`)

O servidor HTTP (`ThreadingHTTPServer` em `radar/server.py`) opera sob o modelo **single-user loopback (`127.0.0.1`)**. Como páginas web abertas no mesmo navegador podem tentar acessar `127.0.0.1` via DNS rebinding ou requisições cross-origin (CSRF), o servidor aplica as seguintes defesas verificadas por testes (`tests/test_backend_gate_f44.py` e `tests/test_coverage_consolidation_f47.py`):

1. **Bind exclusivo em loopback**: `create_server` faz bind em `127.0.0.1` por padrão; nunca expõe `0.0.0.0` sem configuração explícita.
2. **Proteção anti-DNS Rebinding (`_host_allowed`)**: todas as requisições (`GET`, `POST`, `DELETE`) exigem cabeçalho `Host` em `{"127.0.0.1", "localhost", "::1"}` exatamente na porta do servidor. Qualquer outro `Host` recebe `403 Forbidden` (`{"error":"host nao autorizado"}`).
3. **Proteção anti-CSRF local (`_origin_allowed` + `_guard_write`)**:
   - Métodos de escrita (`POST`/`DELETE`) com cabeçalho `Origin` exigem origem loopback na mesma porta (`http://127.0.0.1:<port>` ou `http://localhost:<port>`); origens externas recebem `403 Forbidden` (`{"error":"origem nao autorizada"}`).
   - Qualquer escrita com corpo exige `Content-Type: application/json`; outros tipos (`text/plain`, `application/x-www-form-urlencoded`, `multipart/form-data` simples de navegador) são drenados e recusados com `415 Unsupported Media Type`.
4. **Limites de tamanho de corpo e drenagem segura (`_read_json`, `_decode_base64`, `_drain`)**:
   - Payloads JSON comuns têm teto padrão de `8 KiB` (`4 KiB` para preferências/alertas);
   - Importações de pacotes/documentos têm tetos estritos validados antes da decodificação base64 e proteção contra Zip-Slip / zip bomb (`radar/packages.py`);
   - Corpos rejeitados são drenados até um teto seguro (`64 MiB`) para evitar reset de socket sem esgotar memória.
5. **Bloqueio de Path Traversal (`_serve_file`)**: caminhos de arquivos estáticos (`web-react/dist`) são resolvidos via `Path.resolve()` e conferidos contra `DIST_DIR.resolve()` antes da leitura. Rotas `/api/*` desconhecidas sempre retornam `404` (nunca caem no fallback SPA).
6. **Cabeçalhos de segurança e controle de cache**:
   - `X-Content-Type-Options: nosniff` em todas as respostas (incluindo mídia de flashcards, que valida assinatura mágica binária PNG/JPEG/GIF/WebP e recusa SVG);
   - `Cache-Control: no-store` em todas as respostas `application/json`;
   - Redação de caminhos absolutos do sistema de arquivos em `GET /api/saude/prontidao` (`_public_readiness`).
7. **Limitação de concorrência em consultas pesadas (`_EXPENSIVE_PATHS`)**: rotas que varrem grandes volumes (`/api/carteira/dossie`, `/api/revisao/grupos`, `/api/saude/prontidao`, `/api/quadro-vagas`, `/api/pipeline/parciais`, `/api/revisao/piloto`) são protegidas por `BoundedSemaphore(2)` com timeout de 5 s, retornando `429 Too Many Requests` em caso de saturação.

## Operação contínua

Scripts em `scripts/`: `install_tasks.ps1` / `uninstall_tasks.ps1` / `verify_tasks.ps1`
(Agendador de Tarefas), `run_cycle.ps1` (um ciclo de monitoramento), `serve.ps1`, `notify.ps1`.
Certifique-se de que o campo `"python"` em `radar_ops.json` aponte para `.\.venv\Scripts\python.exe` (ou fique vazio para detecção automática da `.venv` por `install_tasks.ps1` e `run_cycle.ps1`).
Detalhes em `docs/MONITORING_SCHEDULING.md`.

## Backup e restauração

- Banco: copie `data\radar.sqlite3` com o servidor parado (ou use a API de backup).
- Estudos: `python -m radar estudos-backup` / `estudos-exportar` / `estudos-importar`.
- Revisões: `revisao-exportar` / `revisao-importar`.

## Testes e CI

```powershell
python -m unittest discover -s tests -t .
cd web-react; npx tsc -b; npm test; npm run build
```

`.github/workflows/ci.yml`: job `python` (Windows: unittest + checagem do `dist`) e job
`web-react` (Ubuntu: tsc, vitest, build). Testes que dependem de `data/` se pulam sozinhos.

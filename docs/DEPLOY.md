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

## Operação contínua

Scripts em `scripts/`: `install_tasks.ps1` / `uninstall_tasks.ps1` / `verify_tasks.ps1`
(Agendador de Tarefas), `run_cycle.ps1` (um ciclo de monitoramento), `serve.ps1`, `notify.ps1`.
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

# Primeira fonte do Radar Implementation Plan

> **For agentic workers:** use test-driven-development; nenhum commit nesta tarefa por instrução explícita do usuário.

**Goal:** percorrer uma página oficial de Guajará-Mirim até API SQLite e interface navegável.

**Architecture:** Python stdlib com conector isolado, repositório SQLite, HTTP loopback e arquivos web locais. A integração se dá pelo contrato da spec.

**Tech Stack:** Python 3 stdlib, sqlite3, unittest, HTML/CSS/JS.

**Spec:** `docs/superpowers/specs/2026-10-09-primeira-fonte-radar-design.md`

## Global Constraints

- Uma fonte oficial; sem Jev, commits, publicação, migração destrutiva ou dependências adicionais.
- `null` para informação desconhecida; não somar modalidades, não transformar vagas de reserva em imediatas ou locais de prova em exercício.
- Falha de coleta não atualiza banco nem marca dados antigos como verificados.

## Review Focus

- Página oficial muda lista ou ordem: parser deve rejeitar estrutura inesperada em vez de gravar parcial.
- Fonte retorna HTTP inválido/timeout: dados persistidos continuam íntegros e horário não avança.
- HTML/JSON contém texto hostil: UI deve usar APIs textuais e link HTTPS validado, sem interpretação HTML.
- Duas coletas iguais: quatro registros, não oito; atualização muda somente as mesmas chaves.
- Número zero explícito vs campo ausente: testes distinguem `0` de `null` e mantêm local de prova/exercício separados.

---

### Task 1: Coleta da página oficial

**Files:** `radar/collector.py`, `radar/__init__.py`, `tests/fixtures/guajara-oficial.html`, `tests/test_collector.py`.

**Interfaces:** `collect(source_html: str, verified_at: str) -> list[dict]` e `fetch_official() -> str`; constantes `SOURCE_URL` e `SOURCE_NAME`. Parser valida título, ID, quatro cargos/contagens e data publicada; falha com `ValueError` em documento incompleto. Fetch HTTPS com timeout, tamanho limitado, host fixo e resposta decodificada; nunca finge sucesso offline.

- [ ] Criar testes antes do código: fixture fiel com quatro cargos (69/32/3/3), `None` para reservas/cota/local/escolaridade, distinção zero em variante sintética, HTML incompleto rejeitado, falha HTTP simulada.
- [ ] Executar `python -m unittest tests.test_collector -v` e observar falha por ausência da implementação.
- [ ] Implementar o mínimo em `radar/collector.py` e rodar testes novamente; conferir suíte global ao encerrar.

### Task 2: Persistência e API

**Files:** `radar/storage.py`, `radar/server.py`, `tests/test_storage.py`, `tests/test_server.py`.

**Interfaces:** `upsert_records(db_path, records)` e `list_records(db_path) -> list[dict]`; `create_server(db_path, host='127.0.0.1', port=8000)` retorna servidor HTTP com GET `/api/concursos`, `/` e assets web. Comando CLI separado em `radar/__main__.py` após ambos módulos prontos; `python -m radar collect --db PATH`, `python -m radar serve --db PATH`.

- [ ] Criar testes de idempotência/atualização/rollback, JSON em vazio e registros, rota estática e métodos/paths não conhecidos; executar RED.
- [ ] Implementar SQLite transacional com PK `(source_url, competition_id, role)` e API loopback; executar GREEN e suíte global.

### Task 3: Interface

**Files:** `web/index.html`, `web/styles.css`, `web/app.js`, `tests/test_ui.py` (teste independente pelo HTML servido e análise funcional no navegador).

**Interfaces:** consome GET `/api/concursos` e campos exatamente como na spec; `null` significa desconhecido.

- [ ] Criar teste RED para estados/carregamento/vazio/erro, domínio e fontes em HTML/JS; observar falha.
- [ ] Criar layout responsivo e acessível com contraste/foco, informações oficiais e horário; não renderizar dados arbitrários com `innerHTML`; executar GREEN.

### Task 4: QA e integração

**Files:** `tests/test_contract.py`, `README.md`, `.gitignore` (apenas se necessário), correções nos módulos donos após achados.

- [ ] QA independente escreve casos de contrato e integração sobre fixture e banco temporário; cobre zero/desconhecido, prova/exercício, falha, repetição, HTML incompleto; executa suíte.
- [ ] Orquestrador executa coleta oficial manual, repete, inicia API local, testa JSON/HTML em navegador, simula vazio/erro e confere `git status`, arquivos e testes.
- [ ] Documentar instruções de execução e limites de atualidade da fonte; relatar apenas resultados comprovados.

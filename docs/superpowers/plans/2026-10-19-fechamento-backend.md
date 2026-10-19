# Plano — fechamento integral do backend (Fase 44)

Base: `b2fddc2`. Branch: `radar-configuracao`. Schema: v21 (sem migração).

## 1. Estado inicial verificado

- [x] Diretório, branch, HEAD e remoto confirmados; árvore limpa e sincronizada.
- [x] Nenhum commit posterior a `b2fddc2`.
- [x] Suíte inicial: **1.877 testes, OK** (1 ignorado).
- [x] Backup consistente por API: `data/radar.sqlite3.bak-20261019-072446`.
- [x] `integrity_check` = `ok`; `foreign_key_check` = 0.
- [x] Snapshot: 1.276 documentos, 1.110 versões, 17.515 blocos, 9.340 propostas,
      9.340 evidências, 0 revisões/valores/reconciliações/lotes, 635 certames,
      125 identidades de cargo, 12 ciclos, 44 ciclos-fonte.
- [x] Banco cresceu em relação à referência (1.232/1.072/9.211): o ciclo agendado
      continuou ativo durante a fase; nenhum número foi presumido.

## 2. Inventário

- [x] 92 módulos, 83 arquivos de teste, 45 tabelas, 129 entradas método+rota.
- [x] Matriz por domínio em `docs/BACKEND_INVENTORY.md`.
- [x] Lacunas classificadas: P0 (CSRF local), P1 (contrato, prontidão, estado de
      extração, configuração de fontes, desempenho, idempotência de sessão), P2
      (OpenAPI, WAL, pool/timeout, histórico antigo, cobertura universal).

## 3. Correções

### P0 — segurança de escrita local
- [x] `Origin` loopback na mesma porta; `Content-Type: application/json` quando há corpo.
- [x] `Host` loopback na mesma porta (anti DNS rebinding).
- [x] `nosniff` e `no-store` em JSON.
- [x] Testes de 403/415/200/headers.

### P1 — contrato de API
- [x] `radar/api_contract.py` com 129 entradas método+rota e 24 domínios.
- [x] `verify()` por método+rota, com marcadores para rotas declaradas por sufixo.
- [x] `docs/API.md` gerado; CLI `api-contrato [--markdown|--verificar]`.
- [x] Contrato v1 de `GET /api/concursos` preservado (teste existente).

### P1 — prontidão
- [x] `radar/readiness.py` com checks bloqueantes e pendências.
- [x] `GET /api/saude/prontidao` e CLI `prontidao`.
- [x] Cache de 60 s + single-flight; HTTP redige caminho absoluto.
- [x] Schema pendente/banco vazio retornam `bloqueado` sem traceback.

### P1 — estados de extração
- [x] `concluida` vs `parcial` vs `falhou`.
- [x] `partial` explícito em `record_analysis`/`append_page_analysis`.
- [x] Lote final conclui a versão; lote sem texto também fecha.
- [x] `_note_is_partial` tolera JSON não-objeto.
- [x] 3 testes antigos ajustados para o estado correto.

### P1 — configuração de fontes
- [x] `budget.state_report(config=...)` reflete `sources.<chave>.enabled`.
- [x] `/api/fontes` e prontidão passam a configuração (inclusive `config_path`).

### P1 — desempenho
- [x] Pré-agrupamento por concurso em `decisive_fields`.
- [x] Varredura `bulk` em `opportunities`.
- [x] Cache com fingerprint em carteira e quadro de vagas.
- [x] Chave por hora local; paginação preservada acima de 5.000.
- [x] Limite de 2 GETs pesados concorrentes (429).

### P1 — estudos
- [x] Conclusão de sessão idempotente por id.
- [x] Fluxo ponta a ponta validado: disciplina, tópico, sessão, flashcard, questão,
      tentativa, simulado, resposta, finalização repetida, desempenho, exportação,
      importação dry-run.

## 4. Testes

- [x] Novos: `tests/test_backend_gate_f44.py` (29 testes).
- [x] Suíte final: **1.906 testes, OK** (1 ignorado).
- [x] Sem dependência de internet na suíte comum.
- [x] Contrato por método, prontidão com config, banco vazio, ciclo parcial, estudos
      ausente, cache na virada de data local, último lote, note não-objeto, Host.

## 5. Revisão independente

- [x] `code-reviewer`: 0 crítico; 4 altos (contrato cego a método, prontidão ignorando
      config, prontidão quebrando em schema pendente, cache com data UTC) e 4 médios;
      todos corrigidos.
- [x] `security-reviewer`: 0 crítico/alto; 2 médios (Host/DNS rebinding e concorrência de
      GETs pesados) corrigidos; baixos documentados.

## 6. Entrega

- [x] `docs/BACKEND_INVENTORY.md`
- [x] `docs/READINESS_GATE.md`
- [x] `docs/API.md`
- [x] `docs/superpowers/specs/2026-10-19-fechamento-backend-design.md`
- [x] `docs/superpowers/plans/2026-10-19-fechamento-backend-prova-real.md`
- [x] `docs/AUTONOMOUS_WORK_LOG.md` atualizado
- [x] Commit e push em `radar-configuracao`

# Plano — Fase 29: catálogo de fontes, políticas e aquisição multicanal

## Task 1 — Auditoria
- [x] Branch `radar-configuracao`, HEAD `add272a`, árvore limpa, sincronizada.
- [x] Suíte de linha de base: **1255 testes, OK** (execução real).
- [x] Base v16: 635 concursos, 789 documentos, 3608 propostas, 10 associações pendentes,
      0 revisões, 0 valores vigentes; backup com `integrity_check`.
- [x] `radar_ops.json` e tarefa agendada inspecionados (sem alteração).

## Task 2 — Pesquisa real
- [x] DOU, FGV, Quadrix, IBFC, PCI: situação e robots verificados.
- [x] ConcursosNoBrasil, Ache Concursos, JC Concursos: robots verificados; termos não
      verificados ⇒ persistência não verificada/transitória.
- [x] Qconcursos e Questões de Concursos: robots 403 ⇒ bloqueadas.
- [x] 4 repositórios de concursos (GitHub API): licenças e situação; 2 MIT com conteúdo de
      terceiro (não integrar), 1 sem licença (bloqueado), 1 inexistente (404).
- [x] Quest API: comercial, sem licença, código privado ⇒ bloqueada.
- [x] dados.gov.br e Conecta: API 401 / catálogo HTML ⇒ aguardando credencial/validação.
- [x] IBGE Localidades: API real 200, 5.570 municípios ⇒ integração escolhida.

## Task 3 — Catálogo e política
- [x] `radar/source_catalog.py`: 18 fontes, permissão por tipo de conteúdo, evidência
      obrigatória, decisão registrada para licença não declarada, validador.
- [x] `radar/source_policy.py`: porta única (`require_persist`), estado positivo, redação de
      conteúdo transitório, revisão append-only.
- [x] Política ligada ao caminho de escrita (`monitoring`): corpo não autorizado não é gravado
      nem baixado; metadados permanecem.

## Task 4 — Orçamento
- [x] `radar/budget.py`: limites por execução gravados e impostos atomicamente, custo pago
      exige verificação/autorização, intervalo mínimo, janela mensal, checkpoint e consumo.
- [x] Estado operacional preenchido pela execução (`fontes_estado`), sem segredos.

## Task 5 — Conectores
- [x] `radar/connectors.py`: interface, capacidades, política, normalização com procedência,
      guarda de persistência, registro dos 6 conectores existentes + IBGE.
- [x] `radar/ibge_source.py`: snapshot com TTL, limite após descompressão, redirect restrito,
      validação de local e de propostas sem alterar nada.

## Task 6 — API, CLI e UI
- [x] `GET /api/fontes`, `GET /api/fontes/<id>`, `GET /api/fontes-consumo`.
- [x] CLI `fontes`, `fontes-consumo`, `fontes-revisar`, `fontes-politica`, `localidades`.
- [x] Painel de fontes na UI, sem `innerHTML`.

## Task 7 — Prova real
- [x] Migração v18 com delta zero; integridade e FK ok.
- [x] Snapshot IBGE real (5.570 municípios) e validação de 43 propostas de local.
- [x] Achado real: `Taboão/SP` não é município (o correto é Taboão da Serra) — sinal para
      revisão humana, sem alteração automática.
- [x] Suíte final: **1333 testes, OK**.

## Task 8 — Revisão independente e publicação
- [x] Revisão: **0 críticos, 8 importantes, menores**; todos corrigidos com teste.
- [x] Documentação (design, pesquisa, plano, prova real), README e log.
- [ ] Commit e push.

# Plano — Fase 28: revisão humana, confirmação e recuperação documental

## Task 1 — Auditoria
- [x] Branch `radar-configuracao`, HEAD `9de3573`, árvore limpa, sincronizada.
- [x] Suíte de linha de base: **1185 testes, OK** (execução real).
- [x] Base real v15: 598 concursos (597 certames + 1 container), 703 documentos,
      2023 propostas, 10 associações pendentes, 0 revisões, 0 valores vigentes.
- [x] Diagnóstico: revisão só por CLI, sem fila/prioridade/lote; associações sem tela;
      48 anexos bloqueados sem estado por documento; sem exportação/importação validada.

## Task 2 — Schema v16 (aditivo)
- [x] `revisoes_campo`: `previous_decision`, `origin`, `value_json`, `evidence_sha256`.
- [x] Rebuild de `revisoes_campo` e `eventos_documentais` para estender `CHECK`
      (preservando linhas e recriando índices).
- [x] `lotes_revisao` (com `cursor`), `lote_revisao_itens`, `ingestoes_documentais`.
- [x] Migração idempotente; caminho rápido valida o esquema v16; teste v15→v16 real.

## Task 3 — Central de revisão
- [x] `radar/review.py`: fila priorizada/paginada, filtros, detalhe com evidência e conflitos.
- [x] Prioridade determinística com fatores nomeados e motivo por ponto.
- [x] Decisões append-only: validar, rejeitar, adiar, ambíguo, nova extração, reabrir, corrigir.
- [x] Correção cria proposta derivada com a evidência original; reusa derivada idêntica.
- [x] Idempotência de decisão e de seleção; seleção só com decisão validada mais recente.
- [x] Lotes persistidos com próximo/anterior/pausar/retomar/concluir; sem aprovação em massa.
- [x] Exportação com `evidence_sha256`; importação em duas fases e transação única.

## Task 4 — Associações
- [x] Painel de associações pendentes com evidência e ações confirmar/rejeitar/manter pendente.
- [x] Confirmar exige id do certame e justificativa; não valida campos (teste dedicado).
- [x] Rejeitar sem destino permitido (documento não pertence a certame identificado).
- [x] Nenhum candidato por semelhança de título/órgão/data.

## Task 5 — Documentos bloqueados e ingestão manual
- [x] Evento `download_bloqueado` idempotente por documento+motivo+host, com evidência.
- [x] Relatório por estado (`obtido`, `importado_manualmente`, `bloqueado`, `indisponivel`,
      `pendente_download`) com filtro.
- [x] Alternativas por igualdade exata de caminho **em host autorizado**, página de origem
      acessível, pesquisa humana e importação manual.
- [x] Ingestão manual: assinatura, limite, hash local, procedência, canal, estado de revisão.
- [x] `monitoring` registra o bloqueio no ciclo.

## Task 6 — API, CLI e UI
- [x] Rotas `/api/revisao/*` e `/api/documentos/bloqueados|importar`.
- [x] CLI `revisao-fila|decidir|selecionar|lote|exportar|importar`, `documentos-bloqueados|importar`.
- [x] Painéis de revisão, associações e bloqueados na UI (textContent, sem XSS).
- [x] Origem da decisão derivada da rota (`interface`/`cli`/`importacao`), não do cliente.

## Task 7 — Prova real
- [x] Backup consistente com `integrity_check` antes da migração.
- [x] Migração aplicada sem delta em nenhuma tabela histórica.
- [x] Backfill dos 48 bloqueios do IBFC (eventos, sem download).
- [x] Verificação em cópia isolada: decisão, lote, associação e ingestão manual pela UI.
- [x] Suíte final: **1255 testes, OK**.

## Task 8 — Revisão independente e publicação
- [x] Revisão independente: **1 crítico, 7 importantes, menores**; todos corrigidos com teste.
- [x] Documentação (design, pesquisa, plano, prova real), README e log.
- [ ] Commit e push.

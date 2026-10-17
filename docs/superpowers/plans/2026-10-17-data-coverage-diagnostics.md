# Plano — Fase 25: cobertura, diagnóstico de lacunas e enriquecimento

TDD; lógica pura testada isoladamente; leitura somente em cópia/base real; escrita sempre com
`dry_run` por padrão.

## Task 1 — Auditoria do estado real
- [x] Branch `radar-configuracao`, HEAD `a2dbcf6`, árvore limpa, sincronizada.
- [x] Suíte completa: **1004 testes, OK** (baseline confirmada por execução).
- [x] Schema v14, `integrity_check=ok`, caminho `data/radar.sqlite3`.
- [x] Medição do funil e das causas no banco real (somente leitura).

## Task 2 — Diagnóstico de cobertura
- [x] `radar/data_quality.py`: dimensões, estados, denominadores explícitos, funil, causas e
      recortes. Nenhum schema novo.
- [x] `classify_cause` com precedência fechada e `inconclusivo` quando não há prova.
- [x] `gaps`: fila determinística, critérios com peso declarado, ação e tipo de tarefa.

## Task 3 — Enriquecimento aditivo
- [x] `radar/enrichment.py`: identidades de cargo a partir do rótulo literal do edital.
- [x] `clean_label` remove só os sufixos que o pipeline acrescenta (travessão em e `- bloco N`).
- [x] `dry_run` padrão; idempotente; não reatribui, não valida, não apaga.
- [x] `unresolved_role_summary` distingue "tem identidade" de "tem decisão humana".

## Task 4 — API, CLI e interface
- [x] `GET /api/cobertura`, `GET /api/cobertura/resumo`, `GET /api/lacunas`,
      `POST /api/cobertura/papeis` (aditivos; contrato v1 intacto).
- [x] CLI `cobertura`, `lacunas`, `cobertura-papeis [--apply]`.
- [x] Painel **Cobertura e qualidade dos dados** + lista de lacunas; falha de API não vira zero.

## Task 5 — Testes
- [x] `tests/test_data_quality.py` (30): funil, denominadores, zero vs ausente, ambiguidade,
      conflito por campo, `rejeitado`, causa por ramo, fila, resumo.
- [x] `tests/test_enrichment.py` (20): limpeza de rótulo, dry-run, idempotência, escopo,
      não-reatribuição, reconciliação contabilizada.
- [x] `tests/test_coverage_api.py` (7): rotas, entradas inválidas, contrato v1 com 18 campos.
- [x] `tests/test_ui.py` ampliado.
- [x] Suíte completa: **1062 testes, OK**.

## Task 6 — Revisão independente
- [x] Revisão por subagente: **1 crítico, 11 importantes, 11 menores**.
- [x] Crítico corrigido: `cargos` não pode ser "confirmado" sem decisão humana.
- [x] Importantes corrigidos: denominador, conflito entre campos complementares, `rejeitado`,
      confirmação parcial, `apenas_agregador` x documento oficial, `clean_label` com hífen,
      resumo de reconciliação, prioridade de campo em concurso não pesquisado, UI zero, testes.

## Task 7 — Prova real e publicação
- [x] Prova em cópia da base e aplicação controlada do enriquecimento na base habitual,
      com backup consistente e `integrity_check`.
- [x] Documentação (design, pesquisa, plano, prova real), README e log.
- [ ] Commit e push para `radar-configuracao`.

# Plano — Fase 35: identidades de cargo, conflitos reais, prazos e destino nominal

Data: 2026-10-18. Base: `0489ce6` (Fase 34), 1.531 testes, schema v19.

## Etapas

1. **Auditoria de partida** — HEAD/branch/remoto limpos, suíte verde, backup consistente
   (`data/radar.sqlite3.bak-20261018-084417`, `integrity ok`, v19), contagens e snapshot
   temporal. Registrar que a tarefa agendada do ciclo pode mover a base entre leituras.
2. **Diagnóstico dos rótulos** — 246 rótulos / 28 concursos; natureza por marcador;
   identidades duplicadas; cargos por concurso; propostas por rótulo.
3. **Migração v20** — reconstruir `reconciliacoes_cargo` com `role_id` nullable, `state`,
   `nature`, `evidence_json`, `previous_id`; índice `idx_reconciliacoes_contest`; migração
   v19→v20 idempotente; `_READABLE_VERSIONS` sem v18 e sem v19.
4. **Identidades** (`radar/role_identity.py`)
   - `classify_label` (7 naturezas por marcador);
   - `_suggest` (pontuação estrutural, ≥25, top 5, empate → ambígua);
   - `label_inventory` (natureza, estado, evidência, ação proposta);
   - `decide_reconciliation` (estado, vínculo, evidência, `expected_previous_id`, dry-run);
   - `reconciliation_history` (vigente + anteriores);
   - `create_role_for_label` (só naturezas cargolike);
   - `reconciliation_queue` (utilidade = propostas × força da sugestão).
5. **Conflitos** (`radar/conflict_review.py`) — `classify_group` com 8 causas,
   `FIELD_PRIORITY` 1..4, retificação só altera quando sua própria proposta difere do edital
   de abertura, próxima ação por causa.
6. **Prazos** (`radar/deadline_review.py`) — 8 grupos, 5 estados temporais, somente
   documentos autoritativos, `sem_data` explícito, referência temporal injetável (`now`).
7. **Destino nominal** (`radar/nominal_destination.py`) — 4 destinos, modo simulação, sem
   download, sem copiar conteúdo.
8. **Integração na revisão** — `review._reconciled_map` só considera `confirmada`;
   `document_review.reconcile_role_label` grava `state='confirmada'`.
9. **Superfície** — API aditiva (`GET /api/reconciliacao`, `/historico`,
   `/api/conflitos-revisao`, `/api/prazos`, `/api/documentos/nominais-destino`,
   `POST /api/reconciliacao` com dry-run padrão); CLI (`reconciliacao`,
   `reconciliacao-historico`, `reconciliacao-decidir`, `reconciliacao-criar-cargo`,
   `conflitos-revisao`, `prazos`, `documentos-nominais-destino`); UI "Identidades, conflitos
   e prazos" com três filas, detalhe e painel de destino nominal.
10. **Testes** — `tests/test_role_identity_f35.py` (55), UI +1, correção de
    `test_enrichment` para as novas colunas; regressões dos dois defeitos encontrados na
    validação real.
11. **Prova real** — decisão em **cópia isolada** (base real permanece 0 decisões); medição
    de tempos; verificação de que nenhum destino nominal foi executado.
12. **Revisão independente**, correções, documentação, commit e push.

## Critérios de aceite

- Nenhuma identidade é confirmada, fundida ou criada sem decisão humana registrada.
- Sugestão nunca é exibida como certeza; empate vira ambiguidade.
- `POST /api/reconciliacao` grava somente com `dry_run: false`.
- Conflito traz causa, prioridade, motivos e próxima ação.
- Prazo traz estado temporal, documento, trecho, página, versão e próxima ação.
- Destino nominal é simulação explícita; nada é apagado/arquivado.
- Contrato `GET /api/concursos` v1 (18 campos) inalterado.
- Suíte completa verde; base real sem decisões fabricadas.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Fundir duplicatas e perder histórico | só sinaliza; consolidação é decisão humana |
| Sugestão errada parecer confirmação | pontuação estrutural + empate → ambígua + rótulo "não confirmado" |
| Decisão concorrente sobrescrever outra | `expected_previous_id` recusa |
| Retificação não mencionada alterar prazo | compara proposta da retificação com edital de abertura |
| Data futura ser lida como vigência | texto de limitação em API e UI |
| Cópia isolada mascarar bug na base real | validação lê a base real para diagnóstico e só escreve na cópia |
| Base mudar durante a fase (ciclo agendado) | snapshot com timestamp; números declarados como referência |

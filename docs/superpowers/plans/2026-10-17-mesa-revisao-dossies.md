# Plano — Fase 34: mesa de revisão, dossiês e decisões auditáveis

Data: 2026-10-17. Base: `1679159` (Fase 33), 1.481 testes, schema v18.

## Etapas

1. **Auditoria de partida** — HEAD/branch/remoto, suíte, backup consistente, integridade,
   contagens e snapshot temporal.
2. **Diagnóstico da fila** — propostas por estado, por campo, conflitos, evidência com página,
   documentos sem decisão, nominais.
3. **Migração v19** — `snapshot_sha256` e `scope_snapshot` em `lote_revisao_itens`
   (justificativa: sem isso não há como detectar mudança desde a abertura).
4. **Oportunidades** (`radar/opportunities.py`)
   - agrupamento por concurso × cargo (ou rótulo não reconciliado);
   - estado de campo honesto, incluindo `multiplo_por_cargo`;
   - prioridade reutilizada com motivos; próxima ação.
5. **Dossiê** — identidade, documentos, campos com evidência, lacunas, conflitos, prioritários.
6. **Evidência** — contexto antes/depois, origem, confiança estrutural, outras propostas,
   histórico.
7. **Sessão** — snapshot, `alterado`/`motivo_alteracao`, bloqueio de decisão sobre contexto
   alterado, progresso, pausa/retomada, restauração após recarregar.
8. **Nominais** (`radar/nominal_triage.py`) — triagem com política, estado e próxima ação, sem
   download e sem copiar conteúdo.
9. **Linha do tempo** (`radar/timeline.py`) — snapshot, ciclos, atribuição por janela, falhas.
10. **Superfície** — API aditiva (5 rotas), CLI (`oportunidades`, `oportunidade`, `evidencia`,
    `linha-do-tempo`, `documentos-nominais` com offset), painel com tabela compacta, dossiê,
    evidência, sessão, nominais e linha do tempo.
11. **Testes** — `tests/test_mesa_f34.py` (35) + UI; correção de `test_sources` para a versão.
12. **Prova real** — fluxo completo em **cópia isolada**; base real permanece sem decisões.
13. **Revisão independente**, correções, documentação, commit e push.

## Critérios de aceite

- Mesa funciona ponta a ponta: lista → dossiê → evidência → decisão em sessão.
- Nenhuma decisão criada por leitura; base real com 0 revisões.
- Item alterado bloqueia decisão e explica o motivo.
- Filtros e sessão sobrevivem a recarregar a página.
- Nominais sem download e sem conteúdo pessoal.
- Linha do tempo usa as tabelas do monitoramento.
- Suíte verde; contrato v1 intacto; integridade e FK ok.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Mesa lenta com 6 mil propostas | uma varredura por requisição (~0,4 s) + paginação de 25 |
| "Conflito" falso entre cargos | `multiplo_por_cargo` |
| Decidir sobre evidência que mudou | snapshot + conjunto de escopo + bloqueio |
| Sessão "presa" após reload | restauração por `localStorage` + estado no banco |
| Vazamento de dado pessoal na triagem | apenas metadados; conteúdo nunca copiado |
| Inflar cobertura/estado | estados derivados, sem contador próprio |

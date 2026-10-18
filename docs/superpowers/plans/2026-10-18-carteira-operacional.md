# Plano — Fase 36: carteira operacional, prazos atuais e revalidação

Data: 2026-10-18. Base: `1fe3741` (Fase 35), 1.587 testes, schema v20.

## Etapas

1. **Auditoria de partida** — diretório, branch, HEAD, remotes, sincronização, suíte
   completa, backup consistente via API de backup (WAL/conexões), `integrity_check`,
   `foreign_key_check`, snapshot com data/hora, inspeção dos serviços e da tarefa agendada.
2. **Diagnóstico temporal** — 110 prazos no estado atual; separar futuros, expirados,
   sem data e conflitos; identificar os que afetam candidatura.
3. **Calendário operacional** (`radar/deadline_calendar.py`) — 8 estados operacionais,
   urgência com fuso `America/Recife`, candidatos visíveis em conflito, alvos de revalidação.
4. **Revalidação** (`radar/deadline_revalidation.py`) — comparação de sha256 do documento
   oficial, política da fonte, redirecionamento restrito, `dry_run` sem rede, tabela
   append-only `revalidacoes_prazo`.
5. **Migração v21** — tabela + índice, idempotente, v20 legível.
6. **Carteira** (`radar/portfolio.py`) — prontidão determinística, prioridade explicada,
   lacunas, próxima ação, filtros, paginação, destaques com limite por concurso.
7. **Dossiê operacional** — identificação, vagas, formação, prazos, localização, conflitos,
   lacunas, próxima ação; reutiliza `opportunity_dossier`.
8. **Integridade semântica** — SI por cargo (sem herança), indígena com âmbito do concurso,
   local de prova separado de lotação, conflito sem valor único, pagamento declarado como
   não extraído.
9. **Superfície** — 7 rotas aditivas, 6 comandos CLI, seção "Carteira de oportunidades",
   prazos operacionais na UI, botão de revalidação real.
10. **Testes** — `tests/test_portfolio_f36.py` (49), cobrindo prazos, revalidação, prontidão,
    SI, indígena, local, dossiê multi-versão, paginação/filtros, ciclo, schema e API.
11. **Prova real** — revalidar os prazos futuros não conflitantes; medir; verificar UI em
    cópia isolada para decisões; base real sem decisões humanas.
12. **Revisão independente**, correções, documentação, commit e push.

## Critérios de aceite

- Nenhum prazo futuro é apresentado como inscrição aberta.
- Conflito não expõe valor único; todos os candidatos e evidências ficam visíveis.
- Prazo passado permanece, com situação temporal.
- Retificação que repete valor não é causa de mudança.
- Revalidação não grava conteúdo, não altera propostas e não confirma prazo.
- SI não é herdado entre cargos; indígena não é distribuído por cargo.
- Local de prova não é substituído por lotação.
- Nenhuma decisão/revisão/valor vigente é criado pela fase.
- Contrato `GET /api/concursos` v1 (18 campos) inalterado.
- Suíte completa verde; base íntegra; v21 idempotente.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Base muda durante a fase (ciclo 6 h) | snapshot com hora; números declarados como referência; revalidar depois da mudança |
| Revalidação virar coleta massiva | limite por execução, só URL conhecida, política da fonte |
| Documento mudar e a versão antiga ser usada | `fonte_alterada` registrado; nova versão é do ciclo |
| Conflito esconder prazo urgente | candidatos visíveis + estado `conflito_documental` + próxima ação |
| SI de um cargo contaminar outro | estado por cargo; agregado só no escopo do concurso, qualificado |
| Carteira virar lista infinita | destaques com no máximo 2 cargos por concurso |
| Revalidação gravar conteúdo | apenas hashes/status; teste com fetcher proibido em dry-run |

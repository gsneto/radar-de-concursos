# Plano — Fase 27: identidade canônica de certame e piloto oficial (IBFC)

## Task 1 — Auditoria
- [x] Branch `radar-configuracao`, HEAD `c7cb1a3`, árvore limpa, sincronizada.
- [x] Suíte de linha de base: **1120 testes, OK** (execução real).
- [x] Banco real: v14, 593 concursos, 636 documentos, 1887 propostas.
- [x] Caso do DOU comprovado: concurso `54568dbc…`, obs `DOU-S3`, 10 documentos de 10 órgãos,
      0 propostas.

## Task 2 — Schema v15 (aditivo)
- [x] `concursos_identidade.estado_identidade` (padrão `certame`).
- [x] `observacoes_concurso.tipo_identidade` (padrão `certame`).
- [x] Tabela `associacoes_documento` append-only + índices.
- [x] Migração aceita 0 e 2..14; idempotente; caminho rápido (já em v15) **também valida** o
      esquema, incluindo a tabela nova.
- [x] `_READABLE_VERSIONS` atualizado; teste de tabela v15 ausente.

## Task 3 — Identidade e reparação
- [x] `radar/identity.py`: `classify_external_id`, `containers`, `certame_ids`,
      `current_association`, `set_contest_state`, `set_observation_type`, `record_association`,
      `identity_audit`, `repair_plan`, `apply_repair`, `association_queue`.
- [x] `ensure_observation(..., tipo_identidade=)` cria container quando o id não é certame.
- [x] `register_document` grava associação `pendente` para documento em container.
- [x] `apply_repair` só age em `pendente`; decisão humana preservada.
- [x] Container recusado como alvo de associação.

## Task 4 — Exclusão de containers das métricas
- [x] `data_quality`, `priority`, `ops.health`, `list_competition_identities`, `association`.
- [x] Testes de exclusão (cobertura, prioridade, saúde, associação).

## Task 5 — Fonte oficial IBFC
- [x] `radar/ibfc_source.py`: catálogo `/index/{1|abertos|3}`, detalhe `/informacoes/{id}/`,
      identidade `ibfc-<id>`, anexos com `fetch_allowed`/`fetch_blocked_reason`.
- [x] CDN com `Disallow: /` nunca baixado; `downloads_bloqueados` no resumo do ciclo.
- [x] `monitoring.default_sources()` com IBFC e `download_new_only`.
- [x] `dou_source` declara `tipo_identidade: "secao_publicacao"`.
- [x] Testes (21), incluindo transporte stub, parcial, bloqueio de robôs e refresh.

## Task 6 — Bug latente de campos
- [x] `_FIELDS` com `exam_municipio`/`exam_uf`/`work_municipio`/`work_uf`.
- [x] Regressão `PersistenceTest` (versão inteira não aborta por local de prova).

## Task 7 — API e CLI
- [x] `GET /api/identidade`, `GET /api/associacoes/fila`, `POST /api/associacoes/<id>`,
      `POST /api/identidade/reparar`.
- [x] CLI `identidade`, `identidade-reparar`, `associacoes-fila`, `associacao-revisar`,
      `ibfc-piloto`.
- [x] Contrato v1: teste confere os **18 nomes** de campo.

## Task 8 — Prova real
- [x] Backup com `integrity_check` antes de qualquer escrita.
- [x] Reparação: dry-run, apply, reexecução idempotente (0 ações), contagens antes/depois.
- [x] Piloto IBFC: dry-run, apply, ciclo `concluido`, 48 downloads bloqueados por robôs.
- [x] Suíte final: **1185 testes, OK**.

## Task 9 — Revisão independente e publicação
- [x] Revisão: 1 crítico, 8 importantes, menores; todos os críticos/importantes corrigidos.
- [x] Documentação (design, pesquisa, plano, prova real), README e log.
- [ ] Commit e push.

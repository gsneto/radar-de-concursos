# Inventário do backend — fechamento para o frontend (Fase 44)

Referência: `radar-configuracao`, base `b2fddc2`, schema **v21**, 92 módulos em
`radar/`, 83 arquivos de teste, **129 entradas método+rota** (112 caminhos), 45 tabelas.
Data de referência: 2026-10-19. Números da base no fechamento: 1.276 documentos,
1.110 versões, 17.515 blocos, 9.340 propostas/evidências, 0 revisões, 0 valores vigentes,
0 reconciliações, 0 lotes.

Estados usados: **implementado e testado**; **implementado parcialmente**;
**implementado, não validado suficientemente**; **ausente**; **bloqueado externo**;
**melhoria futura (P2)**.

## 1. Coleta e catálogo de fontes

| Item | Conteúdo |
|---|---|
| Objetivo | Descobrir concursos/documentos, baixar apenas o autorizado, registrar proveniência e consumo. |
| Módulos | `source_catalog.py`, `source_policy.py`, `connectors.py`, `budget.py`, `acquisition.py`, `document_discovery.py`, `document_download.py`, `document_ingest.py`, `dou_source.py`, `fgv_source.py`, `quadrix_source.py`, `ibfc_source.py`, `pci_source.py`, `ibge_source.py`, `monitoring.py`. |
| Tabelas | `fontes_estado`, `fontes_consumo`, `fontes_revisoes`, `tentativas_download`, `ingestoes_documentais`, `documento_urls`, `ciclos_monitoramento`, `ciclos_fontes`, `localidades_ibge`. |
| API | `GET /api/fontes`, `GET /api/fontes/{id}`, `GET /api/fontes-consumo`, `GET /api/documentos/bloqueados`, `GET /api/documentos/nominais*`, `POST /api/documentos/importar`. |
| CLI | `fontes`, `fontes-consumo`, `fontes-revisar`, `fontes-politica`, `localidades`, `documentos-bloqueados`, `documentos-importar`, `ibfc-piloto`. |
| Estado | **Implementado e testado.** 18 fontes catalogadas, 5 habilitadas na configuração, 2 dependem de credencial/termos (`dados-gov-br`, `quest-api`), 4 bloqueadas por licença/robots, 3 aguardam validação de uso. |
| Testes | `test_sources.py`, `test_dou_source.py`, `test_fgv_source.py`, `test_quadrix_source.py`, `test_ibfc_source.py`, `test_pci_source.py`, `test_acquisition_f33.py`, `test_document_download.py`, `test_document_ingest.py`, `test_monitoring.py`. |
| Dependências | `pypdf`, `pymupdf` (contexto de tabela), rede para coleta; testes comuns não usam internet. |
| Limitações | Fontes sem permissão não persistem corpo; agregadores não comprovam campo decisivo; credenciais externas ausentes. |
| Correções nesta fase | `budget.state_report(config=...)` passou a refletir a habilitação real da configuração (antes a API mostrava todas as fontes desligadas). |
| Situação final | **Aprovado.** Integrações pendentes isoladas e documentadas; mecanismo de conector completo. |

## 2. Pipeline documental

| Item | Conteúdo |
|---|---|
| Objetivo | Fonte → descoberta → versão imutável → extração → blocos → propostas → evidência → derivados. |
| Módulos | `document_store.py`, `document_extract.py`, `document_fields.py`, `document_types.py`, `ocr.py`, `page_batches.py`, `pipeline.py`, `reprocess.py`, `table_continuity.py`, `vacancy_*`, `label_repair.py`. |
| Tabelas | `documentos`, `versoes_documento`, `blocos_documento`, `propostas_campo`, `evidencias`, `eventos_documentais`, `associacoes_documento`. |
| API | `GET /api/pipeline*`, `POST /api/documentos/reprocessar`, `POST /api/documentos/tipos`, `GET /api/quadro-vagas`. |
| CLI | `pipeline`, `pipeline-documentos`, `documentos-reprocessar`, `documentos-tipos`, `ocr-executar`, `documentos-lote`, `documentos-paginas`, `quadro-auditoria`, `quadro-vagas`. |
| Estado | **Implementado e testado.** SHA-256, versão imutável, evidência por página/bloco/offset, reprocessamento idempotente, OCR opcional, lotes com checkpoint, continuidade multipágina. |
| Testes | `test_document_extract.py`, `test_document_extract_pdf.py`, `test_document_extract_real.py`, `test_multipage.py`, `test_pipeline.py`, `test_reprocess.py`, `test_ocr_and_extraction.py`, `test_document_store.py`. |
| Limitações | 166 documentos descobertos sem versão; 5 versões sem texto (1 PDF ilegível, 4 sem camada de texto); 1.104 versões históricas marcadas `parcial` (prefixo de 40 páginas ou estado antigo); 733 sem nota de análise. |
| Correções nesta fase | `extraction_state` agora distingue `concluida`, `parcial` e `falhou`; lote final de páginas pode concluir a versão; `_note_is_partial` tolera JSON não-objeto; cache do quadro de vagas invalidado por versão/bloco/proposta. |
| Situação final | **Aprovado.** Incompletude é representada e retomável; nada é marcado como integral sem suporte. |

## 3. Modelo canônico

| Item | Conteúdo |
|---|---|
| Objetivo | Separar certame, publicação/container, órgão, banca, cargo, especialidade, código, regional, lotação, local de prova, documento, versão e retificação. |
| Módulos | `identity.py`, `role_identity.py`, `role_reconciliation.py`, `regional_scope.py`, `location.py`, `geography.py`, `document_types.py`, `association.py`. |
| Tabelas | `concursos_identidade`, `observacoes_concurso`, `cargos_identidade`, `observacoes_cargo`, `associacoes_documento`, `reconciliacoes_cargo`. |
| API | `GET /api/identidade`, `POST /api/identidade/reparar`, `GET /api/reconciliacao`, `GET /api/reconciliacao/historico`, `POST /api/reconciliacao`, `GET /api/associacoes*`. |
| CLI | `identidade`, `identidade-reparar`, `reconciliacao`, `reconciliacao-decidir`, `reconciliacao-criar-cargo`, `associacoes*`. |
| Estado | **Implementado e testado.** Container de fonte separado de certame; rótulo original, alias e nome normalizado preservados; sem fusão por similaridade. |
| Testes | `test_identity.py`, `test_identity_api.py`, `test_role_identity_f35.py`, `test_role_reconciliation.py`, `test_document_reconcile.py`, `test_association.py`, `test_geography.py`, `test_location.py`. |
| Limitações | 125 identidades de cargo; reconciliação depende de decisão humana registrada. |
| Situação final | **Aprovado.** |

## 4. Extração e regras de negócio

| Item | Conteúdo |
|---|---|
| Objetivo | Vagas/reservas, formação/elegibilidade, prazos e localização com estados explícitos. |
| Módulos | `document_fields.py`, `vacancy_tables.py`, `vacancy_columns.py`, `vacancy_inline.py`, `vacancy_aggregate.py`, `modality_legend.py`, `indigenous_scope.py`, `decisive_fields.py`, `eligibility.py`, `edital_requirements.py`, `section_requirements.py`, `inline_requirements.py`, `deadline_*`, `exam_location.py`. |
| Tabelas | `propostas_campo`, `evidencias`, `blocos_documento`, `revisoes_campo`, `valores_atuais`, `revalidacoes_prazo`. |
| API | `GET /api/campos-decisivos`, `GET /api/elegibilidade*`, `GET /api/prazos*`, `GET /api/quadro-vagas`, `GET /api/revisao/grupos`. |
| CLI | `campos-decisivos`, `elegibilidade*`, `prazos*`, `quadro-vagas`, `quadro-auditoria`, `revisao-grupos`. |
| Estado | **Implementado e testado.** Total publicado nunca substituído pela soma; `CR`/`CR*` não viram zero; PPIQ/PI-PQ não são vaga exclusiva; formação mínima ≠ formação específica; prazos por grupo/documento/versão; local de prova ≠ lotação. |
| Testes | `test_vacancy_tables.py`, `test_vacancy_columns_f41.py`, `test_indigenous_scope_f40.py`, `test_eligibility_f38.py`, `test_eligibility_f39.py`, `test_deadline_audit_f37.py`, `test_edital_requirements.py`, `test_section_requirements.py`, `test_exam_location.py`. |
| Limitações | Categorias ambíguas permanecem ambíguas; não há rateio interpretativo automático. |
| Situação final | **Aprovado.** |

## 5. Revisão e reconciliação

| Item | Conteúdo |
|---|---|
| Objetivo | Decisão humana por campo, agrupada pela evidência, com histórico e proteção contra evidência obsoleta. |
| Módulos | `review.py`, `review_groups.py`, `pilot.py`, `identity_suggestions.py`, `conflict_review.py`, `version_conflicts.py`, `deadline_review.py`. |
| Tabelas | `revisoes_campo`, `valores_atuais`, `lotes_revisao`, `lote_revisao_itens`. |
| API | `GET /api/revisao/fila`, `/grupos`, `/pilotos`, `/piloto`, `/identidades`, `/proposta/{id}`, `/lotes*`; `POST /api/revisao/lotes*`, `/proposta/{id}`, `/selecionar`, `/importar`. |
| CLI | `revisao-fila`, `revisao-decidir`, `revisao-selecionar`, `revisao-lote`, `revisao-exportar`, `revisao-importar`, `revisao-grupos`, `piloto-revisao`, `pilotos`, `identidades-sugeridas`. |
| Estado | **Implementado e testado.** Decisão append-only, idempotente, por campo; hash da evidência e `scope_snapshot` obrigatórios na interface; lote não aprova em massa. |
| Testes | `test_review.py`, `test_review_api.py`, `test_review_groups_f42.py`, `test_pilot_f43.py`, `test_confirmation.py`, `test_conflict_review` (coberto em `test_review_groups_f42`). |
| Limitações | 0 decisões humanas reais; piloto preparado, não revisado. |
| Situação final | **Aprovado.** |

## 6. Elegibilidade, carteira e prioridades

| Item | Conteúdo |
|---|---|
| Objetivo | Separar descoberta geral de recomendação personalizada, com prioridade explicável. |
| Módulos | `eligibility.py`, `portfolio.py`, `opportunities.py`, `priority.py`, `ranking.py`, `preferences.py`, `coverage_states.py`, `data_quality.py`. |
| Tabelas | `propostas_campo`, `revisoes_campo`, `valores_atuais`, `cargos_identidade`, `ops_state`. |
| API | `GET /api/carteira`, `/destaques`, `/dossie`, `GET /api/elegibilidade*`, `GET /api/prioridades`, `GET /api/triagem`, `GET /api/cobertura*`. |
| CLI | `carteira*`, `elegibilidade*`, `prioridades`, `ops-prioridades`, `cobertura*`. |
| Estado | **Implementado e testado.** 676 oportunidades na carteira real; prioridade determinística; lacunas explícitas; nenhuma transferência de vaga entre cargos. |
| Testes | `test_portfolio_f36.py`, `test_eligibility_f38.py`, `test_eligibility_f39.py`, `test_priority.py`, `test_priority_api.py`, `test_ranking.py`, `test_coverage_f33.py`, `test_data_quality.py`. |
| Limitações | Cobertura documental incompleta vira lacuna, não resposta negativa. |
| Correções nesta fase | Cache em processo com fingerprint e invalidação; varredura única (bulk) e pré-agrupamento por concurso. Carteira fria: 4,07 s → 1,09 s; quente: 4,20 s → 0,016 s. |
| Situação final | **Aprovado.** |

## 7. Prazos e conflitos

| Item | Conteúdo |
|---|---|
| Objetivo | Situação temporal por grupo, conflito entre documentos/versões e revalidação. |
| Módulos | `deadline_calendar.py`, `deadline_audit.py`, `deadline_revalidation.py`, `deadline_review.py`, `version_conflicts.py`, `conflict_review.py`. |
| Tabelas | `propostas_campo`, `evidencias`, `documentos`, `versoes_documento`, `revalidacoes_prazo`. |
| API | `GET /api/prazos`, `/auditoria`, `/calendario`, `/caso`, `/revalidacao`, `/revalidacao/historico`; `POST /api/prazos/revalidacao`, `/verificar-documento`; `GET /api/conflitos*`. |
| CLI | `prazos`, `prazos-calendario`, `prazos-auditoria`, `prazos-caso`, `prazos-revalidar`, `prazos-revalidacao-historico`, `conflitos-revisao`, `conflitos-versao`. |
| Estado | **Implementado e testado.** 60 conflitos classificados na base; 11 revalidações; nenhum prazo pendente no fechamento. |
| Testes | `test_deadline_audit_f37.py`, `test_deadline_review` (coberto), `test_portfolio_f36.py`, `test_version_conflicts` (coberto). |
| Limitações | Revalidação depende de fonte oficial acessível; conflito não é resolvido automaticamente. |
| Situação final | **Aprovado.** |

## 8. Monitoramento e operação

| Item | Conteúdo |
|---|---|
| Objetivo | Ciclo periódico, limites, checkpoints, recuperação, alertas e diagnóstico. |
| Módulos | `monitoring.py`, `ops.py`, `ops_config.py`, `notifications.py`, `budget.py`, `page_batches.py`. |
| Tabelas | `ciclos_monitoramento`, `ciclos_fontes`, `alertas`, `ops_state`, `fontes_consumo`, `fontes_estado`. |
| API | `GET /api/monitoramento`, `GET /api/saude`, `GET /api/saude/prontidao`, `GET /api/alertas`, `POST /api/alertas/{id}`. |
| CLI | `monitor`, `ops-ciclo`, `ops-saude`, `ops-alertas`, `ops-alerta-marcar`, `prontidao`. |
| Estado | **Implementado e testado.** Instância única (`radar_ops.lock`), ciclo interrompido marcado na execução seguinte, falha isolada por fonte, orçamento por fonte, notificações opcionais. |
| Testes | `test_monitoring.py`, `test_ops.py`, `test_ops_api.py`, `test_notifications.py`, `test_monitoring_api.py`, `test_backend_gate_f44.py`. |
| Limitações | O relatório de prontidão não consulta o Agendador do Windows; calcula o próximo ciclo pelo intervalo configurado. |
| Correções nesta fase | `next_run_at` calculado; `/api/saude/prontidao` com cache curto e geração single-flight; GETs pesados limitados a 2 concorrentes (429). |
| Situação final | **Aprovado.** |

## 9. Módulo de estudos

| Capacidade | Módulo/rota | Estado | Evidência |
|---|---|---|---|
| Perfil de estudos | `study_store.py`, `knowledge_store.py`; `/api/estudos/perfil` | Implementado e testado | `test_study.py`, `test_knowledge_api.py` |
| Disciplinas e tópicos | `study_store.py`; `/api/estudos/disciplinas`, `/topicos` | Implementado e testado | `test_study.py` |
| Sessões e cronômetro | `study.py`, `study_store.py`; `/sessoes`, `/sessao-atual` | Implementado e testado; conclusão idempotente por id | `test_study.py`, `test_backend_gate_f44.py` |
| Progresso | `study_store.py`; `/progresso`, `/painel` | Implementado e testado | `test_study.py` |
| Revisão espaçada | `study_store.py`; `/revisoes` | Implementado e testado | `test_study.py` |
| Flashcards + mídia | `flashcards.py`, `practice_store.py`, `media.py`; `/flashcards*`, `/midia/{id}` | Implementado e testado; SM-2-lite; imagem por assinatura/hash | `test_practice.py`, `test_flashcards.py`, `test_media.py` |
| Questões e tentativas | `questions.py`, `practice_store.py`; `/questoes`, `/tentativas` | Implementado e testado | `test_questions.py`, `test_practice.py` |
| Simulados | `exams.py`, `practice_store.py`; `/simulados*` | Implementado e testado; tempo no servidor; finalização idempotente; gabarito não vaza em andamento | `test_exams.py`, `test_practice.py` |
| Desempenho | `practice_store.py`; `/desempenho` | Implementado e testado | `test_practice.py` |
| Exportar/importar/backup | `study_backup.py`; `/exportar`, `/importar` | Implementado e testado | `test_study_backup.py` |
| Pacotes | `packages.py`; `/pacotes*` | Implementado e testado; limites, licença e colisões | `test_packages.py` |
| Caderno de erros | — | **Ausente no planejamento documentado** | modo `revisao_erros` cobre o caso |
| Conteúdo de terceiros | — | **Bloqueado externo** por licença; questões são do usuário | `THIRD_PARTY_NOTICES.md`, `docs/.../study-platform-open-source-mining.md` |

Observações: os dados de estudo ficam em tabelas `estudo_*`/`pratica_*`, separados do
domínio de concursos. Nenhum endpoint de estudo depende de chave de fornecedor. O
temporizador de simulado é server-side; a finalização grava tentativas uma única vez.

## 10. API, contratos e documentação

| Item | Conteúdo |
|---|---|
| Registro | `radar/api_contract.py`: 129 entradas método+rota, 112 caminhos, 24 domínios. |
| Verificação | `api_contract.verify()` compara método+rota com o AST de `radar/server.py`; teste falha se uma rota real não estiver documentada ou se o contrato listar rota inexistente. |
| Documentação | `docs/API.md` gerado por `python -m radar api-contrato --markdown`. |
| Contrato v1 | `GET /api/concursos` preservado com os 18 campos; coberto por `test_contract.py`. |
| Padrões | Erros JSON, 400/403/404/405/415/429/503, `limit`/`offset`, idempotência declarada por rota. |
| Estado | **Implementado e testado.** |
| Limitações | Não é OpenAPI formal; é especificação equivalente versionada e verificável, sem dependência nova. |
| Situação final | **Aprovado.** |

## 11. Banco, migrações e integridade

| Item | Conteúdo |
|---|---|
| Schema | v21, 45 tabelas, migrações aditivas idempotentes em `document_store.py`. |
| Integridade | `PRAGMA integrity_check` = `ok`; `foreign_key_check` sem violações; backup consistente por API em `data/radar.sqlite3.bak-20261019-072446`. |
| Concorrência | WAL não habilitado (`journal_mode=delete`); escritas usam `BEGIN IMMEDIATE`; leituras concorrentes com conexão por requisição. |
| Testes | `test_document_store.py`, `test_practice.py` (migração idempotente), `test_document_versions.py`. |
| Situação final | **Aprovado.** Nenhuma migração nova nesta fase. |

## 12. Segurança

| Item | Conteúdo |
|---|---|
| Fronteiras | `_serve_file` com resolução contra `WEB_DIR`; rotas dinâmicas validam UUID/ids; download com allowlist de hosts; importações com limites e validação de assinatura; SQL parametrizado. |
| Escrita local | `Origin` loopback na mesma porta + `Content-Type: application/json`; `Host` loopback na mesma porta (anti DNS rebinding); 403/415. |
| Cabeçalhos | `X-Content-Type-Options: nosniff`; `Cache-Control: no-store` em JSON. |
| Segredos | Nenhum segredo no diff; credenciais apenas por variável de ambiente; logs não incluem corpo transitório. |
| Revisão independente | Nenhum achado crítico/alto; 2 médios corrigidos (Host e concorrência de GETs pesados). |
| Situação final | **Aprovado.** |

## 13. Desempenho medido

Metodologia: `create_server` + `urllib` local, base real de 67 MB, uma execução fria e uma
quente por rota; escrita de estudos em cópia isolada.

| Operação | Antes | Depois |
|---|---|---|
| `GET /api/carteira?limit=50` | 4,07 s frio / 4,20 s quente | **1,09 s frio / 0,016 s quente** |
| `GET /api/quadro-vagas` | 2,83 s por chamada | **2,88 s frio / 0,009 s quente** |
| `GET /api/saude/prontidao` | 0,63–0,78 s por chamada | **0,64 s frio / cache 60 s** |
| `GET /api/revisao/grupos?contexto=1` | 5,28 s frio / 1,03 s quente | 5,25 s / 1,03 s (pré-aquecer com `revisao-prewarm`) |
| `GET /api/concursos` | 0,10 s / 0,003 s | inalterado |
| Sessão de estudo (iniciar/concluir) | 0,008 s / 0,007 s | inalterado |
| Exportar estudos | 0,003 s | inalterado |

Causas: varredura O(n×m) em `decisive_fields` (corrigida com pré-agrupamento), quatro
varreduras de oportunidades (corrigida com bulk) e reparse de PDF no quadro (corrigida
com cache por versão/bloco/proposta). Nenhum índice novo foi necessário.

## 14. Itens P2 (fora do caminho crítico)

1. **OpenAPI formal** — a especificação equivalente em `docs/API.md` cobre o contrato; gerar OpenAPI exigiria dependência ou gerador próprio.
2. **Histórico de extração antigo** — 733 versões `parcial` sem nota de análise; reprocessar com o extrator atual resolveria, mas não bloqueia o frontend.
3. **WAL** — o banco usa `journal_mode=delete`; WAL exigiria migração operacional e revisão de backup concorrente.
4. **Cota de threads/timeout HTTP** — o limite de 2 GETs pesados reduz a amplificação; um pool fixo e timeout de socket é melhoria operacional.
5. **CORS/autenticação de rede** — desnecessários no modelo local em `127.0.0.1`.
6. **Cache de prontidão com `full=1` via HTTP** — o CLI já força `full=True`; o endpoint usa cache de 60 s.
7. **Rate limit por IP** — o produto é single-user local; 429 por concorrência já existe.
8. **Cobertura universal de concursos** — explicitamente fora do critério de prontidão.

## 15. Situação final por domínio

| Domínio | Situação |
|---|---|
| Coleta e fontes | Aprovado (2 fontes pendentes externas) |
| Pipeline documental | Aprovado |
| Modelo canônico | Aprovado |
| Vagas, formação, prazos, localização | Aprovado |
| Revisão e reconciliação | Aprovado |
| Elegibilidade e carteira | Aprovado |
| Prazos e conflitos | Aprovado |
| Monitoramento e operação | Aprovado |
| Estudos | Aprovado (caderno de erros não planejado) |
| API e contratos | Aprovado |
| Banco e integridade | Aprovado |
| Segurança | Aprovado |
| Desempenho | Aprovado após correções medidas |

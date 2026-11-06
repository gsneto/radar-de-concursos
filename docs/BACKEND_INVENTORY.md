# Inventário do backend — fechamento para o frontend (Fase 44) e consolidação (Fase 47)

Referência: `radar-configuracao`, schema **v21**, 92 módulos em
`radar/`, 85 arquivos de teste, **130 entradas método+rota** (113 caminhos), 45 tabelas documentais/estudos (+ tabela v1 `concursos`).
Data de atualização (Fase 47): **2026-11-04**. Números da base consolidada: **3.420 documentos**,
**2.013 versões**, **42.009 blocos**, **18.240 propostas/evidências**, **843 certames** (+1 container DOU),
**894 oportunidades na carteira**, **14 revalidações de prazo** (`0` pendentes).

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

---

## 16. Inventário Completo e Classificação de Consolidação (Fase 47)

Nenhuma tabela ou subcomando foi removido na Fase 47 para preservar 100% de compatibilidade com os testes e scripts operacionais. Abaixo está a classificação explícita do que é ativo, o que é diagnóstico/manutenção e o que é legado contratual v1 candidato a agrupamento futuro.

### 16.1 Classificação dos Subcomandos CLI (`radar/__main__.py` — 120 subcomandos de topo + 8 subparsers `estudos-*`)

| Categoria | Qtd | Subcomandos | Papel e Recomendação de Consolidação |
|---|---:|---|---|
| **Operação cotidiana e servidor** | 12 | `serve`, `prontidao`, `ops-ciclo`, `ops-saude`, `ops-alertas`, `ops-alerta-marcar`, `ops-config`, `ops-triagem`, `ops-notificar`, `ops-identidade`, `ops-prioridades`, `ops-preferencias` | **Ativos (núcleo operacional).** Usados pelos scripts PowerShell (`scripts/*.ps1`) e operação local. |
| **Carteira, elegibilidade e prazos** | 15 | `carteira`, `carteira-destaques`, `carteira-dossie`, `elegibilidade`, `elegibilidade-pendentes`, `elegibilidade-revisao`, `elegibilidade-destaques`, `prazos`, `prazos-calendario`, `prazos-auditoria`, `prazos-caso`, `prazos-verificar-documento`, `prazos-revalidar`, `prazos-revalidacao-historico`, `campos-decisivos` | **Ativos (decisão do usuário).** Espelham diretamente as telas principais da SPA React. |
| **Revisão humana, reconciliação e conflitos** | 22 | `revisao-fila`, `revisao-grupos`, `revisao-decidir`, `revisao-selecionar`, `revisao-lote`, `revisao-exportar`, `revisao-importar`, `revisao-duplicados`, `revisao-prewarm`, `reconciliacao`, `reconciliacao-historico`, `reconciliacao-decidir`, `reconciliacao-criar-cargo`, `conflitos-revisao`, `conflitos-versao`, `curadoria-autonoma`, `piloto-revisao`, `pilotos`, `identidades-sugeridas`, `oportunidades`, `oportunidade`, `evidencia` | **Ativos (auditoria e curadoria humana/autônoma).** Sustentam o fluxo append-only de decisão e resolução determinística. |
| **Pipeline documental, OCR e aquisição** | 28 | `pipeline`, `pipeline-documentos`, `pipeline-duplicados`, `pipeline-cobertura`, `pipeline-continuidade`, `pipeline-regional`, `documentos-tipos`, `documentos-reprocessar`, `documentos-nominais`, `documentos-nominais-destino`, `documentos-parciais`, `documentos-paginas`, `documentos-lote`, `documentos-pendentes`, `documentos-extrair`, `documentos-bloqueados`, `documentos-baixar-bloqueados`, `documentos-reclassificar-bloqueios`, `documentos-importar`, `aquisicao-planejar`, `aquisicao-executar`, `editais-faltantes`, `ocr-pendentes`, `ocr-executar`, `cobertura`, `cobertura-papeis`, `cobertura-estados`, `lacunas` | **Ativos (manutenção e redução de pendências).** Usados na Tarefa 2 da Fase 47 para zerar versões `nao_iniciada`, `pdf_sem_texto` e editais oficiais sem versão. Candidatos a agrupamento futuro sob `radar pipeline <acao>` e `radar doc <acao>`. |
| **Fontes, confirmação, identidade e contrato** | 15 | `fontes`, `fontes-consumo`, `fontes-revisar`, `fontes-politica`, `confirmacao-status`, `confirmacao-reconciliar`, `confirmacao-lote`, `confirmacao-item`, `confirmacao-metricas`, `confirmacao-prioridades`, `confirmacao-oportunidades`, `identidade`, `identidade-reparar`, `associacoes`, `associacoes-fila` | **Ativos (governança de fontes e vínculos).** |
| **Utilitários de domínio e contrato** | 6 | `api-contrato`, `linha-do-tempo`, `localidades`, `quadro-vagas`, `quadro-auditoria`, `monitor` | **Ativos (diagnóstico e geração de `docs/API.md`).** |
| **Estudos e prática pessoal** | 16 (+8 sub) | `estudos-painel`, `estudos-disciplina`, `estudos-topico`, `estudos-sessao`, `estudos-revisao`, `estudos-conteudo`, `estudos-perfil`, `estudos-cobertura`, `estudos-exportar`, `estudos-importar`, `estudos-backup`, `estudos-flashcard`, `estudos-questao`, `estudos-simulado`, `estudos-pacote`, `estudos-desempenho` | **Ativos (módulo de estudos).** Já organizados sob o prefixo `estudos-*`. |
| **Legado contratual v1 / pilotos de fase** | 15 | `collect`, `documents-migrate`, `documents-sync`, `documents-register`, `documents-fetch`, `documents-analyze`, `documents-review`, `documents-select`, `documents-coverage`, `documents-reconcile`, `documents-link-amendment`, `documents-role`, `associacao-revisar`, `ibfc-piloto`, `quadrix-cargos` | **Legado preservado (compatibilidade v1/Fases 3–18).** Substituídos no uso diário pelos comandos em português (`documentos-*`, `revisao-*`, `reconciliacao-*`, `ops-ciclo`), mas mantidos para não quebrar a suíte de testes históricos. |

### 16.2 Classificação das 45 Tabelas SQLite (`data/radar.sqlite3`, Schema v21)

| Grupo | Tabelas (contagem em `2026-11-04`) | Situação |
|---|---|---|
| **1. Identidade e Observações Canônicas (4)** | `concursos_identidade` (844), `observacoes_concurso` (844), `cargos_identidade` (125), `observacoes_cargo` (0) | **Ativas.** `observacoes_cargo` é populada quando conectores estruturados registram cargo antes da extração de PDF. |
| **2. Armazenamento e Extração Documental (8)** | `documentos` (3.420), `documento_urls` (3.420), `versoes_documento` (2.013), `blocos_documento` (42.009), `propostas_campo` (18.240), `evidencias` (18.240), `eventos_documentais` (7.559), `associacoes_documento` (206) | **Ativas (núcleo de rastreabilidade).** |
| **3. Revisão Humana, Reconciliação e Prazos (7)** | `revisoes_campo` (1.589), `valores_atuais` (1.441), `lotes_revisao` (0), `lote_revisao_itens` (0), `reconciliacoes_cargo` (475), `revalidacoes_prazo` (17), `auditorias_cobertura` (0) | **Ativas** (populadas via curadoria autônoma auditável e decisões rastreadas). Nota: `auditorias_cobertura` é **legada de fases iniciais** (cobertura atual é calculada por `coverage_states.py` e `cobertura-papeis`), mantida por compatibilidade de schema. |
| **4. Coleta, Fontes, Monitoramento e Operação (11)** | `ciclos_monitoramento` (76), `ciclos_fontes` (328), `alertas` (4.536), `ops_state` (3), `fila_confirmacao` (709), `tentativas_download` (1.183), `ingestoes_documentais` (0), `fontes_estado` (1), `fontes_consumo` (2), `fontes_revisoes` (0), `localidades_ibge` (5.570) | **Ativas.** Sustentam o ciclo autônomo, orçamento de fontes e geografia IBGE. |
| **5. Estudos e Prática Pessoal (15)** | `estudo_disciplinas` (0), `estudo_topicos` (0), `estudo_progresso` (0), `estudo_sessoes` (0), `estudo_revisoes` (0), `estudo_perfil` (0), `pratica_flashcards` (0), `pratica_flashcard_revisoes` (0), `pratica_midias` (0), `pratica_questoes` (0), `pratica_questao_versoes` (0), `pratica_tentativas` (0), `pratica_simulados` (0), `pratica_simulado_questoes` (0), `pratica_pacotes` (0) | **Ativas (dados pessoais do usuário).** Isoladas das tabelas de concursos. |

### 16.3 Refatoração Estrutural de `radar/server.py` (Fase 47)

- O método `do_GET` de `_RadarRequestHandler` (anteriormente uma cadeia monolítica de ~1.035 linhas com 75+ ramos `elif`) foi consolidado em uma tabela de despacho declarativa (`_GET_DISPATCH`, $O(1)$ por caminho exato) combinada com 6 métodos por domínio (`_get_core_and_ops`, `_get_pipeline_and_documents`, `_get_review_and_reconciliation`, `_get_portfolio_and_eligibility`, `_get_deadlines_and_conflicts`, `_get_studies_and_practice`) e `_get_dynamic_routes` para rotas parametrizadas.
- `radar/api_contract.py:server_routes()` foi atualizado para inspecionar `do_GET` e os handlers `_get_*` no AST, preservando `api_contract.verify()` com 130 rotas verificadas (`ok=True`).


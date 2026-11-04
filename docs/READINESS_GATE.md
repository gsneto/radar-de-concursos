# Gate de prontidão do backend para o frontend — Fase 44 (atualizado na Fase 47)

Data de referência: **2026-11-04** (baseline original Fase 44: `2026-10-19`). Base: `radar-configuracao`,
schema **v21**. Relatório reproduzível:

```powershell
.\.venv\Scripts\python.exe -m radar prontidao --db .\data\radar.sqlite3
```

Estados: **APROVADO**, **REPROVADO**, **PENDENTE EXTERNO**. Um item `PENDENTE EXTERNO`
não reprova o backend; um item `REPROVADO` bloqueia.

## Dados

| Critério | Estado | Evidência |
|---|---|---|
| Banco íntegro | APROVADO | `PRAGMA integrity_check` = `ok`; `foreign_key_check` = 0 violações; 45 tabelas. |
| Migrações verificadas | APROVADO | Schema v21; migrações aditivas e idempotentes cobertas por `test_document_store.py` e `test_practice.py`; nenhuma migração nova nesta fase. |
| Proveniência documental | APROVADO | **18.240 propostas = 18.240 evidências**; 0 propostas sem evidência; 0 evidências com trecho vazio; todas as **2.013 versões** com SHA-256 de 64 caracteres. |
| Idempotência | APROVADO | Reprocessamento (`test_reprocess.py`), decisão repetida (`test_review.py`), lote (`test_review.py`), simulado (`test_practice.py`), importação (`test_study_backup.py`) e lote de páginas (`test_multipage.py`). |
| Atualização de versões | APROVADO | Versão imutável por SHA-256; `previous_version_id`; retificação vinculada; `test_document_versions.py`, `test_document_amendment.py`. |
| Políticas de persistência | APROVADO | `source_policy` consultada no ponto de escrita (`monitoring.py`); corpo não autorizado descartado; `test_sources.py`. |

## Domínio

| Critério | Estado | Evidência |
|---|---|---|
| Identidade de concurso e cargo | APROVADO | `concursos_identidade` separa `certame` (843) de `container_fonte` (1); 125 identidades de cargo; reconciliação exige decisão humana; `test_identity.py`, `test_role_identity_f35.py`. |
| Campos decisivos com estados | APROVADO | `decisive_report` com `candidato`, `ambiguo`, `nao_localizado`, `nao_pesquisado`, `sem_data_documental`; 127 conflitos classificados; `test_vacancy_tables.py`, `test_indigenous_scope_f40.py`. |
| Elegibilidade e reservas | APROVADO | PI exclusivo, PPIQ/PI-PQ unificadas, `CR`/`CR*`, zero explícito e menção fora de escopo separados; `test_eligibility_f38.py`, `test_eligibility_f39.py`, `test_vacancy_columns_f41.py`. |
| Prazos e documentos rastreáveis | APROVADO | Grupos de prazo por documento/versão; revalidação com fonte e hash; 14 revalidações (`0` pendentes); `test_deadline_audit_f37.py`. |
| Carteira sem mistura de cargos | APROVADO | **894 oportunidades** por concurso+cargo; prioridade explicada e menor distância desde Paulo Afonso–BA; `test_portfolio_f36.py`, `test_coverage_consolidation_f47.py`. |
| Dados incompletos sem quebrar | APROVADO | Lacunas explícitas; 1.407 documentos secundários/agregador sem versão (`0` editais oficiais decisivos pendentes), 1 PDF corrompido na origem (`pdf_ilegivel`), 1.111 parciais históricas e 127 conflitos aparecem como pendência, não como erro. |

## Coleta e operação

| Critério | Estado | Evidência |
|---|---|---|
| Conectores com estado real | APROVADO | 18 fontes catalogadas; 5 habilitadas; 2 pendentes externas; 4 bloqueadas por licença/robots; 3 aguardando validação de uso. `GET /api/fontes` reflete a configuração. |
| Limites e custos | APROVADO | `budget.py` impõe chamadas, itens, créditos, valor, intervalo mínimo e janela mensal; `test_sources.py`. |
| Checkpoints e retomada | APROVADO | `budget.save_checkpoint`, `page_batches` com checkpoint e retomada; `test_multipage.py`, `test_acquisition_f33.py`. |
| Monitoramento e diagnóstico | APROVADO | `ciclos_monitoramento`/`ciclos_fontes`; `GET /api/saude`; `GET /api/saude/prontidao`; `test_monitoring.py`, `test_ops.py`, `test_backend_gate_f44.py`. |
| Recuperação de falhas | APROVADO | Falha isolada por fonte; ciclo `em_andamento` vira `interrompido` no ciclo seguinte; lock de instância; `test_monitoring.py`. |
| Ciclo agendado verificável | APROVADO | Tarefa `Radar de Concursos - Ciclo` em estado `Ready`; último ciclo real `parcial` (fonte sem observação v1) e próximo previsto calculado pelo intervalo de 6 h. |

## API

| Critério | Estado | Evidência |
|---|---|---|
| Endpoints dos domínios | APROVADO | 129 entradas método+rota em 24 domínios, incluindo concursos, documentos, pipeline, revisão, elegibilidade, carteira, prazos, fontes, monitoramento, saúde, estudos, flashcards, questões, simulados e pacotes. |
| Contrato público v1 | APROVADO | `GET /api/concursos` com 18 campos preservado; `test_contract.py` compara o payload. |
| Documentação dos contratos | APROVADO | `docs/API.md` gerado por `python -m radar api-contrato --markdown`; `api_contract.verify()` compara método+rota com o AST do servidor. |
| Paginação, filtros e erros | APROVADO | `limit`/`offset` validados por rota; erros JSON 400/403/404/405/415/429/503; nenhum traceback na resposta; `test_review_api.py`, `test_backend_gate_f44.py`. |
| Ausência de endpoints enganosos | APROVADO | Rotas leem o banco real; nenhuma fixture/constante de produção; `test_contract.py`, `test_server.py`. |
| Testes de contrato | APROVADO | `test_contract.py` (v1) e `test_backend_gate_f44.py::ContractTest`/`ContractMethodTest`. |

## Estudos

| Critério | Estado | Evidência |
|---|---|---|
| Serviços essenciais | APROVADO | Perfil, disciplinas, tópicos, sessões, progresso, revisões, flashcards, questões, tentativas, simulados, desempenho, exportação/importação, pacotes e mídia. |
| Sessões e progresso | APROVADO | Cronômetro server-side; uma sessão aberta por vez; conclusão idempotente por id; `test_study.py`, `test_backend_gate_f44.py`. |
| Flashcards e revisão | APROVADO | SM-2-lite; fila novos/vencidos/futuros; imagem validada por assinatura; `test_flashcards.py`, `test_practice.py`, `test_media.py`. |
| Questões e tentativas | APROVADO | Correção no servidor; versão da questão preservada; `test_questions.py`, `test_practice.py`. |
| Simulados e resultados | APROVADO | Tempo e expiração no servidor; respostas salvas; finalização idempotente; gabarito oculto em andamento; `test_exams.py`, `test_practice.py`. |
| Importação/exportação | APROVADO | Formato v2, transação, limites, reexecução; `test_study_backup.py`, `test_packages.py`. |
| Conteúdo externo | PENDENTE EXTERNO | Nenhum conteúdo de terceiro importado; questões são do usuário; licenças em `THIRD_PARTY_NOTICES.md`. |

## Segurança e testes

| Critério | Estado | Evidência |
|---|---|---|
| Nenhum defeito crítico/alto conhecido | APROVADO | Revisão independente de código e de segurança: 0 crítico, 0 alto; 2 médios corrigidos (Host/DNS rebinding e concorrência de GETs pesados). |
| Nenhuma quebra de integridade | APROVADO | `integrity ok`, FK vazia, 0 decisões fictícias, 0 revisões/valores/reconciliações/lotes reais. |
| Nenhuma credencial exposta | APROVADO | Nenhum segredo no diff; credenciais apenas por `RADAR_*`; respostas de erro sem caminho/SQL/traceback; prontidão HTTP redige caminho absoluto. |
| Suíte aprovada | APROVADO | **1.915+ testes Python, OK** (em `.venv`) + suíte completa React (`vitest`). |
| Fluxos essenciais cobertos | APROVADO | Contrato, escrita/CSRF/Host, prontidão, estados de extração, cache/invalidação, estudos, importação/exportação, simulados, pipeline, coleta e revisão. |
| Recuperação documentada | APROVADO | Backup por API (`data/radar.sqlite3.bak-20261104`), ciclo interrompido, retomada de páginas, reprocessamento, importação transacional. |

## Conclusão

**BACKEND CONSOLIDADO E PRONTO.**

Não há bloqueador concreto. Permanecem como não bloqueadores (documentados em [`docs/COBERTURA_DADOS.md`](COBERTURA_DADOS.md)):

- 2 fontes dependem de credencial/termos externos (`dados-gov-br`, `conecta-gov-br`);
- 1.407 documentos secundários/agregador sem versão (`0` editais oficiais decisivos pendentes) e 1.111 versões históricas parciais (retomáveis);
- 1 versão com PDF corrompido na origem (`pdf_ilegivel`; todas as 6 versões `pdf_sem_texto` foram processadas por OCR na Fase 47);
- 127 conflitos documentais classificados aguardando decisão humana;
- 0 decisões humanas reais (o piloto está preparado, não revisado);
- itens P2 listados em `docs/BACKEND_INVENTORY.md`.

Nenhum desses itens impede o frontend: todos têm estado explícito, mecanismo de
tratamento e recuperação, e não exigem módulo essencial novo no backend.

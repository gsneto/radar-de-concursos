# API do Radar de Concursos

Versão do contrato: `api_contract_v1`. Rotas: **129** (112 caminhos).

## Convenções

- Servidor local em `127.0.0.1`; sem autenticação de rede.
- Corpo de escrita em JSON UTF-8 (`Content-Type: application/json`).
- `Origin`, quando enviado, precisa ser loopback na mesma porta; caso contrário, 403.
- `Host` precisa ser loopback na mesma porta; caso contrário, 403 (anti DNS rebinding).
- Erros: `{"error": "..."}` com 400/403/404/405/415/429/503; nunca traceback.
- Consultas pesadas concorrentes podem receber 429; tente novamente.
- Paginação por `limit`/`offset` quando a rota declara os parâmetros.
- `GET /api/concursos` mantém o contrato v1 com 18 campos (aditivo desde então).

## Alertas

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/alertas` | limit, unseen | — | não | n/a | Alertas persistentes, com contagens. |
| POST | `/api/alertas/{alert_id}` | — | action, until | sim | sim | Marca visto/adiado/reaberto/dispensado; não apaga histórico. |

## Associações documento↔concurso

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/associacoes` | — | — | não | n/a | Associações documento↔concurso e seu estado. |
| GET | `/api/associacoes/fila` | limit, state | — | não | n/a | Fila de associações pendentes de revisão. |
| POST | `/api/associacoes/{association_id}` | — | action, reviewer, reason | sim | sim | Confirma ou rejeita uma associação documental. |

## Carteira operacional

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/carteira` | conflito, contest_id, documental, indigena, limit, offset, prazo, prontidao, role_id, search, si, uf | — | não | n/a | Carteira operacional de oportunidades com prioridade explicada. |
| GET | `/api/carteira/destaques` | limit | — | não | n/a | Destaques da carteira. |
| GET | `/api/carteira/dossie` | role_id, scope | — | não | n/a | Dossiê completo de uma oportunidade da carteira. |

## Cobertura e confirmação

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/cobertura` | — | — | não | n/a | Cobertura de conferência por concurso. |
| GET | `/api/cobertura/estados` | limit | — | não | n/a | Estados de cobertura documental por concurso. |
| GET | `/api/cobertura/resumo` | — | — | não | n/a | Resumo agregado de cobertura e pendências. |
| POST | `/api/cobertura/papeis` | — | contest_id, role_id, state, reviewer, note | sim | sim | Registra conferência de escopo por cargo, sem confirmar campos. |

## Concursos, identidade e oportunidades

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/concursos` | — | — | não | n/a | Contrato público v1: lista de concursos com 18 campos, lida de list_records. |
| GET | `/api/concursos/{contest_id}/detalhes` | — | — | não | n/a | Alias versionado do detalhe documental (UUID validado). |
| GET | `/api/concursos/identidades` | — | — | não | n/a | Identidades canônicas de concurso (inclui containers de fonte marcados). |
| GET | `/api/identidade` | — | — | não | n/a | Relatório de identidade documental e pendências de reconciliação. |
| POST | `/api/identidade/reparar` | — | dry_run | sim | sim | Repara vínculos de identidade comprovados; dry_run por padrão. |
| GET | `/api/oportunidades` | conflict, contest_id, document_state, field, has_page, limit, min_priority, offset, search | — | não | n/a | Fila de oportunidades documentais com filtros combináveis. |
| GET | `/api/oportunidades/{role_id}` | scope | — | não | n/a | Dossiê de uma oportunidade (concurso + cargo + escopo). |
| GET | `/api/linha-do-tempo` | limit, since | — | não | n/a | Linha do tempo de eventos documentais, mais recente primeiro. |
| GET | `/api/campos-decisivos` | contest_id, limit | — | não | n/a | Cobertura dos campos decisivos por concurso, com estado explícito. |
| GET | `/api/quadro-vagas` | contest_id, version_id | — | não | n/a | Quadro de vagas por colunas e modalidades, com validação aritmética. |
| GET | `/api/lacunas` | limit | — | não | n/a | Lacunas de dados agrupadas por campo e motivo, sem inventar valor. |

## Confirmação documental

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/confirmacao` | — | — | não | n/a | Estado da fila de confirmação documental. |

## Conflitos

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/conflitos` | contest_id, limit | — | não | n/a | Conflitos entre versões documentais. |
| GET | `/api/conflitos-revisao` | cause, contest_id, field, limit, offset, priority | — | não | n/a | Conflitos classificados com causa e próxima ação. |

## Documentos e aquisição

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/documentos/bloqueados` | contest_id, limit, state | — | não | n/a | Aquisição bloqueada por política/robots/HTTP, com alternativas. |
| GET | `/api/documentos/nominais` | limit, offset | — | não | n/a | Listas nominais detectadas; corpo não é baixado nem extraído. |
| GET | `/api/documentos/nominais-destino` | contest_id, destination, limit, offset | — | não | n/a | Destino operacional das listas nominais. |
| GET | `/api/editais-faltantes` | limit, source | — | não | n/a | Concursos sem edital localizado, com próxima ação de coleta. |
| POST | `/api/documentos/importar` | — | document_id, declared_origin, channel, content_base64, dry_run | sim | condicional | Ingestão manual controlada, com procedência declarada e hash. |
| POST | `/api/documentos/reprocessar` | — | version_ids, dry_run, limit | sim | sim | Reprocessa versões com a versão atual do extrator, sem duplicar propostas. |
| POST | `/api/documentos/tipos` | — | document_id, tipo_documental, reviewer, reason | sim | sim | Reclassifica o tipo documental com justificativa registrada. |

## Elegibilidade

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/elegibilidade` | conflict, conflito, contest_id, eligibility, identity, indigenous, limit, offset, profile, role_id, search, si, temporal, uf | — | não | n/a | Matriz de elegibilidade por cargo, formação e reserva indígena. |
| GET | `/api/elegibilidade/destaques` | limit, profile | — | não | n/a | Destaques de elegibilidade para um perfil. |
| GET | `/api/elegibilidade/pendentes` | cause, contest_id, limit, offset | — | não | n/a | Pendências de elegibilidade com causa e próxima ação. |
| GET | `/api/elegibilidade/revisao` | limit, profile | — | não | n/a | Revisão de compatibilidade de formação. |

## Estudos

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/estudos/painel` | — | — | não | n/a | Painel de estudos: disciplinas, tópicos, progresso, tempo e revisões. |
| GET | `/api/estudos/disciplinas` | — | — | não | n/a | Disciplinas de estudo. |
| POST | `/api/estudos/disciplinas` | — | nome, peso | sim | nao | Cria disciplina de estudo. |
| GET | `/api/estudos/topicos` | disciplina_id | — | não | n/a | Tópicos, opcionalmente por disciplina. |
| POST | `/api/estudos/topicos` | — | disciplina_id, nome, parent_id | sim | nao | Cria tópico de estudo. |
| GET | `/api/estudos/progresso` | contest_id | — | não | n/a | Progresso por tópico e por edital. |
| POST | `/api/estudos/progresso` | — | topico_id, state, contest_id | sim | sim | Define o estado de progresso de um tópico. |
| GET | `/api/estudos/sessoes` | limit | — | não | n/a | Histórico de sessões de estudo. |
| POST | `/api/estudos/sessoes` | — | action, id, disciplina_id, topico_id, contest_id, modo | sim | condicional | Inicia/pausa/retoma/conclui/descarta sessão; uma sessão aberta por vez. |
| GET | `/api/estudos/sessao-atual` | — | — | não | n/a | Sessão aberta e tempo decorrido calculado no servidor. |
| GET | `/api/estudos/revisoes` | — | — | não | n/a | Revisões espaçadas pendentes. |
| POST | `/api/estudos/revisoes` | — | progresso_id, resultado | sim | sim | Marca revisão espaçada como concluída. |
| GET | `/api/estudos/perfil` | — | — | não | n/a | Perfil de conhecimento por conceito. |
| POST | `/api/estudos/perfil` | — | disciplina, rotulo, nivel, revisar, confianca, observacoes, origem | sim | sim | Atualiza o perfil de conhecimento. |
| DELETE | `/api/estudos/perfil` | conceito_key | — | sim | sim | Remove uma entrada do perfil. |
| GET | `/api/estudos/conteudo` | contest_id | — | não | n/a | Conteúdo programático do edital por concurso. |
| GET | `/api/estudos/preparacao` | contest_id | — | não | n/a | Preparação: cobertura do conteúdo e perspectivas. |
| GET | `/api/estudos/exportar` | — | — | não | n/a | Exporta dados pessoais de estudo em JSON versionado. |
| POST | `/api/estudos/importar` | — | payload, dry_run | sim | sim | Importa dados pessoais de estudo com validação e transação. |
| POST | `/api/estudos/lacuna` | — | contest_id, conceito_key | sim | sim | Envia lacuna de edital para a trilha de estudo. |

## Flashcards

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/estudos/flashcards` | incluir_arquivados | — | não | n/a | Lista flashcards. |
| GET | `/api/estudos/flashcards/fila` | limit | — | não | n/a | Fila de revisão de flashcards (novos + vencidos). |
| GET | `/api/estudos/flashcards/estatisticas` | — | — | não | n/a | Estatísticas de flashcards. |
| POST | `/api/estudos/flashcards` | — | action, id, frente, verso, disciplina_id, topico_id, contest_id, conceito_key, tags, fonte, licenca, qualidade, estado | sim | condicional | Cria, atualiza ou revisa flashcard (SM-2-lite). |
| POST | `/api/estudos/flashcards/{flashcard_id}/imagem` | — | dados_base64, licenca | sim | sim | Anexa imagem validada por assinatura binária e hash. |
| DELETE | `/api/estudos/flashcards/{flashcard_id}/imagem` | — | — | sim | sim | Remove a imagem do flashcard. |
| GET | `/api/estudos/midia` | — | — | não | n/a | Rota base de mídia: exige id; sem id devolve 400. |
| GET | `/api/estudos/midia/{media_id}` | — | — | não | n/a | Serve mídia local com Content-Type fixo e nosniff. |

## Fontes e consumo

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/fontes` | — | — | não | n/a | Catálogo de fontes com política de persistência e estado real. |
| GET | `/api/fontes/{source_id}` | — | — | não | n/a | Detalhe da fonte: política por tipo, consumo e revisões. |
| GET | `/api/fontes-consumo` | limit, source_id | — | não | n/a | Consumo por fonte (chamadas, créditos, custo) e último resultado. |

## Monitoramento

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/monitoramento` | — | — | não | n/a | Ciclos de monitoramento, fontes e pendências. |

## Pacotes de conteúdo

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/estudos/pacotes` | limit | — | não | n/a | Pacotes de conteúdo exportados/importados. |
| GET | `/api/estudos/pacotes/exportar` | licenca, nome, tipo | — | não | n/a | Exporta pacote ZIP com manifesto e direitos declarados. |
| POST | `/api/estudos/pacotes/previa` | — | dados_base64 | sim | sim | Pré-visualiza pacote sem gravar (limites de tamanho e estrutura). |
| POST | `/api/estudos/pacotes/importar` | — | dados_base64, dry_run | sim | sim | Importa pacote com validação de licença, tamanho e colisões. |

## Pipeline documental

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/pipeline` | — | — | não | n/a | Visão do pipeline documental por etapa, com contagens reais. |
| GET | `/api/pipeline/cobertura` | limit | — | não | n/a | Cobertura de documentos por concurso e estado de conferência. |
| GET | `/api/pipeline/continuidade` | — | — | não | n/a | Continuidade de tabelas entre páginas e versões. |
| GET | `/api/pipeline/documentos` | contest_id, limit, pending | — | não | n/a | Documentos pendentes ou processados, com motivo por estado. |
| GET | `/api/pipeline/duplicidades` | limit | — | não | n/a | Duplicidades documentais candidatas, sem fusão automática. |
| GET | `/api/pipeline/escopo-regional` | — | — | não | n/a | Escopos regionais identificados e sua evidência. |
| GET | `/api/pipeline/ocr` | limit | — | não | n/a | Versões sem texto e elegibilidade para OCR opcional. |
| GET | `/api/pipeline/parciais` | limit | — | não | n/a | Versões parcialmente extraídas, com decisão de processar páginas restantes. |

## Prazos

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/prazos` | contest_id, group, limit, offset, state | — | não | n/a | Prazos por grupo e estado temporal. |
| GET | `/api/prazos/auditoria` | cause, contest_id, group, limit, offset | — | não | n/a | Auditoria de conflitos de prazo entre documentos/versões. |
| GET | `/api/prazos/calendario` | contest_id, group, limit, offset, state, urgency | — | não | n/a | Calendário de prazos com urgência calculada no servidor. |
| GET | `/api/prazos/caso` | escopo | — | não | n/a | Caso de prazo com evidências e explicação. |
| GET | `/api/prazos/revalidacao` | limit | — | não | n/a | Alvos de revalidação de prazo e política da fonte. |
| GET | `/api/prazos/revalidacao/historico` | contest_id, group, limit, offset | — | não | n/a | Histórico append-only de revalidações. |
| POST | `/api/prazos/revalidacao` | — | limit, apply | sim | condicional | Executa revalidação de prazos; apply=False apenas simula. |
| POST | `/api/prazos/verificar-documento` | — | version_id, contest_id, group, escopo, dry_run, checked_by | sim | condicional | Verifica um documento oficial já armazenado, sem baixar conteúdo novo. |

## Preferências

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/preferencias` | — | — | não | n/a | Preferências operacionais do usuário. |
| POST | `/api/preferencias` | — | reference_municipio, reference_uf, interest_states, practical_distance_km, priority | sim | sim | Atualiza preferências usadas na priorização. |

## Prioridades

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/prioridades` | limit | — | não | n/a | Prioridades operacionais calculadas por política determinística. |

## Questões e desempenho

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/estudos/questoes` | disciplina, incluir_arquivadas, topico | — | não | n/a | Banco de questões. |
| POST | `/api/estudos/questoes` | — | action, id, enunciado, alternativas, gabarito, tipo, comentario, disciplina, topico, dificuldade, tags, fonte, licenca, procedencia, conceito_key | sim | condicional | Cria, atualiza ou arquiva questão; gabarito nunca vai em prova em andamento. |
| GET | `/api/estudos/tentativas` | limit, simulado_id | — | não | n/a | Tentativas registradas. |
| POST | `/api/estudos/tentativas` | — | questao_id, resposta, duracao_segundos | sim | nao | Registra tentativa de prática e corrige no servidor. |
| GET | `/api/estudos/desempenho` | — | — | não | n/a | Desempenho geral, por disciplina e por tópico. |

## Reconciliação de identidade

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/reconciliacao` | contest_id, limit, min_candidates, nature, offset, state | — | não | n/a | Candidatos de reconciliação de identidade de cargo. |
| GET | `/api/reconciliacao/historico` | — | — | não | n/a | Histórico append-only de reconciliações. |
| POST | `/api/reconciliacao` | — | contest_id, label, state, reviewer, reason, role_id, nature, evidence, previous_id, dry_run | sim | sim | Reconcilia rótulo de cargo com identidade canônica. |

## Revisão humana

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/revisao/fila` | conflict, field, limit, min_priority, offset, reviewed_since, reviewed_until, search, source, state, until | — | não | n/a | Fila de propostas para revisão humana. |
| GET | `/api/revisao/grupos` | contest_id, contexto, document_id, field, limit, linha, offset, state, version_id | — | não | n/a | Propostas agrupadas pela identidade da evidência (versão, bloco, offsets). |
| GET | `/api/revisao/pilotos` | — | — | não | n/a | Concursos com linhas de quadro prontas para o piloto de revisão. |
| GET | `/api/revisao/piloto` | contest_id, size | — | não | n/a | Relatório do piloto: fichas, progresso e próximos pendentes. |
| GET | `/api/revisao/identidades` | contest_id | — | não | n/a | Sugestões de identidade cargo+formação, sem criar identidade. |
| GET | `/api/revisao/evidencia/{evidence_id}` | — | — | não | n/a | Trecho literal e contexto da evidência. |
| GET | `/api/revisao/lotes/{batch_id}` | — | — | não | n/a | Estado e progresso de um lote de revisão. |
| GET | `/api/revisao/lotes/{batch_id}/exportar` | — | — | não | n/a | Exporta o lote para decisão offline, com hash de evidência. |
| POST | `/api/revisao/lotes` | — | created_by, size, filters | sim | nao | Abre lote determinístico de propostas pendentes. |
| POST | `/api/revisao/lotes/{batch_id}` | — | action, reviewer, reason | sim | condicional | Fecha/importa lote; não aprova em massa. |
| GET | `/api/revisao/proposta/{proposal_id}` | — | — | não | n/a | Detalhe da proposta, com evidência, hash e histórico de decisões. |
| POST | `/api/revisao/proposta/{proposal_id}` | — | decision, reviewer, reason, value, evidence_sha256, scope_snapshot, lote_id | sim | sim | Decisão humana de um único campo, com hash da evidência vista. |
| POST | `/api/revisao/selecionar` | — | proposal_id, reviewer, reason | sim | sim | Seleciona valor vigente após validação explícita. |
| POST | `/api/revisao/importar` | — | payload, dry_run | sim | sim | Importa decisões de lote de forma transacional e idempotente. |
| GET | `/api/revisao/duplicidades` | contest_id, field, limit | — | não | n/a | Duplicidades textuais candidatas, sem fusão automática. |

## Saúde e prontidão

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/saude` | — | — | não | n/a | Saúde operacional: config, banco, fontes, fila, alertas e último ciclo. |
| GET | `/api/saude/prontidao` | — | — | não | n/a | Relatório único de prontidão do backend com evidência por critério. |

## Simulados

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/estudos/simulados` | limit | — | não | n/a | Lista simulados. |
| POST | `/api/estudos/simulados` | — | modo, nome, limit, duracao_segundos, seed, shuffle, exclude_answered, disciplina, topico, dificuldade, tags | sim | nao | Cria simulado tradicional ou adaptativo sem duplicar questão. |
| GET | `/api/estudos/simulados/{exam_id}` | — | — | não | n/a | Simulado com itens, respostas salvas e tempo restante do servidor. |
| GET | `/api/estudos/simulados/{exam_id}/resultado` | — | — | não | n/a | Resultado corrigido e persistido. |
| GET | `/api/estudos/simulados/{exam_id}/questoes` | — | — | não | n/a | Questões aplicadas, sem gabarito enquanto a prova está em andamento. |
| GET | `/api/estudos/simulados/{exam_id}/resumo` | — | — | não | n/a | Resumo de navegação: posição, marcadas e respondidas. |
| POST | `/api/estudos/simulados/{exam_id}/responder` | — | ordem, resposta | sim | sim | Salva resposta de um item. |
| POST | `/api/estudos/simulados/{exam_id}/marcar` | — | ordem, marcada | sim | sim | Marca/desmarca item para revisão. |
| POST | `/api/estudos/simulados/{exam_id}/posicao` | — | ordem | sim | sim | Salva a posição de navegação. |
| POST | `/api/estudos/simulados/{exam_id}/proxima` | — | — | sim | sim | Avança para a próxima questão adaptativa. |
| POST | `/api/estudos/simulados/{exam_id}/finalizar` | — | — | sim | sim | Finaliza e persiste tentativas uma única vez (idempotente). |

## Triagem

| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |
|---|---|---|---|---|---|---|
| GET | `/api/triagem` | include_seen, limit | — | não | n/a | Triagem de alertas e pendências operacionais. |

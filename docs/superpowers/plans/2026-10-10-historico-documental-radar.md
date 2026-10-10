# Histórico documental do Radar — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Aguarde a revisão do usuário antes de executar. O repositório ainda não tem commits; não criar commits sem pedido explícito.

**Goal:** Corrigir datas do coletor v1 e registrar documentos oficiais versionados com evidências e revisão humana, preservando o contrato da lista de concursos.

**Architecture:** O fluxo v1 continua independente. Migração SQLite aditiva e sincronização explícita criam identidades UUID para concurso/cargo; descoberta restrita à fonte oficial, download por hash, blocos e propostas citáveis, decisões append-only e duas rotas GET novas formam o fluxo documental. Operações administrativas são comandos locais; nenhuma extração aprova fatos.

**Tech Stack:** Python 3, sqlite3, unittest, http.server, HTMLParser, urllib; PDF textual com biblioteca pequena escolhida e versão fixada no incremento de extração; HTML/CSS/JS locais.

**Spec:** `docs/superpowers/specs/2026-10-10-historico-documental-radar-design.md`

## Global Constraints

- `GET /api/concursos` mantém os mesmos 18 campos, significados, ordem e JSON determinístico; `verified_at` refere-se somente ao artigo v1.
- Desconhecido é `null`; zero exige citação inequívoca. Contagem global não se atribui automaticamente a cargo, especialidade ou modalidade.
- Migração `user_version=2` é aditiva, transacional, idempotente e explícita; não altera `concursos`. Sincronização de identidades é operação separada. GET v1 não migra.
- Identidade UUID de concurso/cargo não é inferida por título ou similaridade; alias de URL e reconciliação entre observações requerem confirmação humana.
- Primeira fonte é Guajará-Mirim/RO; rede somente em páginas públicas oficiais autorizadas, sem cookies, credenciais ou catálogos terceiros. Testes usam fixtures e bancos temporários.
- Documento localizado, download íntegro, extração, revisão e cobertura são estados distintos. Retificações não invalidam seleções humanas automaticamente.
- Não executar migração em banco real, rede real, push, publicação ou commit durante o planejamento; execução depende de revisão deste plano. O registro git atual não tem commits.

## Mapa de arquivos

- `radar/collector.py`, `tests/test_collector.py`: validar datas e ordem do período v1 antes de persistir.
- `radar/document_store.py`, `tests/test_document_store.py`: DDL v2, identidades, observações, documentos, versões, tentativas, eventos, blocos, propostas e consultas.
- `radar/document_review.py`, `tests/test_document_review.py`: revisões, seleções correntes e auditorias de cobertura.
- `radar/server.py`, `tests/test_document_api.py`: índice de identidades e detalhes por UUID, ambos GET.
- `radar/document_discovery.py`, `tests/test_document_discovery.py`: links oficiais reconhecidos, procedência, fallback manual.
- `radar/document_download.py`, `tests/test_document_download.py`: política HTTPS/redirect, limites e transferência versionada.
- `radar/document_extract.py`, `radar/document_fields.py`, `tests/test_document_extract.py`, `tests/fixtures/documents/`: blocos HTML/PDF textuais e propostas tipadas.
- `radar/__main__.py`, `tests/test_document_cli.py`: migração, sincronização, registro, download, análise, revisão, seleção e cobertura por comandos explícitos.
- `web/index.html`, `web/app.js`, `web/styles.css`, `tests/test_ui.py`, `README.md`, `docs/AUTONOMOUS_WORK_LOG.md`: apresentação e operação local documentadas.

## Review Focus

1. Período de inscrições impossível/invertido: falha antes de retornar linhas para persistência (Task 1).
2. Banco v1 ainda sem migração ou sincronização: GET documental não modifica arquivo; 503 antes da migração, índice vazio antes da sincronização (Tasks 2–4).
3. Mesmo identificador em fontes distintas e URL nova de documento: UUIDs permanecem distintos; nenhuma mescla por nome/título (Tasks 3 e 5).
4. Redirect para IP privado, host não permitido ou PDF sem texto: nenhum byte externo vira versão/evidência; falha é rastreável (Tasks 6–7).
5. Retificação conflitante, cota global e cobertura anterior: valor corrente anterior permanece; cobertura cai para parcial na projeção quando aparecer documento não auditado (Tasks 8–9).

---

## Incremento A — contrato e persistência sem rede

### Task 1: Validar calendário e ordem no coletor v1

**Files:** Modify `radar/collector.py:158-174`; Test `tests/test_collector.py`.

**Interfaces:** `collect(source_html: str, verified_at: str) -> list[dict]` continua produzindo os mesmos 18 campos. `_period_to_iso(match) -> tuple[str, str]` retorna duas datas ISO válidas ou levanta `ValueError`.

- [ ] **RED:** em `CollectRegistrationContextTest`, variar a fixture oficial com `31 de fevereiro de 2026` e `30 e 10 de julho de 2026`; exigir `ValueError` em ambos e ausência de persistência no fluxo CLI. Conservar teste positivo do período real `10–30/07/2026` e do período numérico.

```python
invalid = self.html.replace('10 e 30 de julho de 2026', '31 e 32 de fevereiro de 2026')
with self.assertRaises(ValueError):
    collector.collect(invalid, VERIFIED_AT)
reversed_period = self.html.replace('10 e 30 de julho de 2026', '30 e 10 de julho de 2026')
with self.assertRaises(ValueError):
    collector.collect(reversed_period, VERIFIED_AT)
```

- [ ] Executar `python -m unittest tests.test_collector -v`; confirmar falha pelo calendário/ordem e não por mudança acidental da fixture.
- [ ] Substituir interpolação sem validação em `_period_to_iso` por `date(int(year), int(month), int(day))` para ambas as pontas; recusar `start > end`, devolver `isoformat()`. Não tocar em `radar/storage.py`.
- [ ] Executar `python -m unittest tests.test_collector tests.test_contract -v` e `python -m unittest discover -s tests -q`; conferir os resultados reais.

### Task 2: Migrar esquema documental em cópia SQLite

**Files:** Create `radar/document_store.py`; Test `tests/test_document_store.py`.

**Interfaces:** `connect_documents(db_path) -> sqlite3.Connection` liga FK por conexão; `migrate_document_schema(db_path) -> None` aceita `user_version` 0/2 e rejeita >2. Criar tabelas do quadro da spec: `concursos_identidade`, `observacoes_concurso`, `cargos_identidade`, `observacoes_cargo`, `documentos`, `documento_urls`, `versoes_documento`, `tentativas_download`, `eventos_documentais`, `blocos_documento`, `evidencias`, `propostas_campo`, `revisoes_campo`, `valores_atuais`, `auditorias_cobertura`; FKs, UNIQUE, CHECK para enumerações e índices de consulta. O DDL não executa backfill.

- [ ] **RED:** criar DB v1 temporário com fixture oficial via `collect`/`upsert_records`; salvar `list_records` e bytes HTTP de `/api/concursos`; migrar duas vezes; exigir igualdade, `PRAGMA integrity_check='ok'`, `foreign_key_check=[]`, `user_version=2` e contagem zero de identidades. Testar DB vazio, versão 3 intacta e erro induzido entre DDLs sem tabelas parciais.

```python
before = list_records(db)
migrate_document_schema(db)
migrate_document_schema(db)
self.assertEqual(list_records(db), before)
with sqlite3.connect(db) as conn:
    self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 2)
    self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])
```

- [ ] Executar `python -m unittest tests.test_document_store -v` e verificar RED pela função ausente.
- [ ] Definir DDL como sequência de statements executados em `BEGIN IMMEDIATE`/`COMMIT` explícitos; não usar `executescript` para essa transação. Criar tabelas com chaves e checagens do contrato, guardar UUID como TEXT e horários UTC ISO com offset; rejeitar esquema existente incompatível e `user_version` futuro antes de escrever. Rollback em exceção.
- [ ] Executar teste focado e suíte completa; inspecionar cópia em banco temporário, nunca executar migração no banco de uso real nesta etapa.

### Task 3: Sincronização explícita de identidades e observações

**Files:** Modify `radar/document_store.py`; Test `tests/test_document_store.py`.

**Interfaces:** `sync_v1_identifiers(db_path) -> None` exige esquema v2, cria uma identidade por par `(source_url, competition_id)` e um cargo por `(observation_id, role)` ainda não sincronizados; não modifica `concursos`. `list_competition_identities(db_path) -> list[dict]` devolve `{id, observations:[{source_url, competition_id}]}`. `get_competition_details(db_path, contest_id: str) -> dict | None` consulta UUID e usa as mesmas identidades; leitura nunca executa sync.

- [ ] **RED:** duas fontes com mesmo `competition_id` devem produzir dois UUIDs; quatro cargos da fixture oficial produzem quatro `role_id`; reaplicar sync preserva IDs; GET/consulta antes de sync não cria identidades. Nome de cargo alterado após coleta v1 (simulado em cópia) não remapeia identidade anterior por similaridade.

```python
sync_v1_identifiers(db)
first = list_competition_identities(db)
sync_v1_identifiers(db)
self.assertEqual(list_competition_identities(db), first)
self.assertEqual(len(first[0]['observations']), 1)
```

- [ ] Executar teste focado para RED; implementar transação que consulta as chaves naturais existentes e insere `uuid4()` para apenas chaves novas, preservando nomes integrais e sem atribuir especialidade não expressa. Concorrência de duas conexões é serializada por transação/UNIQUE e leitura do ID já existente.
- [ ] Executar teste focado e suíte; conferir igualdade de `list_records` antes/depois.

### Task 4: Duas rotas GET documentais e contrato v1 intacto

**Files:** Modify `radar/server.py:89-113`; Test `tests/test_document_api.py`.

**Interfaces:** Consumes `list_competition_identities(db_path)` e `get_competition_details(db_path, contest_id)`. Produces `GET /api/concursos/identidades` (array) e `GET /api/concursos/{contest_uuid}/detalhes` (objeto); UUID inválido 400, inexistente 404; DB sem esquema documental 503 explicativo, nenhum efeito colateral; métodos de escrita 405. JSON detalhado tem `contest`, `roles`, `coverage`, `documents`, `proposals`, `current_values`.

- [ ] **RED:** servidor em porta efêmera: banco v1 sem migração retorna 503 em ambas as rotas, mas bytes da lista v1 iguais antes/depois. Após migração e antes de sync, índice `[]`; após sync, dois IDs de fontes homônimas distintos, detalhe com roles observados e arrays documentais vazios; UUID inválido, UUID ausente, `/identidades/detalhes`, query inesperada e escrita não expõem dados. Garantir que resposta não contém `local_path`.

```python
status, _, body = request('GET', '/api/concursos/identidades')
self.assertEqual(status, 200)
contest_id = json.loads(body)[0]['id']
status, _, body = request('GET', f'/api/concursos/{contest_id}/detalhes')
self.assertEqual(json.loads(body)['coverage']['state'], 'nao_auditada')
```

- [ ] Executar `python -m unittest tests.test_document_api -v` para RED.
- [ ] Implementar roteamento por `urlsplit`, UUID canônico por `uuid.UUID`, sem decodificar barra para transformar segmento em rota; serializar campos previstos e mapear erros de schema para 503 sem auto-migração. Manter `_serve_api` v1 idêntico.
- [ ] Executar teste focado, `tests.test_contract` e suíte completa. Comparar bytes v1 no mesmo processo antes/depois de migração/sync.

## Incremento B — histórico, descoberta e aquisição

### Task 5: Documento, versão íntegra e evidência auditável

**Files:** Modify `radar/document_store.py`; Test `tests/test_document_store.py`.

**Interfaces:** `register_document(db_path, candidate: dict) -> str` recebe `observation_id`, `kind`, `official_url`, `title`, `discovery_url`, `discovery_method`, `discovered_at`, metadados opcionais (`role_id`, `issuer`, `published_at`, `source_identifier`); `record_version(db_path, document_id: str, content: bytes, metadata: dict) -> str` recebe `fetched_at`, `fetched_url`, `content_type`, `published_at` opcional; `record_analysis(db_path, version_id: str, blocks: list[dict], proposals: list[dict]) -> None` grava bloco/evidência/proposta em transação. `get_competition_details` projeta documentos, versões, eventos, tentativas e propostas. A raiz de artefatos fica ao lado do banco em diretório próprio, com caminhos relativos e nomes SHA-256.

- [ ] **RED:** registrar mesmo candidato duas vezes preserva ID; mesma URL em outra observação do **mesmo** concurso não duplica/mescla documento indevidamente; URL diferente com mesmo título não mescla; mesmo SHA retorna mesma versão, bytes diferentes criam versão adicional. Falha de escrita/entrada de proposta inválida não deixa versão ou blocos parciais; evidência cuja `quote` não coincide com `text[start_offset:end_offset]` falha. Role de outro concurso é recusado, escopo global permanece `role_id=None`. Testar duas conexões concorrentes em registro idempotente.

```python
document_id = register_document(db, candidate)
self.assertEqual(register_document(db, candidate), document_id)
v1 = record_version(db, document_id, b'primeiro', metadata)
self.assertEqual(record_version(db, document_id, b'primeiro', metadata), v1)
self.assertNotEqual(record_version(db, document_id, b'segundo', metadata), v1)
```

- [ ] Executar teste focado para RED; implementar URLs normalizadas para comparação (host minúsculo, sem fragmento, caminho preservado), FKs e consulta transacional por identidade. Alias permanente requer ação humana explícita; redirects ficam em `final_url`/`fetched_url`, sem mesclar por título. Gravar bytes em arquivo temporário próprio, fsync/rename atômico e commit apenas quando íntegros; limpar apenas temporários próprios em erro. Proposta só aceita campos em lista branca, tipo de valor coerente, vínculo com bloco/versão e evidência exata.
- [ ] Executar teste focado, API e suíte; conferir que a rota de detalhe contém metadados, nunca caminho de arquivo ou bytes brutos.

### Task 6: Descoberta oficial e download protegido

**Files:** Create `radar/document_discovery.py`, `radar/document_download.py`, `tests/test_document_discovery.py`, `tests/test_document_download.py`, `tests/fixtures/documents/guajara-links.html`.

**Interfaces:** `discover_documents(article_html: str, article_url: str, observation_id: str) -> list[dict]` devolve candidatos da Task 5; `register_manual_url(db_path, observation_id, kind, official_url, title) -> str` recusa URL não autorizada. `download_document(db_path, document_id: str, transport=None) -> str` grava tentativa/evento e retorna ID de versão íntegra. Transporte injetável recebe URL/timeout/limite e produz status, headers, URL final, chunks e IP conectado; política permite apenas HTTPS público/rotas oficiais configuradas, <=3 redirects, timeout 15 s, <=20 MiB.

- [ ] **RED:** fixture de links reais/sintéticos com edital, retificação, relativo, duplicado, terceiro, âncora vazia e link irrelevante; exigir procedência e `[]` quando nenhum link verificável. Transporte falso exercita HTML/PDF válido, 404/timeout, MIME inválido, >20 MiB, redirecionamento circular, externo, IP loopback/privado/link-local, DNS público mas peer privado e documento com SHA novo; em toda falha, versão anterior e `verified_at` v1 persistem, tentativa e erro ficam registrados.

```python
candidates = discover_documents(html, article_url, observation_id)
self.assertEqual({c['kind'] for c in candidates}, {'edital', 'retificacao'})
old = download_document(db, document_id, transport=fake_ok)
with self.assertRaises(ValueError):
    download_document(db, document_id, transport=fake_private_peer)
self.assertEqual(get_competition_details(db, contest_id)['documents'][0]['versions'][0]['id'], old)
```

- [ ] Executar testes focados para RED; usar HTMLParser para links/contexto, URL relativa via `urljoin`, whitelist de host/rotas aprovada na implementação. Desabilitar redirects implícitos; validar cada hop, DNS resolvido e peer efetivo antes de ler bytes (se o transporte não expõe peer verificável, falhar fechado). Limitar streaming, tempo e MIME, fechar resposta em erro; não enviar cookies. Registre tentativa concluída/falha sem rebaixar documento já baixado.
- [ ] Executar testes focados e suíte completa sem rede real. Verificar condições de acesso publicadas antes de habilitar chamadas reais em incremento posterior.

## Incremento C — interpretação, revisão e uso local

### Task 7: Blocos HTML/PDF e propostas com citação

**Files:** Create `radar/document_extract.py`, `radar/document_fields.py`, `tests/test_document_extract.py`, `tests/fixtures/documents/edital.html`, `tests/fixtures/documents/edital-textual.pdf`, `tests/fixtures/documents/invalido.pdf`; Modify `radar/document_store.py` para estado de extração.

**Interfaces:** `extract_blocks(content: bytes, content_type: str) -> list[dict]` retorna `page_number` (PDF base 1, HTML null), `locator`, `start_offset`, `end_offset`, `text`. `extract_field_proposals(blocks: list[dict], version_id: str, contest_id: str, role_id: str | None = None) -> list[dict]` produz `field_name`, `value_json`, `value_type`, `extraction_method`, `ambiguity_reason`, `evidence` (`block_index`, `quote`, offsets). `record_analysis` persiste transacionalmente; PDFs sem texto/criptografados/inválidos não geram proposta.

- [ ] **RED:** fixture HTML/PDF textual com trecho específico e página; `quote == block['text'][start:end]`, zero somente quando explícito, cota global com `role_id=None`, datas impossíveis/invertidas rejeitadas, cota racial genérica não rebatizada indígena. PDF digitalizado sem texto, criptografado, malformado, muitas páginas e tamanho excessivo marcam extração falha ou parcial sem criar fatos/valor corrente.

```python
for proposal in proposals:
    evidence = proposal['evidence']
    block = blocks[evidence['block_index']]
    self.assertEqual(block['text'][evidence['start_offset']:evidence['end_offset']], evidence['quote'])
self.assertTrue(all(p['role_id'] is None for p in global_proposals))
```

- [ ] Executar teste focado para RED; avaliar capacidade/licença da biblioteca PDF textual, registrar decisão e pin de versão antes de instalar. Implementar limite de bytes/páginas/tempo, HTML textual com locator e parsing conservador por padrões inequívocos, validação com `datetime.date`; diagnósticos de texto ausente em evento e `extraction_state` apropriado. Sem OCR implícito.
- [ ] Executar teste focado e suíte, confirmar que análise `parcial` não significa edital integralmente interpretado.

### Task 8: Revisão humana, seleção corrente e cobertura

**Files:** Create `radar/document_review.py`, `tests/test_document_review.py`; Modify `radar/document_store.py` para projeção de decisões.

**Interfaces:** `review_proposal(db_path, proposal_id: str, decision: str, reviewer: str, reason: str) -> str`; `select_current_value(db_path, proposal_id: str, reviewer: str, reason: str) -> str`; `record_coverage(db_path, contest_id: str, state: str, checked_urls: list[str], reviewer: str, checked_at: str, note: str) -> str`. Seleção exige última revisão validada, evidência válida e cargo do mesmo concurso; gera `supersedes_id` da seleção anterior. Cobertura auditada exige URLs oficiais inspecionadas, revisão humana e instante.

- [ ] **RED:** proposta extraída não é validada; rejeição preserva revisões anteriores; sem reviewer/razão/evidência ou cargo errado não seleciona. Retificação conflitante não altera valor corrente, nova escolha humana gera histórico de duas seleções e cadeia `supersedes_id`; campo global não se replica. `auditada_ate` sem URLs/autor falha; ao surgir documento novo após auditoria, projeção torna-se `parcial` e evento anterior fica intacto.

```python
self.assertEqual(get_competition_details(db, contest_id)['current_values'], [])
review_proposal(db, proposal_id, 'validado', 'revisor-local', 'edital conferido')
select_current_value(db, proposal_id, 'revisor-local', 'escolha fundamentada')
self.assertEqual(get_competition_details(db, contest_id)['current_values'][0]['proposal_id'], proposal_id)
```

- [ ] Executar teste focado para RED; implementar append-only com validação transacional, escopo e valores tipados, projeção determinística por `(selected_at, id)`; eventos de revisão sem sobrescrever evidências/valores prévios. Cobertura só afirma páginas listadas e instante, não ausência de futuros links.
- [ ] Executar teste focado, API e suíte completa.

### Task 9: CLI explícita, interface de leitura e documentação

**Files:** Modify `radar/__main__.py`, `web/index.html`, `web/app.js`, `web/styles.css`, `README.md`, `docs/AUTONOMOUS_WORK_LOG.md`; Create `tests/test_document_cli.py`; Modify `tests/test_ui.py`, `tests/test_document_api.py`.

**Interfaces:** `python -m radar documents-migrate --db PATH` e `documents-sync --db PATH` chamam Task 2/3; `documents-register --db PATH --observation-id ID --kind edital|retificacao|outro --url URL --title TEXT`; `documents-fetch --db PATH --document-id ID`; `documents-analyze --db PATH --version-id ID`; `documents-review --db PATH --proposal-id ID --decision validado|rejeitado --reviewer NAME --reason TEXT`; `documents-select --db PATH --proposal-id ID --reviewer NAME --reason TEXT`; `documents-coverage --db PATH --contest-id ID --state parcial|auditada_ate --checked-url URL --reviewer NAME --checked-at ISO --note TEXT`. UI consome lista v1 e índice de identidades para ligar cartão a `GET /api/concursos/{contest_uuid}/detalhes`.

- [ ] **RED:** comandos `documents-migrate/sync` são explícitos e idempotentes; `collect`/`serve` não migram. Estados sem documento, localizado, baixado, extração parcial, proposta pendente/validada e erro HTTP exibem mensagens distintas; proposta só mostra campo com citação/versão; `nao_auditada` não é cobertura total; uma nova retificação rebaixa projeção de cobertura a parcial. Link/trecho hostil é renderizado com `textContent`, sem `innerHTML`, URL HTTP não vira link. UI lida com índice vazio e detalhes 503 sem sumir com cartão v1.

```python
self.assertEqual(set(api_v1_record), set(CONTRACT_FIELDS))
self.assertEqual(detail['coverage']['state'], 'nao_auditada')
self.assertNotIn('local_path', json.dumps(detail))
```

- [ ] Executar `python -m unittest tests.test_document_cli tests.test_ui tests.test_document_api -v` para RED; implementar comandos sem side effects implícitos, ligação UI por par `(source_url, competition_id)` das observações, renderização DOM segura, estados recuperáveis. Atualizar README com comandos, limites, backup/rollback e significado de estados; registrar evidência de testes no log.
- [ ] Executar focados e `python -m unittest discover -s tests -v`; inspecionar `git status --short --branch` e candidatos a versionamento, sem adicionar DB, bytes documentais, segredos ou executar rede real como teste. Conferir resposta v1 byte a byte contra snapshot anterior; relatar limites da fonte e cobertura.

## Portões entre incrementos

- A só termina quando a correção de datas e migração idempotente passaram em cópia v1, identidades permaneceram estáveis e lista v1 ficou byte a byte intacta.
- B só inicia com contrato A estável; requisição real exige validação de domínio/rotas/condições de acesso. Download sem peer verificável falha fechado.
- C só usa bytes íntegros versionados. Campo e cobertura correntes exigem decisão humana; PDF sem texto permanece sem fatos.

## Auto-revisão e handoff

- Confirmar correspondência da spec para todas as tabelas, estados, URLs, identidades, rotas, extração, revisão e cobertura antes da execução.
- O plano substitui a rota antiga baseada em `source_url` pelo UUID, prevê índice estável, datas como primeiro incremento e tentativas de download persistidas.
- Em tarefas de implementação, usar TDD, revisar diff e resultados reais a cada portão; seguir proibição de commits sem pedido explícito neste repositório sem histórico.

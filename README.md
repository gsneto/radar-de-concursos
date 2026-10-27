# GSN Concursos

O GSN Concursos é uma ferramenta para **coletar, organizar e analisar** informações sobre concursos públicos brasileiros. Ele reúne dados de uma fonte oficial em um banco local, guarda o **histórico dos documentos** (editais, retificações e versões) e extrai **fatos com evidência** — sempre como propostas que passam por **revisão humana explícita** antes de serem consideradas confirmadas.

O foco do projeto é a **rastreabilidade**: cada informação pode ser rastreada até o documento, a versão e o trecho que a originaram.

## O que o Radar faz

- Coleta informações de uma fonte oficial configurada.
- Organiza concursos e cargos em um banco SQLite local.
- Registra, baixa e analisa documentos HTML e PDF textual.
- Mantém o histórico de versões de cada documento, por conteúdo.
- Extrai propostas de fatos (vagas, datas, locais, escolaridade) com citação de evidência.
- Associa retificações ao documento original.
- Identifica conflitos entre propostas do mesmo campo e escopo.
- Permite revisar propostas e selecionar explicitamente o valor corrente.
- Monitora as fontes oficiais em busca de novas publicações e alterações, com um comando que pode ser agendado no Windows.
- Oferece uma interface web para consultar concursos e o histórico documental.

A extração gera **propostas que exigem revisão**; nada é confirmado automaticamente. O suporte atual é limitado às fontes e aos formatos configurados.

## Tecnologias

Python 3 (biblioteca padrão), SQLite, HTML/CSS/JavaScript sem dependências de frontend e `pypdf` para PDF textual.

## Pré-requisitos

- Python 3.9 ou superior (testado com Python 3.12).
- Acesso à internet para a coleta da fonte oficial.
- `pypdf`, instalado a partir de `requirements.txt`.

Os comandos abaixo usam PowerShell (Windows). Em outros sistemas, use os comandos equivalentes do seu shell.

## Instalação

Na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Como executar

1. Crie a pasta de dados (o SQLite não cria diretórios):

```powershell
New-Item -ItemType Directory -Path .\data -Force
```

2. Colete a fonte oficial pela primeira vez:

```powershell
python -m radar collect --db .\data\radar.sqlite3
```

3. Inicie o servidor local:

```powershell
python -m radar serve --db .\data\radar.sqlite3
```

4. Abra a interface no navegador:

```
http://127.0.0.1:8000/
```

5. Encerre o servidor com `Ctrl+C`.

O servidor escuta em `127.0.0.1:8000` por padrão. `collect` atualiza a fonte sob demanda e não duplica os cargos; se a página mudar ou estiver indisponível, a coleta falha sem apagar os registros anteriores. Para abrir a interface sem dados, aponte `serve` para um banco ainda inexistente.

## Monitoramento

Um ciclo de monitoramento consulta as fontes oficiais, registra documentos novos, compara os conhecidos e sinaliza alterações — sem confirmar nada automaticamente:

```powershell
python -m radar documents-migrate --db .\data\radar.sqlite3
python -m radar monitor --db .\data\radar.sqlite3
```

O ciclo termina sozinho (não fica em loop) e imprime um resumo em JSON. A interface mostra o estado do último ciclo em `/api/monitoramento`. Para rodar periodicamente, use o Agendador de Tarefas do Windows — instruções em [`docs/MONITORING_SCHEDULING.md`](docs/MONITORING_SCHEDULING.md).

## Operacao autonoma

Um **ciclo operacional** unico reune coleta, fila documental, alertas e saude, controlado por uma configuracao central (`radar_ops.json`, exemplo em `radar_ops.json.example`):

```powershell
python -m radar ops-config --write          # grava radar_ops.json com os defaults
python -m radar ops-ciclo --limit 10        # coleta + reconcilia + fila em lote + alertas
python -m radar ops-saude                   # saude real (config, banco, ciclos, fila, alertas)
python -m radar ops-alertas --unseen        # alertas persistentes
python -m radar ops-triagem                 # central de triagem (grupos por concurso/prazo)
python -m radar ops-identidade              # registra a identidade de app (atalho/AUMID)
python -m radar ops-notificar               # despacha notificacoes nativas elegiveis
python -m radar ops-prioridades             # ranking explicavel de oportunidades
python -m radar ops-preferencias            # mostra/atualiza preferencias geograficas
python -m radar estudos-painel              # painel de estudos (progresso, tempo, revisoes)
python -m radar estudos-sessao start --modo pomodoro   # cronometro de estudo
python -m radar estudos-conteudo --concurso ID         # conteudo programatico extraido
python -m radar estudos-cobertura --concurso ID        # cobertura de preparacao e lacunas
python -m radar estudos-exportar --out estudos.json    # exporta os dados pessoais
python -m radar estudos-flashcard fila                 # fila de flashcards para revisar
python -m radar estudos-simulado create --nome "S1" --limit 10
python -m radar estudos-desempenho                     # desempenho agregado
```

**Agendamento (Windows):** `pwsh -File .\scripts\install_tasks.ps1` registra a tarefa "GSN Concursos - Ciclo" (a cada 6 h, sem sobrepor execucoes, recuperando apos reinicio), usando o Python do `radar_ops.json` e a conta do usuario, **sem senha armazenada**. `verify_tasks.ps1` mostra estado/proxima execucao; `uninstall_tasks.ps1` remove as tarefas **sem apagar dados**. O servidor local (loopback) pode ser iniciado por `pwsh -File .\scripts\serve.ps1`.

Alertas persistentes (novo candidato, documento recuperado, retificacao, fonte indisponivel, prazo de isencao proximo/expirado) ficam no banco e aparecem na secao **Alertas** da interface, que se atualiza periodicamente. `GET /api/alertas` e `GET /api/saude` expoem os dados. Ver [`docs/superpowers/specs/2026-10-16-autonomous-operation-design.md`](docs/superpowers/specs/2026-10-16-autonomous-operation-design.md).

**Notificacoes nativas e central de triagem:** alertas criticos/oportunidades podem virar **notificacoes nativas do Windows** (toast WinRT com identidade `RadarDeConcursos.Radar`; `scripts/install_app_identity.ps1` registra o atalho/AUMID). O canal e **opcional** (`notifications.local`, padrao `false`) e, quando ligado, aplica dedup por evento, severidade minima, categorias e limite por ciclo (`max_per_cycle`), retomando o excedente nos ciclos seguintes. A **central de triagem** (`GET /api/triagem`, `#triage-panel`) agrupa alertas **apenas por `contest_id` provado** (nunca por semelhanca de titulo), ordena por prazo documentado e oferece acoes reais (`POST /api/alertas/<id>`: visto/dispensar/adiar/reabrir) que **preservam historico e documentos**. Ver [`docs/superpowers/specs/2026-10-16-windows-notifications-triage-design.md`](docs/superpowers/specs/2026-10-16-windows-notifications-triage-design.md).

**Priorizacao geografica e ranking explicavel:** a secao **Priorizacao de oportunidades** (`#priorities-panel`) ordena os concursos por uma pontuacao **deterministica e explicavel** (`GET /api/prioridades`), mostrando **prova, lotacao e abrangencia separadas**, a distancia da prova como **geografica (linha reta)** - nunca rodoviaria -, vagas indigenas imediatas **separadas** do cadastro de reserva, e o motivo de cada fator. Uma oportunidade **distante** com muitas vagas indigenas e compatibilidade formal confirmada continua visivel (piso excepcional); a **urgencia** de prazo aparece a parte e nao torna um cargo incompativel uma boa oportunidade. As preferencias do usuario (municipio/UF de referencia, estados de interesse como BA/PE, faixa de distancia pratica) ficam em `radar_ops.json` (**ignorado pelo Git**), sao editaveis por `GET/POST /api/preferencias` ou `ops-preferencias`, e **nao** sao enviadas a servicos externos. A localizacao vem **apenas de evidencia documental** (nunca inferida do orgao, da capital ou da lotacao). Ver [`docs/superpowers/specs/2026-10-16-geographic-ranking-design.md`](docs/superpowers/specs/2026-10-16-geographic-ranking-design.md).

**Estudos:** a secao **Estudos** (`#study-panel`) reune disciplinas e topicos, um **cronometro** (livre ou Pomodoro), o registro de **sessoes de estudo** persistidas, o **progresso por topico** (isolado por edital) e a **revisao espacada** (`GET/POST /api/estudos/*`, CLI `estudos-*`). O painel deriva tudo de dados **persistidos** (nunca de exemplos ficticios) e continua funcionando apos reiniciar. Os dados de estudo sao **pessoais**: ficam em tabelas proprias (schema v10/v11), nao entram no contrato v1 nem sao enviados as fontes. Parte da logica foi **adaptada de codigo open source MIT** (ver [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) e [`docs/superpowers/specs/2026-10-16-study-platform-open-source-mining.md`](docs/superpowers/specs/2026-10-16-study-platform-open-source-mining.md)); nenhuma dependencia nova foi adicionada (stdlib-only).

**Conteudo programatico, perfil de conhecimento e preparacao:** a secao **Preparacao e conteudo programatico** (`#prep-panel`, `#perfil-panel`) extrai o **conteudo programatico** dos editais (disciplinas/topicos/subtopicos) **com evidencia** (pagina e trecho, revisavel) reutilizando o pipeline documental; mantem um **perfil editavel de conhecimentos** (familiaridade declarada, separada de progresso e desempenho); e calcula a **cobertura de preparacao** de forma explicavel (`GET /api/estudos/conteudo`, `/preparacao`, `/perfil`, `POST /api/estudos/lacuna`). Uma lacuna pode ser **enviada para o plano de estudos** (idempotente). Os **dados pessoais de estudo** podem ser **exportados/importados** (`GET /api/estudos/exportar`, `POST /api/estudos/importar`, CLI `estudos-exportar|importar`) e o banco pode receber **backup consistente** (`estudos-backup`, via API do SQLite com verificacao de integridade). A cobertura **nao** e probabilidade de aprovacao nem se mistura com a compatibilidade formal do cargo. Ver [`docs/superpowers/specs/2026-10-16-syllabus-knowledge-preparation-design.md`](docs/superpowers/specs/2026-10-16-syllabus-knowledge-preparation-design.md).

**Pratica: flashcards, questoes e simulados:** a secao **Pratica** (`#fc-panel`, `#q-panel`, `#exam-panel`, `#perf-panel`, `#pac-panel`) permite criar e revisar **flashcards** (agendamento SM-2-lite adaptado de projeto MIT, ver [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)) com **imagem** validada por assinatura (PNG/JPEG/GIF/WebP; SVG recusado) e servida por rota propria com `nosniff`; cadastrar e responder **questoes** (com **versao** preservada: editar nao reescreve tentativas antigas); e montar **simulados** com cronometro **calculado no servidor**, respostas salvas progressivamente, **mapa de questoes**, pulo entre questoes, **marcacao para revisao**, retomada na posicao salva e confirmacao de brancos antes de finalizar. Modos **tradicional**, **adaptativa**, **revisao de erros** e **personalizada**: a selecao adaptativa e deterministica e **explicavel** (fatores e motivos por questao), declara **confianca baixa** com menos de 3 tentativas e avisa que o percentual **nao e comparavel** ao de um simulado de conjunto fixo. O **gabarito nao e revelado** antes da resposta nem em prova em andamento. Ha **desempenho** agregado com denominador explicito (brancos contam no simulado finalizado, e isso e informado) - percentual de acerto **nao** e probabilidade de aprovacao e **nao** sobrescreve o perfil declarado. **Pacotes** `radar-pacote` v1 (JSON + ZIP) permitem previa e importacao nao destrutiva e idempotente, com defesa contra **Zip-Slip** e **zip bomb**; licenca desconhecida entra como **nao verificada** e nao deve ser redistribuida. API `/api/estudos/flashcards|questoes|tentativas|simulados|desempenho|midia|pacotes`; CLI `estudos-flashcard|questao|simulado|desempenho|pacote`. Nenhum conteudo de terceiros foi importado. Ver [`docs/superpowers/specs/2026-10-17-advanced-practice-navigation-media-adaptive-packages-design.md`](docs/superpowers/specs/2026-10-17-advanced-practice-navigation-media-adaptive-packages-design.md).

## Fontes oficiais

- **Prefeitura de Guajará-Mirim/RO (SEMED)** — artigo oficial com o resumo do concurso (base do contrato v1 de 18 campos).
- **Diário Oficial da União — Seção 3 (Imprensa Nacional)** — segunda fonte, independente e federal: descobre editais, retificações e avisos de concursos na edição diária pública (`https://www.in.gov.br/leiturajornal`). O adaptador registra documentos com proveniência e histórico, sem alterar os 18 campos de `GET /api/concursos`. Ver [`docs/superpowers/specs/2026-10-16-fonte-oficial-2-design.md`](docs/superpowers/specs/2026-10-16-fonte-oficial-2-design.md).
- **FGV Conhecimento** — terceira fonte: catálogo público de concursos (`https://conhecimento.fgv.br/concursos`) com identidade por concurso (slug) e recuperação dos documentos publicados (edital, retificações, resultados). Segue os links documentais das páginas, inclusive para concursos já conhecidos (revisão incremental). Ver [`docs/superpowers/specs/2026-10-16-fgv-source-design.md`](docs/superpowers/specs/2026-10-16-fgv-source-design.md).
- **Quadrix** — quarta fonte oficial: banca com páginas server-rendered (`https://www.quadrix.org.br/informacoes/<id>/`) e **documentos públicos** (edital, retificações, anexos, comunicados) em `anexos-r2.selecao.net.br`. Recupera editais completos com hash e proveniência. Ver [`docs/superpowers/specs/2026-10-16-official-confirmation-expansion-design.md`](docs/superpowers/specs/2026-10-16-official-confirmation-expansion-design.md).
- **IBFC (Instituto Brasileiro de Formação e Capacitação)** — quinta fonte, **oficial e piloto da Fase 27**: catálogo `https://concursos.ibfc.org.br/index/{1|abertos}` e detalhe `/informacoes/<id>/`, com identidade **por certame** (`ibfc-<id>`) e documentos publicados (edital, retificações, convocações, resultados). Anexos em `anexos-r2.selecao.net.br` são baixados; anexos em `anexos.cdn.selecao.net.br` têm `robots.txt` com `Disallow: /` e são registrados **apenas com metadados**, sem cópia local. Ver [`docs/superpowers/specs/2026-10-17-identidade-canonica-container-fonte-design.md`](docs/superpowers/specs/2026-10-17-identidade-canonica-container-fonte-design.md).
- **PCI Concursos (MCP)** — canal **complementar de descoberta** (agregador não oficial), via servidor MCP público (`https://mcp.pciconcursos.com.br/mcp`). Registra candidatos com proveniência e metadados mínimos, distinguíveis de concursos confirmados; a confirmação documental continua exigindo fonte oficial e revisão humana. Ver [`docs/superpowers/specs/2026-10-16-pci-mcp-discovery-design.md`](docs/superpowers/specs/2026-10-16-pci-mcp-discovery-design.md).

Cada documento é classificado por **tipo** (`edital_abertura`, `edital_retificado`, `retificacao`, `anexo`, `cronograma`, `comunicado`, `resultado`, `convocacao`, `homologacao`, `gabarito`, `prova`, `pagina_concurso`, `outro`) além do bucket de armazenamento (`kind`). Uma página oficial não é contada como edital processado se nenhum arquivo correspondente foi recuperado.

## Extração de vagas por cargo

Quadros de vagas (HTML ou PDF textual) são lidos por **cabeçalho**, com colunas mapeadas independentemente da ordem: `CARGO`, vagas imediatas, indígenas e cadastro de reserva. Cada número vira uma **proposta com evidência** (trecho, cabeçalho, página) e **exige revisão humana** — nada é confirmado automaticamente. Regras: célula vazia permanece **desconhecida** (não vira `0`); `CR` sem número **não** vira zero nem vaga imediata; um total global **não** é replicado por cargo. Cargos do documento podem virar identidade própria com `python -m radar documents-role` e ser reconciliados com `documents-reconcile`. Ver [`docs/superpowers/specs/2026-10-16-extracao-vagas-dou-design.md`](docs/superpowers/specs/2026-10-16-extracao-vagas-dou-design.md).

Os editais da **Quadrix** usam um layout próprio (cabeçalho de duas linhas com modalidades repetidas `AC PCD PN PI PQ …`, linhas `código rótulo <imediatas> <reserva> <total>`), tratado por uma estratégia específica (`radar/quadrix_tables.py`) usada junto ao extrator genérico. A coluna `PI` = pessoas indígenas; a célula `-` é zero explícito e a soma é conferida contra o total. Ver [`docs/superpowers/specs/2026-10-16-quadrix-vacancy-extraction-reconciliation-design.md`](docs/superpowers/specs/2026-10-16-quadrix-vacancy-extraction-reconciliation-design.md).

Vagas indígenas são separadas em **imediatas** (`indigenous_vacancies`) e **cadastro de reserva** (`indigenous_reserve_vacancies`) — nunca confundidas. Cargos podem ser identificados pelo **código oficial** da banca (`ensure_role(..., code=...)`, identidade contextualizada pelo concurso) e reconciliados com a tabela HTML do certame. Os requisitos de formação (Anexo II) geram `education`, `accepted_courses` e `si_compatibility` (compatibilidade com o bacharelado em Sistemas de Informação), sempre pendentes de revisão. Blocos de código agrupados (`CÓDIGOS 200 ATÉ 206`, `400 A 403`, listas) são expandidos e associados por código; **seções numeradas sem código** (`3.2 PROFESSOR IV – ARTE` + `3.2.1 Requisitos:`) são associadas por **nome de seção** (nunca por escolaridade); um **documento lógico** reconstrói seções cujo cabeçalho e requisitos ficam em páginas diferentes, mantendo a evidência ancorada à página de origem; um complemento genérico lê requisitos declarados por rótulo (multibanca). Os **prazos de isenção da taxa** são extraídos do cronograma em campos distintos (`exemption_start`, `exemption_end`, `exemption_result_preliminary`, `exemption_appeal`, `exemption_result_final`), separados do prazo de inscrição/pagamento. Ver [`docs/superpowers/specs/2026-10-16-cross-page-requirements-design.md`](docs/superpowers/specs/2026-10-16-cross-page-requirements-design.md), [`docs/superpowers/specs/2026-10-16-section-based-requirements-design.md`](docs/superpowers/specs/2026-10-16-section-based-requirements-design.md), [`docs/superpowers/specs/2026-10-16-grouped-codes-education-design.md`](docs/superpowers/specs/2026-10-16-grouped-codes-education-design.md) e [`docs/superpowers/specs/2026-10-16-indigenous-reserve-and-role-identity-design.md`](docs/superpowers/specs/2026-10-16-indigenous-reserve-and-role-identity-design.md).

## Fila de confirmação documental

Candidatos descobertos (ex.: PCI) entram numa **fila persistente e retomável** que procura referências oficiais, registra documentos com proveniência e mantém a descoberta separada da confirmação:

```powershell
python -m radar confirmacao-status --db .\data\radar.sqlite3
python -m radar confirmacao-lote --db .\data\radar.sqlite3 --limit 10
python -m radar confirmacao-reconciliar --db .\data\radar.sqlite3
python -m radar confirmacao-metricas --db .\data\radar.sqlite3
python -m radar confirmacao-prioridades --db .\data\radar.sqlite3 --limit 20
python -m radar confirmacao-oportunidades --db .\data\radar.sqlite3 --contest-id <uuid>
```

Estados vão de `pendente` a `documento_processado`/`revisao_pendente`/`nao_localizado`/`inconclusivo`. A API expõe `GET /api/confirmacao`; `confirmacao-metricas` separa candidatos selecionados, páginas localizadas, documentos recuperados, editais, anexos, retificações e propostas (uma página e um PDF não são duas oportunidades; propostas não são valores validados). Nada é promovido a valor validado sem revisão humana; `nao_localizado` não significa que o concurso seja falso. Ver [`docs/superpowers/specs/2026-10-16-official-confirmation-queue-design.md`](docs/superpowers/specs/2026-10-16-official-confirmation-queue-design.md).

## Pipeline documental

A seção **Pipeline documental** (`#pipeline-panel`) mostra o caminho real de cada documento: descoberto → baixado → validado → classificado → extraído → propostas → revisão. Baixado não é extraído; extraído não é confirmado. Cada documento aparece com o **primeiro bloqueio** e o motivo (`sem_versao`, `nao_iniciada`, `sem_texto`, `paginas_excedidas`, `falhou`, `sem_propostas`, `associacao_pendente`), nunca como “sem dados”.

A extração declara o que fez: `extract_document()` devolve blocos, `truncated`, `total_pages`, `limitation` e `extractor_version`, com códigos estáveis (`pdf_sem_texto`, `pdf_paginas_excedidas`, `pdf_criptografado`, `extrator_indisponivel`). PDFs muito longos (listas de resultado com 3.000 páginas) são lidos no **prefixo de 40 páginas**, com a limitação gravada no evento de análise; o restante não é processado. A versão do extrator fica registrada para rastrear mudanças de comportamento.

Por concurso, a cobertura é **exclusiva e explícita**: `sem_documento`, `documento_sem_texto`, `documento_nao_extraido`, `texto_sem_campo`, `campo_candidato`, `proposta_sem_campo_decisivo`, `campo_confirmado`. Percentuais sempre com o denominador indicado.

**Deduplicação:** propostas idênticas dentro da mesma versão (mesmo escopo, campo, valor, bloco e citação) não são gravadas. Duplicidades históricas **não** são apagadas: `pipeline-duplicados` lista para decisão humana.

**OCR opcional (Fase 31):** `ocr-pendentes` mede a necessidade e informa o motor; `ocr-executar --version-id … --pages 1,2 [--apply]` reconhece texto com o motor local disponível (no Windows, `Windows.Media.Ocr` com modelo `pt-BR`, sem instalar nada; Tesseract é suportado se existir). O PDF **original nunca é alterado** e o texto reconhecido vira **camada derivada** (blocos + propostas marcadas com `ocr:` e o motivo "conferir no documento original"). Limites: 20 páginas por chamada, DPI 72–400, timeout por página, 40 MiB por imagem. Sem motor ou sem modelo, a recusa é explícita (`ocr_indisponivel`/`ocr_modelo_ausente`) e o documento continua `pdf_sem_texto`.

**Quadro de vagas agregado:** quando o edital publica um **total** que já soma modalidades (ex.: IBFC, `Total de Vagas (Ampla, Negros e PCD)`), o Radar grava `vagas_total_publicado` e **não** distribui por ampla, negros, PCD ou indígenas — dividir por percentual seria inventar a abertura. Divergência entre a soma das linhas e o TOTAL vira conflito declarado na evidência. O extrator genérico foi protegido contra mapear cabeçalho agregado para vagas imediatas.

**Requisitos inline:** `Requisito:` em texto corrido é extraído com o cargo do cabeçalho imediatamente anterior no **mesmo bloco**; sem cargo, o item diz "requisito sem cargo identificado". Cursos citados viram `accepted_courses` e a compatibilidade com Sistemas de Informação é **candidata**, sempre com trecho literal — nunca parecer jurídico.

**Duplicidades:** `revisao-duplicados` separa **duplicidade textual** (mesmo trecho e mesmo valor) de **repetição legítima** (mesmo valor em trechos diferentes, como sumário e corpo). Nada é apagado; rejeitar a redundante é decisão humana. A prioridade ganhou fatores declarados: vaga indígena (+4), formação/SI (+3) e duplicata (+1).

**OCR:** `ocr-pendentes` mede a necessidade (`pagina_imagem`, `texto_vetorial_sem_camada_de_texto`, `sem_texto_sem_imagem`) e informa a disponibilidade do motor. Nenhum OCR roda sem motor com modelo português; instalar Tesseract é decisão de sistema, não efeito colateral. Um PDF sem texto é `pdf_sem_texto`, nunca “inexistente”.

**Quadro que atravessa páginas (Fase 32):** quando o cabeçalho está numa página, as linhas em várias e o `TOTAL` em outra, a continuidade é decidida por **evidências combinadas** (cabeçalho repetido, numeração de NTE contínua, página que abre no meio da lista, `TOTAL` que encerra), nunca por adjacência de páginas. Cada tabela recebe `certeza` (`forte`, `provavel`, `independente`, `ambigua`, `irreconstruivel`) e o `TOTAL` do quadro não é confundido com a nota de rodapé. No IBFC 004/2026 isso reconstruiu 27 NTEs somando exatamente 2.500, incluindo o `NÚCLEO 06` que usa rótulo diferente do resto do documento.

**Escopo regional:** NTE é regional administrativa — **não** é município, local de prova nem lotação. O cargo vem do **escopo do edital**, com página e trecho literal; com mais de um cargo o vínculo fica `ambiguo` e nada é atribuído por proximidade. A camada de NTE fecha com o `TOTAL` publicado; a de município é diagnóstica e só é publicável se cada NTE fechar com seus municípios (`soma_municipios_confere` — confere a soma, não cada linha). A proposta gerada é apenas a do **total do quadro** (`vagas_total_publicado`), sem `role_id` e com o motivo "não distribuir por modalidade"; totais de NTE ficam no relatório estrutural e, se emitidos, aparecem como recorte do NTE, nunca como total do concurso.

**PDF longo em lotes:** `documentos-parciais` lista cada extração parcial com a decisão **justificada** — ato de resultado/homologação/isenção é lista nominal e não é processado adiante (nome, nota e classificação não alimentam campo do concurso). `documentos-paginas` mostra em que página está o conteúdo útil amostrando só as páginas não lidas; `documentos-lote` acrescenta um lote idempotente, com limite por chamada, `next_page` e checkpoint para retomada.

API `GET /api/pipeline`, `/api/pipeline/cobertura`, `/api/pipeline/documentos`, `/api/pipeline/duplicidades`, `/api/pipeline/ocr`, `/api/pipeline/continuidade`, `/api/pipeline/parciais`, `/api/pipeline/escopo-regional`, `/api/revisao/duplicidades`; CLI `pipeline`, `pipeline-documentos`, `pipeline-cobertura`, `pipeline-duplicados`, `pipeline-continuidade`, `pipeline-regional`, `documentos-pendentes`, `documentos-extrair [--apply]`, `documentos-parciais`, `documentos-paginas`, `documentos-lote [--apply]`, `ocr-pendentes`. Ver [`docs/superpowers/specs/2026-10-17-pipeline-documental-design.md`](docs/superpowers/specs/2026-10-17-pipeline-documental-design.md) e [`.../2026-10-17-reconstrucao-multipagina-escopo-regional-design.md`](docs/superpowers/specs/2026-10-17-reconstrucao-multipagina-escopo-regional-design.md).

## Cobertura oficial e campos decisivos

A cobertura é medida em **dois denominadores**: concursos com qualquer documento e concursos com **documento oficial**. Página de agregador não é edital: os 504 certames que só têm notícia de agregador aparecem no estado `apenas_agregador`, não em "cobertura oficial". Cada certame recebe **um** estado (`campos_confirmados`, `conflito`, `campos_candidatos`, `edital_extraido`, `oficial_sem_extracao`, `oficial_sem_edital`, `identidade_pendente`, `obtencao_nao_autorizada`, `oficial_nao_importado`, `apenas_agregador`, `sem_documento`) e uma próxima ação. `historico` não é atribuído automaticamente: não há prova de encerramento no modelo.

**Aquisição controlada:** `editais-faltantes` lista certames com fonte oficial habilitada e sem documento; `aquisicao-planejar` simula e `aquisicao-executar --apply` registra/baixa em lote pequeno, com orçamento, limite por concurso e checkpoint. Só edital/retificação; **lista nominal** (nomes/notas/inscritos) não é baixada nem processada, mesmo quando a banca a rotula "Retificação" — `documentos-nominais` mostra o que já estava na base para decisão humana.

**Quatro campos decisivos:** `campos-decisivos` responde, por concurso: vagas indígenas (nunca derivadas de total agregado; ausência de modalidade não é zero), aceitação de Sistemas de Informação (por cargo, com evidência), prazos (documento autoritativo mais recente; anterior fica como substituído) e local de prova (separado de lotação; `a_divulgar` é declaração). `conflitos-versao` separa retificação posterior, divergência no mesmo documento, escopo diferente e equivalência (ex.: `Salvador` × `Salvador/BA`).

API `GET /api/cobertura/estados`, `/api/campos-decisivos`, `/api/conflitos`, `/api/editais-faltantes`; CLI `cobertura-estados`, `editais-faltantes`, `aquisicao-planejar`, `aquisicao-executar`, `campos-decisivos`, `conflitos-versao`, `documentos-nominais`. Ver [`docs/superpowers/specs/2026-10-17-cobertura-oficial-campos-decisivos-design.md`](docs/superpowers/specs/2026-10-17-cobertura-oficial-campos-decisivos-design.md).

## Mesa de revisão

A **Mesa de revisão** agrupa o trabalho por **oportunidade** (concurso × cargo), não por proposta solta: 6.199 propostas viram **273 grupos**. Cada linha mostra concurso, cargo (reconciliado ou rótulo do documento), estado documental, estado de até quatro campos decisivos, pendentes, conflitos, presença de evidência por página e próxima ação. Abrir o concurso mostra o **dossiê**: documentos com versões e páginas, todos os campos com todas as evidências (documento, versão, página, trecho, hash), lacunas declaradas e conflitos. A **comparação de evidências** traz o contexto antes/depois do trecho, a origem do conteúdo (extração, tabela, reconstrução regional, cronograma, OCR) e o histórico de decisões.

Estados de campo são explícitos e vêm do modelo existente: `confirmado`, `corrigido`, `em_conflito`, `ambiguo`, `candidato`, `multiplo_por_cargo` (cargos diferentes não são divergência), `rejeitado` (só quando todas as propostas foram rejeitadas) e `nao_extraido`. "Cargo não reconciliado" não é ambiguidade do valor.

**Sessões** têm progresso real, pausa/retomada e restauração após recarregar. Cada item guarda a impressão da evidência e o conjunto de propostas do escopo no momento da abertura: se a evidência mudou ou surgiu proposta nova para o mesmo campo, o item é marcado **alterado** e as ações são bloqueadas até reavaliação. Decidir continua sendo o fluxo append-only de `revisoes_campo`, com autor, justificativa, decisão anterior e hash — nada é aprovado em massa e nada é confirmado ao abrir.

**Documentos nominais** (listas de nomes, inscrições, notas) têm triagem própria com quatro eixos separados — identificação, natureza, acesso e armazenamento — sem baixar nada para exibir a fila e **sem reproduzir trecho ou contexto** de dados pessoais na mesa, na fila ou na comparação de evidências.

A **linha do tempo** mostra o que o ciclo agendado mudou desde uma referência, usando as tabelas do monitoramento (sem contabilidade paralela): snapshot anterior, ciclos, documentos descobertos, versões, propostas e falhas. Atribuição a ciclo é por janela de tempo, e `since` é normalizado para UTC.

API `GET /api/oportunidades`, `/api/oportunidades/<id>`, `/api/revisao/evidencia/<id>`, `/api/documentos/nominais`, `/api/linha-do-tempo`; CLI `oportunidades`, `oportunidade`, `evidencia`, `documentos-nominais`, `linha-do-tempo`. Ver [`docs/superpowers/specs/2026-10-17-mesa-revisao-dossies-design.md`](docs/superpowers/specs/2026-10-17-mesa-revisao-dossies-design.md).

## Identidades de cargo, conflitos e prazos

A seção **Identidades, conflitos e prazos** (`#identidades`) resolve o que a mesa deixou explícito: **246 rótulos de cargo em 28 concursos**, dos quais **85 não são cargos** (conteúdo programático, local de prova, escolaridade declarada). O rótulo é classificado por **marcador textual** em sete naturezas (`cargo_literal`, `cargo_com_codigo`, `abreviacao`, `especialidade`, `codigo_sem_nome`, `generico_sem_cargo`, `nao_e_cargo`), e a sugestão de identidade é **estrutural e auditável** — nome idêntico (+40), nome idêntico sem código (+35), código oficial (+40), prefixo de nome (+25), especialidade (+15) — só dentro do mesmo concurso, no máximo cinco candidatos, com empate rebaixado a **ambíguo**. A pontuação é chamada de "pontuação estrutural", nunca de probabilidade.

Decisões de identidade são **append-only** e exigem humano: `confirmada`, `rejeitada`, `ambigua`, `reaberta`, com autor, justificativa, evidência, vínculo com a decisão anterior e `expected_previous_id` contra decisão concorrente. Mudar o vínculo de uma confirmação exige `reaberta` antes. `dry_run` é o padrão em API e CLI. Duplicatas de identidade (36 rótulos) são **sinalizadas, não fundidas**; criar identidade a partir de rótulo só é permitido para naturezas que são cargo.

**Conflitos reais** ganham causa antes de vencedor: `retificacao_posterior` (13), `mesmo_documento_valores_distintos` (13), `documentos_diferentes_sem_ordem` (10), `escopo_diferente` (8), `cargos_diferentes_sem_identificacao` (5) e `documentos_com_data_distinta` (4), com prioridade 1..4, motivos e próxima ação. Retificação que não menciona o campo **não altera** o valor.

**Prazos** são candidatos temporais, não vigência: oito grupos (`inscricao_inicio/fim`, `isencao_inicio/fim`, `recurso_isencao`, `resultado_isencao_preliminar/final`, `data_prova`), cinco estados (`futuro`, `hoje`, `expirado`, `data_invalida`, `sem_data`), somente documentos autoritativos sustentam prazo, e cada item traz documento, versão, página, trecho, hash, publicação, coleta e decisão anterior. Data futura não comprova aplicabilidade; ausência de documento autoritativo aparece como `sem_data` com próxima ação.

**Destino de documentos nominais** é **simulação**: `retirar_da_fila_operacional` (156, já têm conteúdo), `manter_metadados_na_fila` (35, só metadados), `reconciliar_identidade` e `revisar_politica_antes_de_agir`. Nada é arquivado, apagado ou movido, e nenhum conteúdo nominal é baixado para exibição.

API `GET /api/reconciliacao`, `/api/reconciliacao/historico`, `/api/conflitos-revisao`, `/api/prazos`, `/api/documentos/nominais-destino`, `POST /api/reconciliacao`; CLI `reconciliacao`, `reconciliacao-historico`, `reconciliacao-decidir`, `reconciliacao-criar-cargo`, `conflitos-revisao`, `prazos`, `documentos-nominais-destino`. Ver [`docs/superpowers/specs/2026-10-18-reconciliacao-identidades-design.md`](docs/superpowers/specs/2026-10-18-reconciliacao-identidades-design.md).

## Identidade por código e escolaridade mínima

Cada código de vaga é uma **oportunidade distinta**. A matriz mostra `código`, `família` (título-base, só leitura) e `localidade` separadamente: a família **nunca** transfere requisito, vaga ou reserva, e a localidade da vaga **não** é local de prova. Quando o edital publica o mesmo título em municípios diferentes (Quadrix 3049, códigos 200–206), os registros permanecem individuais, cada um com seu código, município e vagas.

A leitura de formação pendurada no rótulo só-código (`"200"`) é **juntada por código** ao cargo nomeado, dentro do mesmo concurso e só quando o código é único entre os cargos nomeados. A atribuição fica registrada (`codigo_do_cargo`, `escopo_do_cargo`, `unico_cargo_do_concurso`, `declaracao_do_concurso`).

**Escolaridade mínima não é formação específica.** O classificador separa nível (médio/técnico/superior) de área (cláusula "em …"), e a matriz distingue:

| Estado | Exemplo | Elegibilidade |
|---|---|---|
| expresso | cita "Sistemas de Informação" | compatível |
| categoria | "áreas de TI … ou curso equivalente" | compatível |
| **nível mínimo** | "curso de nível médio", "superior em qualquer área" | **compatível por nível mínimo** |
| correlato | "área de computação" sem categoria | potencial (interpretar) |
| específico diferente | Direito, Design, licenciatura com magistério | incompatível |

Requisito de nível mínimo **não** é incompatibilidade nem ambiguidade; é candidato declarado como tal. Incompatibilidade explícita vence leitura concorrente, aceitação explícita vence ambiguidade, e **decisão humana `validado`/`corrigido` não é sobrescrita** pela releitura do texto (o valor armazenado continua visível na ficha).

`GET /api/elegibilidade/pendentes` (`elegibilidade-pendentes`) audita os rótulos pendentes por causa — `aguarda_decisao_humana`, `duplicata_de_identidade`, `sem_cargo_canonico`, `codigo_sem_nome` — e `GET /api/elegibilidade/revisao` (`elegibilidade-revisao`) monta as fichas com valor armazenado, leitura atual, nível, área, localidade e evidência.

Ver [`docs/superpowers/specs/2026-10-18-identidade-cargo-escolaridade-design.md`](docs/superpowers/specs/2026-10-18-identidade-cargo-escolaridade-design.md).

## Elegibilidade por cargo e reserva indígena

A **Matriz de elegibilidade** (`#eleg-panel`, `GET /api/elegibilidade`, CLI `elegibilidade`) responde, **por cargo**, se o requisito formal aceita o Bacharelado em Sistemas de Informação e se existe vaga indígena para aquele cargo. Seis estados exclusivos, com precedência: `incompativel_por_requisito`, `compativel_com_vaga_indigena_cargo`, `compativel_sem_vaga_indigena`, `compativel_por_interpretacao`, `identidade_pendente` e `informacao_insuficiente`.

**Incompatibilidade vem primeiro.** Um cargo com vaga indígena imediata e requisito de Direito continua incompatível — reserva não torna o cargo elegível. "Ambíguo" só é compatibilidade potencial quando o trecho é de formação **e** cita área de computação/TI; "conhecimentos básicos em informática" não conta. Um cargo nunca herda o estado de outro, nem o agregado do concurso.

A **reserva indígena** tem escopo declarado: `cargo_imediata`, `cargo_sem_imediata_com_reserva`, `cargo_explicito_zero`, `concurso_imediata_sem_distribuicao`, `distribuido_por_cargo`, `reserva_sem_quantidade`, `mencao_sem_quantidade`, `ausente_no_documento` e `nao_localizado`. Quantidade publicada apenas para o concurso **não** é distribuída por cargo; "CR" não é zero nem vaga imediata; total agregado nunca vira vaga indígena.

O **quadro de vagas em texto de PDF** passou a ser lido (`tabela-texto`): o cabeçalho é reconhecido pelas modalidades e cada linha traz um valor por coluna. Isso revelou, por exemplo, o quadro do TJSC Juiz Substituto 2026 — 15 vagas imediatas, **1 indígena**, cadastro de reserva "CR" — que antes não era extraído.

Os **destaques por elegibilidade** (`GET /api/elegibilidade/destaques`, CLI `elegibilidade-destaques`) incluem apenas cargo cujo requisito sustenta o perfil, no máximo dois por concurso, com motivo legível. Cargo incompatível fica fora mesmo com vaga indígena.

Ver [`docs/superpowers/specs/2026-10-18-elegibilidade-cargo-design.md`](docs/superpowers/specs/2026-10-18-elegibilidade-cargo-design.md).

## Auditoria de prazos e ficha de decisão

Cada prazo do calendário tem uma **ficha** (`GET /api/prazos/caso`, `prazos-caso`, botão "Ficha"): todos os candidatos com trecho, contexto anterior e posterior, página, offsets, versão, sha256 e URL; o **evento** a que o trecho se refere (inscrição, isenção, prova, recurso); se o extrator atual ainda reproduz o valor; as verificações de documento registradas; e uma **proposta de correção explicitamente não executada**.

A causa do conflito é derivada e explicada (`GET /api/prazos/auditoria`): `evento_diferente` (o trecho trata de isenção ou prova), `divergencia_real` (dois valores válidos), `extracao_obsoleta`, `evidencia_deslocada`, `coerente` ou `indeterminado`. A auditoria **não escolhe valor**: mostra `valores_sustentados`, `valores_verificados` e `valores_nao_classificados`, e a decisão continua humana no fluxo de revisão.

As contagens do calendário são **por dimensão independente**, cada uma somando o total: `por_temporal` (futuro/hoje/expirado/data_invalida/sem_data), `por_revalidacao`, `por_conflito` e `por_revisao`. `por_situacao` é um estado derivado para orientar a ação, e o bloco `denominador` declara unidade, universo, filtros e o tratamento de propostas rejeitadas. Assim `fonte_inalterada` não é um estado temporal nem confirmação de prazo.

O contexto de extração passou a ser a **oração**, não a página: janela curta antes da data e, se necessário, a frase — evitando que "A isenção … no período … por meio de inscrição" vire prazo de inscrição, ou que a data da prova seja lida como fim de inscrições.

Ver [`docs/superpowers/specs/2026-10-18-auditoria-prazos-design.md`](docs/superpowers/specs/2026-10-18-auditoria-prazos-design.md).

## Carteira operacional e prazos atuais

A seção **Carteira de oportunidades** (`#carteira`) responde o que fazer agora, sem transformar candidato em fato. São **285 oportunidades** (concurso × cargo/rótulo) com uma **prontidão determinística**: `oportunidade_historica` (todos os prazos passaram), `identidade_cargo_pendente`, `conflito_documental_pendente`, `prazo_precisa_revalidacao`, `campos_decisivos_ausentes`, `candidatos_prontos_para_revisao`, `edital_oficial_necessario`, `documentacao_insuficiente` e `informacao_confirmada` (só com decisão humana). Cada linha mostra o motivo, a urgência, a compatibilidade com Sistemas de Informação, a reserva indígena, o local de prova e a próxima ação.

A **carteira inicial** (destaques) é um subconjunto controlado: edital oficial identificado e ao menos um sinal (prazo futuro, SI expresso/categoria/correlato ou reserva indígena), no máximo dois cargos por concurso, com o motivo da inclusão. Rótulo que não é cargo fica fora.

O **calendário de prazos** (`GET /api/prazos/calendario`) dá estado operacional a cada prazo: `candidato_nao_revalidado`, `revalidado_na_fonte`, `conflito_documental`, `alterado_por_retificacao`, `passado_com_evidencia`, `nao_localizado`, `data_ilegivel` e `fonte_nao_confirmada`, com urgência em `America/Recife`. **Data futura não comprova inscrição aberta**; conflito **não escolhe valor** — todos os candidatos ficam visíveis com documento, página, trecho, versão e hash; retificação que repete o valor não altera o prazo; prazo passado é preservado.

**Revalidação** (`prazos-revalidar`, `POST /api/prazos/revalidacao`) verifica apenas o documento oficial já conhecido: compara o sha256 servido hoje com o da coleta e registra metadados em `revalidacoes_prazo` (append-only). `fonte_inalterada` significa "documento idêntico", **não** "prazo confirmado". O padrão é simulação sem rede; `--apply` grava somente hashes/status, nunca conteúdo, e não altera propostas.

O **dossiê operacional** (`carteira-dossie`) reúne identificação, vagas (total agregado, imediatas, reserva, indígenas com âmbito do concurso), formação (requisito literal, cursos aceitos, SI por cargo), prazos (incluindo a lacuna declarada de pagamento), localização (prova e lotação separadas), conflitos, lacunas e próxima ação. Cada seção aponta para a evidência na mesa de revisão.

API `GET /api/carteira`, `/api/carteira/destaques`, `/api/carteira/dossie`, `/api/prazos/calendario`, `/api/prazos/revalidacao`, `/api/prazos/revalidacao/historico`, `POST /api/prazos/revalidacao`; CLI `carteira`, `carteira-destaques`, `carteira-dossie`, `prazos-calendario`, `prazos-revalidar`, `prazos-revalidacao-historico`. Ver [`docs/superpowers/specs/2026-10-18-carteira-operacional-design.md`](docs/superpowers/specs/2026-10-18-carteira-operacional-design.md).

## Revisão humana e confirmação

A seção **Revisão humana** (`#review-panel`) transforma as propostas extraídas em uma fila de trabalho priorizada, paginada e auditável. Cada item mostra valor proposto, valor vigente, evidência literal (documento, versão, página, trecho e link), conflitos com outras propostas e os **fatores que elevaram ou reduziram a prioridade** — a pontuação é determinística e explicada, nunca opaca. Filtros: campo, estado, conflito, prioridade mínima, documento, fonte, período do documento e data da última revisão.

As ações humanas são **append-only**: validar, rejeitar, adiar, marcar como ambíguo, pedir nova extração, reabrir e corrigir. Cada decisão grava estado anterior, estado novo, instante, autor, justificativa, canal (`interface`, `cli` ou `importacao`) e a impressão (`sha256`) da evidência revisada. Corrigir mantém a evidência original e cria uma proposta derivada identificada como correção humana. Reenviar a mesma decisão ou selecionar o mesmo valor é **idempotente**. Aprovar um documento ou um valor **não** confirma os demais campos.

**Lotes** (`#review-batch`) são ferramentas de navegação: abrem de 10 a 25 itens, permitem próximo/anterior/pausar/retomar e sobrevivem a recarregar a página. O lote **não** aprova em massa — não existe ação de aprovação coletiva. A exportação leva `proposal_id` estável e `evidence_sha256`; a importação rejeita item cuja evidência mudou ou que já foi decidido, e grava tudo em uma transação.

A seção **Associações pendentes** (`#assoc-panel`) mostra documento, órgão, data e a evidência do vínculo, com confirmar (exige o id do certame e justificativa), rejeitar e manter pendente. Confirmar a associação **não** valida os campos extraídos. Não há associação por semelhança de título, órgão ou data.

API `/api/revisao/fila`, `/api/revisao/proposta/<id>`, `/api/revisao/selecionar`, `/api/revisao/lotes*`, `/api/revisao/importar`, `/api/documentos/bloqueados`, `POST /api/documentos/importar`; CLI `revisao-fila`, `revisao-decidir`, `revisao-selecionar`, `revisao-lote`, `revisao-exportar`, `revisao-importar`, `documentos-bloqueados`, `documentos-importar`. Ver [`docs/superpowers/specs/2026-10-17-revisao-humana-confirmacao-design.md`](docs/superpowers/specs/2026-10-17-revisao-humana-confirmacao-design.md).

**Documentos bloqueados:** a seção **Documentos bloqueados e ingestão manual** (`#blocked-panel`) classifica cada documento em `obtido`, `importado_manualmente`, `bloqueado`, `indisponivel` ou `pendente_download`, com o motivo e a evidência do `robots.txt`. Documento bloqueado **não** é documento inexistente: a referência oficial é preservada. Alternativas são sugeridas apenas por **igualdade exata de caminho em host autorizado**, página de origem acessível e pesquisa humana (portal do órgão/DOU). O arquivo fornecido manualmente é validado por assinatura (PDF/ZIP/HTML), limitado a 20 MiB, gravado com SHA-256 local, origem declarada, canal e responsável — e continua **pendente de revisão**, nunca oficial por declaração.

## Catálogo de fontes e política de dados

O **catálogo de fontes** (`radar/source_catalog.py`, versionado em código) descreve cada fonte: categoria (concursos, educacional, auxiliar), natureza (oficial, institucional, agregador, comunitária, comercial), domínios, acesso, cobertura, **permissão por tipo de conteúdo**, cache, intervalo mínimo, rate limit, custo verificado, variável de credencial, retenção, deduplicação, termos, estado, conector e data de revisão.

A permissão é **por tipo de conteúdo**, não por fonte: metadado, URL, documento, questão, gabarito, notícia e dado aberto têm decisões independentes. As categorias são `persistencia_permitida` (exige URL de evidência e data), `uso_transitorio` (não grava, não cacheia, não loga), `persistencia_nao_verificada` (tratada como proibida), `acesso_bloqueado` e `importacao_manual_controlada`. Fonte em estado diferente de `habilitada` não persiste, mesmo que o tipo tenha permissão.

`radar/source_policy.py` é a porta única de persistência: o caminho de coleta consulta a política antes de gravar. Corpo de terceiro não autorizado é descartado — os metadados e a URL continuam como pista — e nem chega a ser baixado. `radar/budget.py` impõe, por execução, limites de chamadas, itens, créditos e valor, com intervalo mínimo e janela mensal; custo pago exige verificação e autorização explícitas. `radar/connectors.py` dá a interface comum (capacidades, política, disponibilidade, descoberta, detalhes, paginação, custos) e normaliza resultados preservando identificador original, URL, fonte, datas, oficialidade, incerteza e evidência.

A visão operacional fica em **Catálogo de fontes** (`#sources-panel`): estado, credencial necessária, custo, permissão por tipo, última execução, consumo e revisão de política vencida. API `GET /api/fontes`, `GET /api/fontes/<id>`, `GET /api/fontes-consumo`; CLI `fontes [--validar]`, `fontes-consumo`, `fontes-revisar`, `fontes-politica`, `localidades [--validar]`.

**Integração real desta fase:** IBGE Localidades (dados abertos oficiais, sem chave) valida `exam_location`/`exam_municipio`/`exam_uf` contra a lista de 5.570 municípios. O resultado é **parecer** (`confere_ibge`, `uf_divergente`, `nao_encontrado`, `sem_snapshot`) para revisão humana — nunca confirma campo. Na base real encontrou `Taboão/SP`, que não é município (o correto é Taboão da Serra). Ver [`docs/superpowers/specs/2026-10-17-catalogo-fontes-politicas-design.md`](docs/superpowers/specs/2026-10-17-catalogo-fontes-politicas-design.md).

## Fechamento do backend e prontidão (Fase 44)

O backend foi auditado por domínio e fechado para o início do frontend. O contrato HTTP é
versionado e verificável, e há um relatório único de prontidão:

`powershell
python -m radar api-contrato --verificar   # 129 entradas método+rota
python -m radar api-contrato --markdown    # gera docs/API.md
python -m radar prontidao --db .\data\radar.sqlite3
`

GET /api/saude/prontidao expõe o mesmo relatório pela API (com cache de 60 s). O
relatório separa falha bloqueante (integridade, FK, schema, proveniência, contrato) de
pendência real (documento sem versão, extração parcial, conflito, credencial externa).
GET /api/concursos mantém o contrato v1 com 18 campos.

Escritas locais exigem Origin e Host loopback na mesma porta e corpo JSON; consultas
pesadas concorrentes recebem 429. Inventário, gate e evidências:
[docs/BACKEND_INVENTORY.md](docs/BACKEND_INVENTORY.md),
[docs/READINESS_GATE.md](docs/READINESS_GATE.md),
[docs/API.md](docs/API.md).

## Interface de produto (Fase 45)

A interface passou a ser uma aplicação de produto com shell próprio: sidebar recolhível,
topbar com busca, dashboards, oportunidades com filtros e paginação, dossiê em abas,
estudos e operação. HTML, CSS e JavaScript sem framework e sem build; os painéis técnicos
continuam acessíveis em **Operação**.

```powershell
python -m radar serve --db .\data\radar.sqlite3
```

Abra `http://127.0.0.1:8000/`. Rotas: `#/visao-geral`, `#/oportunidades`, `#/prazos`,
`#/estudos`, `#/historico`, `#/configuracoes`, `#/operacao` e `#/dossie/<uuid>`.
Design, arquitetura e evidências de validação:
[`docs/superpowers/specs/2026-10-19-frontend-produto-design.md`](docs/superpowers/specs/2026-10-19-frontend-produto-design.md)
e [`docs/superpowers/plans/2026-10-19-frontend-produto-prova-real.md`](docs/superpowers/plans/2026-10-19-frontend-produto-prova-real.md).

## Testes

```powershell
python -m unittest discover -s tests -q
```

## Limitações

- Cobertura restrita às fontes oficiais configuradas no projeto.
- Extração de PDF apenas quando há texto; documentos digitalizados (imagem) não são lidos por OCR.
- A extração produz propostas que precisam de revisão humana para virarem fatos confirmados.
- A data exibida indica quando a fonte foi consultada, não garante a situação atual do certame; confirme sempre nos documentos oficiais.
- Notificações nativas são **opcionais** (`notifications.local`) e a exibição visual depende das configurações de foco/notificação do Windows; a entrega é confirmável, a exibição não é garantida.
- A **priorização geográfica** usa apenas localização com evidência documental; a base atual ainda tem poucas propostas de local, então muitos concursos aparecem como "sem dados"/localização não informada (honesto, sem inferência). Distâncias são **linha reta** (não rodoviárias) e dependem de coordenadas conhecidas (seed limitado + provedor local opcional).
- O **perfil de conhecimento** é declarado pelo usuário; não há inferência a partir da formação e a cobertura **não** é probabilidade de aprovação.
- A **extração do conteúdo programático** é conservadora (prefere precisão a cobertura): formatos de seção muito incomuns podem ficar como "não localizado". A base real ainda não tem propostas de conteúdo porque as versões foram analisadas antes desta fase; a extração ocorre nas próximas análises.
**Cobertura e qualidade dos dados:** a seção **Cobertura** (`#coverage-panel`, `#gaps-panel`) mostra o funil real da base (concursos → com documento → com edital oficial → com propostas → com campo confirmado), a distribuição de causas da insuficiência e as dimensões obrigatórias com **denominador explícito**. Quem ainda não foi pesquisado aparece em `fora_do_denominador` e nunca conta como zero; notícia de agregador não é tratada como prova oficial; dimensão sem campo no modelo aparece como `nao_mapeado`. A **fila de lacunas** prioriza com critérios declarados e separa coleta automática de revisão humana. API `/api/cobertura`, `/api/cobertura/resumo`, `/api/lacunas`, `POST /api/cobertura/papeis`; CLI `cobertura`, `lacunas`, `cobertura-papeis [--apply]`. O enriquecimento cria identidades de cargo a partir do rótulo literal do edital (idempotente, `dry_run` por padrão) e **não** resolve ambiguidade nem valida nada. Ver [`docs/superpowers/specs/2026-10-17-data-coverage-diagnostics-design.md`](docs/superpowers/specs/2026-10-17-data-coverage-diagnostics-design.md).

**Identidade canônica de certame (Fase 27):** um identificador de **publicação** (seção do diário) ou de **catálogo** não é um certame. `concursos_identidade.estado_identidade` separa `certame` de `container_fonte`, e `observacoes_concurso.tipo_identidade` registra a natureza da fonte (`secao_publicacao`, `catalogo`). O container é **área de retenção**: recebe documentos, nunca propostas, e fica fora de cobertura, prioridade, saúde e diagnóstico de associação. Documentos em container ganham associação **`pendente`** na tabela append-only `associacoes_documento` (com evidência, revisor e nota; nova decisão referencia a anterior em `supersedes_id`), e a associação a um certame exige **decisão humana registrada** — `apply_repair` nunca desfaz decisão humana e reexecutar o reparo é idempotente. `GET /api/identidade`, `GET /api/associacoes/fila`, `POST /api/associacoes/<document_id>`, `POST /api/identidade/reparar`; CLI `identidade`, `identidade-reparar`, `associacoes-fila`, `associacao-revisar`, `ibfc-piloto`. Ver [`docs/superpowers/specs/2026-10-17-identidade-canonica-container-fonte-design.md`](docs/superpowers/specs/2026-10-17-identidade-canonica-container-fonte-design.md).

**Descoberta, associação e extração (Fase 26):** o texto de PDF é re-segmentado em linhas lógicas (`program_content.logical_lines`) porque o extrator normaliza o texto e apaga quebras — foi a causa comprovada de `conteudo_programatico` ficar em 0%. O **local de prova** passou a ter extrator próprio (`radar/exam_location.py`), que nunca infere de lotação, sede do órgão ou notícia, preserva listas de cidades e registra `a_divulgar` quando o edital declara publicação futura. `radar/reprocess.py` reprocessa editais já analisados de forma **idempotente**, sem reescrever blocos nem evidências. `radar/association.py` diagnostica associações suspeitas (ex.: a seção do DOU usada como identidade de concurso) **sem corrigir automaticamente**. Classificação documental separa página de agregador de ato oficial. API `/api/associacoes`, `POST /api/documentos/tipos`, `POST /api/documentos/reprocessar`; CLI `associacoes`, `documentos-tipos`, `documentos-reprocessar`. Ver [`docs/superpowers/specs/2026-10-17-official-discovery-association-extraction-design.md`](docs/superpowers/specs/2026-10-17-official-discovery-association-extraction-design.md).

- **Anexos com `robots.txt` restritivo não são baixados.** O CDN `anexos.cdn.selecao.net.br` responde `Disallow: /`; esses documentos aparecem com URL e metadados (o usuário chega ao original), mas **sem versão local** e sem extração de texto. O resumo do ciclo mostra `downloads_bloqueados` para que a lacuna seja visível.
- O **container de fonte** existe para impedir que uma seção de diário seja tratada como concurso; ele não cria certames nem associa documentos automaticamente. No banco real há **1 container** (DOU Seção 3) com 10 documentos pendentes de revisão.
- **Licença de software não licencia conteúdo.** Scrapers MIT (ConcursosNoBrasil e derivados) não autorizam armazenar o conteúdo do agregador; fontes sem licença (Quest API, `kauafernandomelo`) e hosts com `robots.txt` 403 (Qconcursos, Questões de Concursos) ficam bloqueados no catálogo. Nenhuma conta, assinatura ou pagamento foi criado.
- **OCR não confirma nada e não roda sozinho.** O motor é o do sistema operacional (Windows OCR `pt-BR`) ou Tesseract, se instalado; sem motor o documento continua `pdf_sem_texto`. O texto reconhecido tem erros previsíveis de acentuação e é sempre marcado como derivado. Na base real, 1 documento de 2 páginas passou por OCR; os 13 PDFs longos seguem **parciais** (prefixo de 40 páginas).
- **Total agregado não é distribuição de vagas.** O quadro do IBFC publica um total que já inclui ampla, negros e PCD e não menciona indígenas: o Radar registra `vagas_total_publicado` e não cria vagas imediatas nem indígenas a partir dele.
- **Baixar não é extrair, extrair não é confirmar.** A base real tem 4.750 propostas candidatas e **0 campos confirmados**: o pipeline entrega evidência (página, trecho, versão, hash), não fato. 13 PDFs longos foram lidos apenas no prefixo e 1 PDF (texto vetorial) não tem camada de texto — ambos registrados como limitação, não como conteúdo ausente.
- **Revisão humana não é aprovação automática.** A base real pode continuar com 0 valores confirmados mesmo com milhares de propostas: a fila existe para que a decisão seja humana, rastreável e idempotente. Prioridade é heurística determinística, não probabilidade de aprovação.
- **Política de `robots.txt` não é negativa HTTP.** O CDN `anexos.cdn.selecao.net.br` responde `Disallow: /`; por padrão o coletor registra URL e metadados sem baixar. O conector IBFC aceita uma autorização **explícita e exclusiva** (`download_robots_disallowed_hosts` em `radar_ops.json` ou `ibfc-piloto --attempt-blocked` / `documentos-baixar-bloqueados`) para tentar o download normal das URLs públicas já descobertas, em série, com timeout, limite de tamanho e sem qualquer evasão. Negativa real (401/403), limite (429) e CAPTCHA interrompem a tentativa e ficam registrados; documento não obtido nunca é “edital inexistente”.
- A gestão de estudos cobre disciplinas, tópicos, sessões, progresso, revisão espaçada, **flashcards com imagem, questões, simulados com mapa/marcação/retomada, prática adaptativa e pacotes portáveis**, com **exportação/importação (formato v2) e backup** dos dados pessoais. O cronômetro não bloqueia a aba nem alerta o fim do Pomodoro. A prática adaptativa é heurística determinística (não é TRI/IRT nem estima probabilidade de aprovação).
- **Nenhum banco de questões de terceiros** foi importado: a licença do software não autoriza redistribuir conteúdo editorial (ex.: `examsim`). Questões são criadas pelo próprio usuário.

Detalhes técnicos de operação, processamento e desenvolvimento ficam em [`docs/`](docs/) e no [registro de trabalho](docs/AUTONOMOUS_WORK_LOG.md).

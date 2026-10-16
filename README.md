# Radar de Concursos

O Radar de Concursos é uma ferramenta para **coletar, organizar e analisar** informações sobre concursos públicos brasileiros. Ele reúne dados de uma fonte oficial em um banco local, guarda o **histórico dos documentos** (editais, retificações e versões) e extrai **fatos com evidência** — sempre como propostas que passam por **revisão humana explícita** antes de serem consideradas confirmadas.

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
```

**Agendamento (Windows):** `pwsh -File .\scripts\install_tasks.ps1` registra a tarefa "Radar de Concursos - Ciclo" (a cada 6 h, sem sobrepor execucoes, recuperando apos reinicio), usando o Python do `radar_ops.json` e a conta do usuario, **sem senha armazenada**. `verify_tasks.ps1` mostra estado/proxima execucao; `uninstall_tasks.ps1` remove as tarefas **sem apagar dados**. O servidor local (loopback) pode ser iniciado por `pwsh -File .\scripts\serve.ps1`.

Alertas persistentes (novo candidato, documento recuperado, retificacao, fonte indisponivel, prazo de isencao proximo/expirado) ficam no banco e aparecem na secao **Alertas** da interface, que se atualiza periodicamente. `GET /api/alertas` e `GET /api/saude` expoem os dados. Ver [`docs/superpowers/specs/2026-10-16-autonomous-operation-design.md`](docs/superpowers/specs/2026-10-16-autonomous-operation-design.md).

## Fontes oficiais

- **Prefeitura de Guajará-Mirim/RO (SEMED)** — artigo oficial com o resumo do concurso (base do contrato v1 de 18 campos).
- **Diário Oficial da União — Seção 3 (Imprensa Nacional)** — segunda fonte, independente e federal: descobre editais, retificações e avisos de concursos na edição diária pública (`https://www.in.gov.br/leiturajornal`). O adaptador registra documentos com proveniência e histórico, sem alterar os 18 campos de `GET /api/concursos`. Ver [`docs/superpowers/specs/2026-10-16-fonte-oficial-2-design.md`](docs/superpowers/specs/2026-10-16-fonte-oficial-2-design.md).
- **FGV Conhecimento** — terceira fonte: catálogo público de concursos (`https://conhecimento.fgv.br/concursos`) com identidade por concurso (slug) e recuperação dos documentos publicados (edital, retificações, resultados). Segue os links documentais das páginas, inclusive para concursos já conhecidos (revisão incremental). Ver [`docs/superpowers/specs/2026-10-16-fgv-source-design.md`](docs/superpowers/specs/2026-10-16-fgv-source-design.md).
- **Quadrix** — quarta fonte oficial: banca com páginas server-rendered (`https://www.quadrix.org.br/informacoes/<id>/`) e **documentos públicos** (edital, retificações, anexos, comunicados) em `anexos-r2.selecao.net.br`. Recupera editais completos com hash e proveniência. Ver [`docs/superpowers/specs/2026-10-16-official-confirmation-expansion-design.md`](docs/superpowers/specs/2026-10-16-official-confirmation-expansion-design.md).
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

## Testes

```powershell
python -m unittest discover -s tests -q
```

## Limitações

- Cobertura restrita às fontes oficiais configuradas no projeto.
- Extração de PDF apenas quando há texto; documentos digitalizados (imagem) não são lidos por OCR.
- A extração produz propostas que precisam de revisão humana para virarem fatos confirmados.
- A data exibida indica quando a fonte foi consultada, não garante a situação atual do certame; confirme sempre nos documentos oficiais.

Detalhes técnicos de operação, processamento e desenvolvimento ficam em [`docs/`](docs/) e no [registro de trabalho](docs/AUTONOMOUS_WORK_LOG.md).

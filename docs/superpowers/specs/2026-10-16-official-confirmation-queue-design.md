# Fila de confirmação documental e reconciliação multifonte — desenho

Data: 2026-10-16

## Intenção

Transformar os candidatos descobertos pela PCI (Fase 10) em **oportunidades
rastreáveis**: uma fila persistente, retomável e incremental que procura
**referências oficiais**, registra documentos com proveniência e mantém a
descoberta separada da confirmação. A descoberta da PCI **não** é comprovação
oficial; um documento registrado **não** significa campos validados.

Estados independentes preservados: **descoberto** (PCI), **confirmado
documentalmente** (documento/evidência) e **elegibilidade analisada** (revisão
humana).

## Situação real da base (2026-10-16)

- A base habitual (`data/`) **não existe**; não há dados v1 nem candidatos nela.
- Os 477 candidatos da Fase 10 estão **apenas** nos bancos temporários de prova
  (`%TEMP%\pci10-*`). Não são copiados para a base habitual.
- Portanto, a reconciliação é feita **contra os dados realmente disponíveis**
  (nesta fase, a própria base de trabalho com os candidatos PCI), sem inventar
  métricas de sobreposição. Quando a base contiver DOU/FGV/v1, a mesma comparação
  passa a medir sobreposição real.

## Modelo de estados da confirmação

Vocabulário (persistido em `fila_confirmacao.state`):

`pendente` · `em_processamento` · `fonte_oficial_localizada` ·
`documento_localizado` · `documento_registrado` · `documento_processado` ·
`revisao_pendente` · `confirmacao_parcial` · `nao_localizado` · `inconclusivo` ·
`falhou` · `concluido`.

Semântica importante: `nao_localizado` **não** significa que o concurso seja falso;
`falhou` **não** significa encerrado; `documento_registrado` **não** significa campos
validados. O estado acompanha o candidato; documentos e propostas mantêm seus
próprios estados.

## Fila persistente (migração aditiva v5)

Tabela `fila_confirmacao` (uma linha por observação/candidato):

| Coluna | Papel |
|---|---|
| `observation_id` (PK) | identidade estável do candidato (observação) |
| `source_id`, `competition_id` | fonte de descoberta e identidade do candidato |
| `state` | estado atual (vocabulário acima) |
| `attempts`, `last_attempt_at`, `next_attempt_at`, `last_success_at` | controle de tentativas/retomada |
| `official_url`, `official_source`, `document_id` | referência oficial e documento registrado |
| `priority_score`, `priority_reason` | ordenação transparente da fila |
| `reason`, `ambiguity`, `result_json`, `history_json` | motivo, ambiguidade e histórico |
| `updated_at` | última atualização |

Índices por `state` e por `(state, priority_score)`. Migração v5 aditiva,
idempotente e tolerante a banco parcial; leitura aceita 2/3/4/5.

## Priorização

`priority_score` (maior = antes) a partir de sinais disponíveis no candidato PCI:
inscrições (possivelmente) abertas, prazo próximo (`dias_restantes`), cargos de TI
(`analista de sistemas`, `técnico em informática`, `tecnologia`, `sistemas`),
menção a indígena, e candidatos com URL de referência pronta. `priority_reason`
registra o porquê. A prioridade **ordena**, não exclui.

## Resolução de referências oficiais (injetável)

`radar/official_resolvers.py`, executado em cadeia, cada um devolve
`{official_url, source, title, evidence, confidence, ambiguity}` ou `None`:

1. **FgvCatalogResolver** — casa o candidato com o **catálogo oficial da FGV**
   (conector existente), por normalização de órgão/título; devolve a página oficial
   do concurso. `confidence` alto quando há correspondência forte de órgão; senão
   `ambiguity`.
2. **DouSearchResolver** — consulta a **busca pública do DOU**
   (`https://www.in.gov.br/consulta/-/buscar/dou?q=...`), reutilizando o parser
   `jsonArray` já existente; devolve a matéria do DOU quando o órgão/certame casa.
   `confidence` médio → marcado para revisão.

Resolvers são **injetáveis** (rede substituível em testes). Nenhuma URL da PCI
autoriza download: a URL oficial descoberta passa pelas defesas existentes
(`document_download`: HTTPS, DNS/IP público, peer, TLS, MIME, limites) e pela
allowlist (`document_discovery`).

## Processamento em lotes

`process_batch(db_path, *, resolvers, limit, now, transport, downloader, analyzer)`:

1. `recover_stale` — itens `em_processamento` antigos voltam a `pendente`
   (retomada após interrupção).
2. `select_batch` — até `limit` itens elegíveis (`pendente`, ou `falhou`/
   `nao_localizado` com `next_attempt_at` vencido), ordenados por prioridade.
3. Cada item é marcado `em_processamento` e processado **isolado em try/except**
   (uma falha não derruba o lote):
   - referência oficial encontrada → tenta baixar/registrar/extrair:
     `documento_registrado` + `revisao_pendente` (há propostas para revisão);
     se o download falhar → `documento_localizado` (ref achada, arquivo não obtido).
   - sem referência → `nao_localizado` (com `next_attempt_at` por backoff).
   - ambíguo → `inconclusivo`.
   - erro técnico → `falhou` (com backoff).
4. Retorna resumo: elegíveis, processados, por estado, e contadores.

Limite padrão conservador (`DEFAULT_BATCH_LIMIT = 10`, configurável por CLI/API).
Sem paralelismo agressivo; uma requisição por vez.

## Reconciliação multifonte

`reconcile(db_path)` compara cada candidato PCI com documentos de **outras fontes**
(título normalizado, órgão), classificando: `coincidente` (já conhecido por outra
fonte), `novo`, `ambiguo`, `sem_dados`. Preserva as duas proveniências; **não**
funde identidades automaticamente (associação é candidata a revisão).

## CLI e API

- CLI (padrão `documents-*`/`monitor`): `confirmacao-status`, `confirmacao-reconciliar`,
  `confirmacao-lote --limit N [--dry-run]`, `confirmacao-item --observation-id ID`.
- API aditiva `GET /api/confirmacao` (somente leitura): contadores por estado,
  última execução, próximos itens. `GET /api/concursos` (18 campos) **inalterado**.

## Limites e segurança

- Confirmação depende de referências oficiais **realmente acessíveis**; a maioria
  dos candidatos municipais não está no DOU/FGV e permanece `nao_localizado`.
- Nenhum scraping de mecanismos de busca; apenas busca pública do DOU e catálogo FGV.
- Sem copiar acervo da PCI; apenas referências/metadados.
- Sem migração da base habitual; prova em banco temporário.
- Nada é promovido a valor validado sem revisão humana.

## Como adicionar um novo conector de confirmação

Implementar um resolver com a mesma interface (`resolve(candidate) -> dict | None`)
e incluí-lo na cadeia (`official_resolvers.default_resolvers`). Nenhuma outra
mudança de schema ou CLI é necessária.

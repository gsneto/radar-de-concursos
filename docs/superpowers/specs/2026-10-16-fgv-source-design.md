# Terceira fonte — FGV Conhecimento — desenho e decisão

Data: 2026-10-16

## Intenção

Adicionar uma terceira fonte de descoberta e enriquecimento documental: o portal
oficial da **FGV Conhecimento** (`https://conhecimento.fgv.br/concursos`). O
objetivo é descobrir certames organizados pela FGV, recuperar os documentos
publicados nas páginas individuais (edital, retificações, resultados) e alimentar
o fluxo documental existente — sem alterar os 18 campos de `GET /api/concursos`.

Estados que permanecem separados: **descoberto** (a FGV listou o certame),
**confirmado documentalmente** (há documento/evidência) e **elegibilidade
analisada** (requisitos e vagas examinados). A página da banca não substitui o
edital.

## Comparação de complementaridade (evidência real, 2026-10-16)

| Candidata | Acesso observado | Documentos | Veredito |
|---|---|---|---|
| **FGV Conhecimento** | HTTP 200; HTML server-rendered (Drupal); catálogo paginado (`?page=0..13`); `robots.txt` **não** proíbe `/concursos` | Páginas individuais com histórico datado de PDFs (edital, retificação, resultado) em `conhecimento.fgv.br/sites/default/files/concursos/*.pdf` | **Escolhida** |
| Cebraspe | HTTP 200, mas página com ~16 KB e **0 links** (renderização por JS) | Difícil sem browser | Descartada (dependência de JS; custo alto) |
| IBFC | **HTTP 403** (bloqueado ao cliente) | — | Descartada (acesso não disponível) |
| PCI Concursos | HTTP 200, agregador com `robots.txt` | Agrega terceiros | Descartada como **fonte** (não oficial); possível canal de descoberta futuro |
| Portal estadual/institucional | Não avaliado nesta fase | — | Fora de escopo |

A FGV foi escolhida por ser **oficial** (organiza os certames), **server-rendered**
(parseável sem browser), com **catálogo paginado estável** e **histórico documental
datado** por concurso — o que permite descobrir novos certames e enriquecer os
conhecidos com edital/anexos/retificações.

## Condições de acesso e segurança

- Somente páginas públicas de catálogo e detalhe; **nenhuma** área autenticada,
  inscrição ou gestão. Nenhuma credencial, cookie de sessão ou dado de candidato.
- `robots.txt` observado: proíbe `/core/`, `/profiles/`, `/admin/`, `/search/`,
  `/user/*` etc.; **não** proíbe `/concursos` nem `/sites/default/files/concursos/`.
- Requisições sequenciais com User-Agent identificável, timeout e limite de bytes;
  frequência baixa (um ciclo consulta poucas páginas). Sem paralelismo agressivo.
- Downloads reutilizam `document_download` (HTTPS, DNS/IP público, peer verificado,
  TLS, MIME, limites). Novo host oficial autorizado na allowlist:
  `conhecimento.fgv.br` apenas em `/concursos/...` e `/sites/default/files/concursos/...`.

## Arquitetura do adaptador (`radar/fgv_source.py`)

Parsing puro (testável, sem rede):

- `parse_catalog(html)` → entradas `{slug, url, title}` (blocos `views-row` →
  `views-field-title` → `<a href="/concursos/<slug>">Título</a>`).
- `parse_detail(html)` → `{title, status, documents[]}`, onde cada documento vem do
  bloco `paragraph--type--texto-data` dentro de `field-concurso-arquivos`, com
  `<time datetime>` (data) e `<a href>` (arquivo). `status` de `field-concurso-status`.
- `classify_document(title)` → `retificacao` quando o título começa pelo marcador
  (ex.: "1ª Retificação", "Retificação do Edital") ou contém "retifica" sem "edital";
  `edital` quando contém "edital" (um edital apenas "retificado" continua edital);
  senão `outro` (resultado, comunicado, aviso etc.).
- Identidade do concurso: `competition_id` = slug (estável), `source_url` = URL da
  página individual (canônica por concurso), garantida por `ensure_observation`.

Rede (injetável):

- `catalog_url(page)`, `fetch_catalog(page)`, `fetch_detail(slug)` — UA, HTTPS,
  limite de bytes, decodificação robusta.

Descoberta multi-concurso:

- `discover(db_path, catalog_html, *, catalog_fetcher, detail_fetcher, max_pages,
  max_new_details, discovered_at)`:
  1. Percorre páginas do catálogo até o fim real (página sem entradas) ou `max_pages`.
  2. Deduplica entradas por slug.
  3. Para cada entrada, garante a observação (`ensure_observation`), com identidade
     **por concurso** (`competition_id = slug`), preservando a proveniência da FGV.
  4. Consulta a página de detalhe **apenas de concursos novos** (sem documentos),
     limitado a `max_new_details` por ciclo — evita baixar todo o histórico.
  5. Emite candidatos: um por documento (PDF) do concurso, com `kind`, `title`,
     `published_at` (data da página), `official_url` (PDF) e `discovery_url` (página).

## Integração com o monitoramento

`monitoring._run_source` ganha suporte a fonte **multi-concurso**
(`source["multi_contest"]`): o `discover` recebe `db_path` e devolve candidatos que
carregam o próprio `observation_id`; o ciclo acompanha `known_ids` por observação e
baixa apenas **documentos novos** (`download_new_only`), sem rebaixar o histórico.

Métricas distinguem **novidade de descoberta** (concurso que não existia) de
**enriquecimento documental** (documentos de concurso já conhecido), refletidas em
`documents_new` e no resumo por fonte.

## Extração de vagas e revisão

Reutiliza `document_extract` + `vacancy_tables` (Fase 8) sobre os PDFs/HTML
recuperados. Nada é confirmado automaticamente; toda proposta exige revisão humana
(`reviews`/`valores_atuais`). Se o catálogo exibir um número e o edital outro,
prevalece o documento, com divergência registrada — o número do catálogo não é
promovido.

## Identidade e deduplicação

- Cada concurso da FGV tem identidade própria (`competition_id = slug`), nunca
  fundida por semelhança de título.
- A proveniência do DOU e da FGV coexistem; associar um mesmo certame entre fontes
  é decisão explícita (não automática nesta fase).
- Reexecução é idempotente: `ensure_observation` e `register_document` são
  idempotentes; concursos conhecidos não geram candidatos nem versões novas.

## Limites conhecidos

- Catálogo inclui certames antigos/encerrados; o **estado do catálogo** é registrado
  como veio da fonte, separado do estado consolidado do Radar. Ausência de uma
  página **não** é prova de cancelamento.
- Retificação só é associada com evidência (título/número); caso contrário fica
  pendente. Não se associa automaticamente toda publicação posterior ao edital.
- PDFs grandes podem ser lentos; o ciclo limita páginas e detalhes novos.
- Somente páginas sob `/concursos/` são aceitas (mantém a allowlist restrita);
  processos fora desse prefixo ficam fora de escopo nesta fase.
- PDF digitalizado (sem texto) permanece não extraível (sem OCR).

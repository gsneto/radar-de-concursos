# Extração de vagas por cargo e modalidade (DOU) — desenho e decisão

Data: 2026-10-16

## Intenção

A Fase 7 passou a descobrir e registrar publicações do DOU (Seção 3). A Fase 8
melhora a **extração** desses documentos: transformar o texto/tabela do edital em
**propostas de vagas por cargo**, com evidência, mantendo a incerteza quando a
informação não é sustentada. **Prioridade absoluta: precisão.** É preferível deixar
um número desconhecido, com evidência e justificativa, a atribuí-lo ao cargo errado.

Não-objetivos: cobertura nacional, OCR de PDF digitalizado, cálculo de cotas por
percentual como valor oficial, associações de cargo por similaridade, terceira fonte.

## Diagnóstico do estado real (2026-10-16)

- O `content` do JSON da "Leitura do Jornal" é **truncado (403 chars)** e sem
  tabelas/links. O **texto completo** está na página do artigo
  (`https://www.in.gov.br/web/dou/-/{urlTitle}`), dentro de `<div class="texto-dou">`,
  com `<p class="identifica">`/`<p class="dou-paragraph">` e, quando houver, `<table>`.
- A extração atual (`document_fields._table_proposals`) exige cabeçalho fixo
  (`VAGAS TOTAIS` + `INDÍGENA`) e colunas em posição fixa; ignora a tabela simples
  `CARGO | CARGA HORÁRIA | VAGAS` (presente no Anexo I real de Guajará-Mirim, com
  `69 + CR*`). Não lê modalidades em ordem diferente nem cabeçalhos multi-linha.
- Propostas por cargo do documento ficam com `role_id=None` e um rótulo em
  `ambiguity_reason` (`LABEL_PREFIX`), reconciliável por decisão humana
  (`reconcile_role_label`). Não há criação de identidade de cargo para concursos
  que não derivam de `concursos` v1 (caso do DOU).
- O modelo de campos (`document_store._FIELDS`) admite apenas:
  `education`, `immediate_vacancies`, `reserve_vacancies`, `indigenous_vacancies`,
  datas e locais. Modalidades como PCD/negros/quilombolas **não** existem no modelo;
  não serão inventadas nesta fase.

## Arquitetura

### 1. Extrator genérico de quadro de vagas — `radar/vacancy_tables.py` (novo)

Formato-agnóstico (recebe **linhas de células**, não HTML nem PDF):

- `normalize(text)` — maiúsculas, sem acento, espaços colapsados.
- `detect_header(rows)` — acha a linha de cabeçalho: exige um token de **cargo**
  (`CARGO`, `ESPECIALIDADE`, `FUNÇÃO`, `EMPREGO`, `ÁREA`) e ao menos um token de
  **quantidade** (`VAGAS`, `TOTAL`, `INDÍGENA`, `RESERVA`, `CR`, `IMEDIATAS`).
- `map_columns(header)` — mapeia `field → coluna` **independente de ordem**:
  `indigenous_vacancies` (INDÍGENA), `reserve_vacancies` (CADASTRO DE RESERVA/RESERVA,
  e `CR` **apenas como palavra isolada** — não casa CRECHE/INSCRIÇÕES),
  `immediate_vacancies` (VAGAS TOTAIS/VAGAS IMEDIATAS/IMEDIATAS/VAGAS). `AMPLA
  CONCORRÊNCIA` **não** é vagas imediatas (é uma modalidade, subconjunto do total).
- `parse_quantity(cell)` — inteiro explícito (inclui `0`); `None` quando vazio ou não
  numérico. `69 + CR*` devolve `69` (a quantidade imediata); o texto do cadastro de
  reserva permanece na evidência (`quote`), sem virar número.
- `extract(rows, contest_id, page_number, section_title)` → lista de propostas:
  - Linha de cargo (rótulo ≠ TOTAL): `ambiguity_reason = LABEL_PREFIX + rótulo`.
  - Linha `TOTAL`/`TOTAL GERAL`: `ambiguity_reason = None` (fato no escopo do concurso).
  - Emite apenas as modalidades **presentes no cabeçalho**; célula vazia → **sem
    proposta** (desconhecido), nunca `0` inferido.
  - `CR` sem número → **sem** proposta de `reserve_vacancies` (não vira 0).
  - **Nunca** replica um total global em cada cargo.
  - Evidência: trecho da linha, cabeçalho, página, título de seção, rótulo do cargo.

### 2. Integração — `radar/document_fields.py`

- HTML: `_HTMLBlocks` passa a expor as linhas por **tabela** (índice) e o extrator
  genérico substitui a heurística de cabeçalho fixo, preservando a saída já
  contratada (totais `immediate=107`/`indigenous=3` e por-cargo indígena `[0,0,1,2]`)
  e **adicionando** as vagas imediatas por cargo da tabela `CARGO|...|VAGAS`.
- PDF: `_pdf_table_proposals` continua como está (quadro ancorado em `QUADRO GERAL DE
  VAGAS`); o extrator genérico é reutilizado onde houver linhas estruturadas.
- Regra inalterada: documento escopado a um cargo (`role_id` definido) **não** recebe
  propostas de tabela (o quadro é multi-cargo).

### 3. Identidade de cargo — `radar/document_store.ensure_role` (novo)

`ensure_role(db_path, contest_id, observation_id, name, specialty=None)` cria, de
forma **idempotente** e transacional, `cargos_identidade` + `observacoes_cargo`
vinculadas à observação do documento. Permite que cargos do DOU existam como
identidade própria do concurso, sem fundir cargos por similaridade. A ligação
proposta→cargo continua sendo decisão explícita (reconciliação); a identidade é
criada a partir do **próprio rótulo do documento**, não de outro cargo.

### 4. Texto completo do DOU — `radar/dou_source.py`

`fetch_article(url_title)` baixa a página do artigo (mesmo host/allowlist) e extrai o
conteúdo de `<div class="texto-dou">` (o ato oficial completo), preservando o
`content` truncado do JSON como *fallback*. A versão documental passa a guardar o
**ato oficial completo**, não a página com chrome do portal.

## Semântica de valores (mantida)

`0` confirmado ≠ ausente ≠ não extraído ≠ ambíguo ≠ pendente de revisão ≠ cadastro de
reserva sem número. Só se emite inteiro quando o documento traz o número; ausência
não vira `0`; `CR` sem número não vira vaga imediata nem zero. Nada é promovido
automaticamente: toda proposta exige revisão humana (`reviews`/`valores_atuais`).

## Limites assumidos

- O DOU frequentemente **não** contém o quadro de vagas; o edital completo e a tabela
  ficam no portal do órgão/banca (ex.: `quadrix.org.br`), que **não** está na allowlist
  e não será ampliado sem necessidade comprovada. Nesses casos o campo permanece
  desconhecido — registrado, não inventado.
- PDF digitalizado (sem texto) permanece não extraível (sem OCR).
- Modalidades além de imediatas/indígenas/reserva não têm campo no modelo; ficam fora.

## Como adicionar novas estratégias de extração

Novo extrator = nova função que produz o mesmo contrato de propostas
(`contest_id`, `role_id`, `field_name`, `value_json`, `value_type`,
`extraction_method`, `ambiguity_reason`, `evidence`) e é chamada por
`extract_field_proposals`. Nada mais precisa mudar; o armazenamento, a revisão e a
API permanecem os mesmos.

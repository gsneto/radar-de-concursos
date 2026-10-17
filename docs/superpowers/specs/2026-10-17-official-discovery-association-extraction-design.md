# Design — Fase 26: descoberta oficial, associação, local de prova e conteúdo programático

Data: 2026-10-17. Base: Fase 25 publicada (`5d10cbb`), schema v14, 1062 testes.

## Diagnóstico que orientou a fase

A Fase 25 mediu o funil: 593 concursos → 499 com documento → **16 com edital oficial** → 15 com
propostas → **0 campos validados**. Também apontou `local_prova` e `conteudo_programatico` em
**0% mesmo entre os 16 com edital**.

Esta fase foi investigar *por quê*. As duas causas foram **comprovadas no código e nos dados**,
não presumidas:

### Causa 1 — o texto de PDF perde todas as quebras de linha

`radar/document_extract.py:97` faz `' '.join((page.extract_text() or '').split())` para cada
página. Resultado medido: as 74 páginas do edital do TJ-AP têm **74 blocos e 74 linhas** — uma
"linha" por página, com 2.500–5.000 caracteres.

`radar/program_content.py` percorre `text.split("\n")`. Com uma linha por página, a linha começa
no cabeçalho do PDF (`TRIBUNAL DE JUSTIÇA ... 51 ANEXO I – CONTEÚDO PROGRAMÁTICO ...`), nunca é
reconhecida como título de seção, e **nenhuma seção é aberta**. Por isso 0 propostas, mesmo com o
anexo inteiro presente no documento.

Prova: `is_content_heading()` retornava `False` para todas as 74 linhas; `extract_program_content`
devolvia `[]`.

### Causa 2 — não existia extrator de local de prova

`radar/location.py` apenas **interpreta** propostas existentes (`resolve_location`). Nenhum
módulo produzia `exam_location`/`exam_municipio`/`exam_uf`. O campo estava em 0% porque nunca foi
extraído — não porque o dado faltasse.

Prova: grep por `exam_location` em `radar/*.py` só encontrava leitura (`location.py`,
`priority.py`, `data_quality.py`).

### Causa 3 — associação: o DOU registra a **seção** como se fosse um concurso

`radar/dou_source.py:27` define `DOU_COMPETITION_ID = "DOU-S3"`, e `discover()` devolve **todos**
os atos relevantes da edição diária com a mesma `observation_id`. Medido no banco: o concurso
`54568dbc…` tem `competicao_id = DOU-S3`, 10 documentos e **9 classificados como edital**
("EDITAL, DE 15 DE OUTUBRO", "EDITAL Nº 19 - TCU/TEFC", "AVISO DE LICITAÇÃO", "EDITAL DE
CONVOCAÇÃO Nº 20/2026"…) e zero propostas.

Não é falha de extração: é uma identidade artificial. Cada ato é de um órgão diferente.

## Decisões

### 1. Segmentação inline em vez de mudar o extrator de PDF

Alterar `extract_blocks` para preservar `\n` mudaria o texto dos blocos e invalidaria as
evidências já gravadas (offsets e hashes). Rejeitado.

Escolha: `program_content.logical_lines()` re-segmenta o parágrafo **sem criar caractere** —
corta antes de `ANEXO … CONTEÚDO PROGRAMÁTICO`, de `BLOCO N`, de `CARGO:` e de itens numerados
cujo número não seja continuação de `art. 5` / `nº 3` / `inciso`. Como cada pedaço é uma fatia
literal do original, a evidência continua verificável.

### 2. `local_prova` com regras explícitas de rejeição

Aceita: "as provas serão realizadas na cidade de X", "a aplicação ocorrerá na cidade de X",
"nas cidades de X e Y", "município de X", "em X/UF".

Rejeita (e há teste para cada): heteroidentificação/entrevista/atendimento especial, "horário
oficial da cidade de Brasília", "sede do órgão/banca", **lotação/local de exercício**, e passado
("foram divulgados").

Registra `a_divulgar` quando o edital declara publicação futura dos locais — informação
declarada, não ausência.

Lista de cidades nunca é reduzida: vira um valor único com todas (`Colatina/ES; Guarapari/ES;
Vitória/ES`), e `exam_municipio` só existe quando há **um** município.

### 3. Reprocessamento aditivo, nunca reanálise

`record_analysis` recusa versão já analisada — e deve continuar recusando, porque reescrever
blocos quebraria evidências existentes. `radar/reprocess.py` lê os blocos gravados, gera
propostas, **valida `texto[inicio:fim] == citação`** e insere apenas o que não existe.

Chave de idempotência: `(field_name, value_json, block_id, quote)`, revalidada **dentro** da
transação `BEGIN IMMEDIATE` para não duplicar sob concorrência.

### 4. Classificação documental: agregador nunca é ato oficial

`classify_document(title, url)`: se o host é agregador conhecido, o tipo é `pagina_agregador`
**mesmo que o título diga "Retificação"** — a notícia que anuncia não é o ato. Em host de
banca/órgão, o título manda. `kind` nunca é alterado (afeta associação e ranking).

### 5. Associação: diagnóstico, não correção automática

`radar/association.py` aponta: identidade de seção de diário, muitos atos sem propostas, títulos
divergentes, URL compartilhada entre concursos, documento sem observação. Somente leitura.
Corrigir associação por semelhança de título é proibido pelo domínio.

## Contratos (aditivos)

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/associacoes` | associações suspeitas com evidência |
| POST | `/api/documentos/tipos` | preenche `tipo_documental` nulo (`dry_run` padrão) |
| POST | `/api/documentos/reprocessar` | reprocessa editais analisados (`dry_run` padrão) |

CLI: `associacoes`, `documentos-tipos [--apply]`, `documentos-reprocessar [--apply] [--limit]`.

`GET /api/concursos` permanece com os 18 campos.

## Critérios de aceite

- `local_prova` sai de 0% para > 0 entre os concursos com edital, com evidência por página.
- `conteudo_programatico` sai de 0% para > 0, com itens rastreáveis.
- Nenhuma proposta nova nasce sem `ambiguity_reason`.
- Reprocessar duas vezes não duplica nada; blocos e evidências antigos intactos.
- Associação suspeita identificada e visível, sem correção automática.

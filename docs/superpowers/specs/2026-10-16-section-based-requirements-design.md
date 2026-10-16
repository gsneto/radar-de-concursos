# Fase 16 — Requisitos por seção sem código, mapeamento por nível/especialidade e elegibilidade

Data: 2026-10-16. Base: `f77779f` (Fase 15), 492 testes OK.

## Problema

A Fase 15 resolvia códigos individuais, listas e faixas (`400 ATÉ 406`). Restavam editais
que publicam os requisitos em **seções numeradas sem código** por cargo, permanecendo
`nao_extraido`.

## Diagnóstico (casos reais reproduzidos)

| Edital | Estrutura real | Antes |
|---|---|---|
| 3056 (Sedes/DF) | Corpo: `2.4 … (CARGO 400)` + `2.4.2 Requisitos:` (subitem **numerado**) | 0 requisitos |
| 3073 (Valença) | Corpo: `3.2 PROFESSOR IV – ARTE` (**sem código**) + `3.2.1 Requisitos:` | 0 requisitos |
| 3057 (Cristalina) | Corpo: `3.3 ASSISTENTE SOCIAL ESCOLAR` (sem código) + `3.3.1 Requisitos:` | 0 requisitos |

Causa: o parser dependia de `(CÓDIGO NNN)` + `a) Requisitos`. Estes editais usam
`(CARGO NNN)` (ou nenhum código) e subitens numerados `N.M.k Requisitos:`.

## Modelo: seções numeradas (`radar/section_requirements.py`)

1. **`parse_sections`** divide o texto em seções `N.M NOME` (o nome termina no primeiro
   subitem `N.M.k`; `(?<![\d.])` evita casar o `N.M` interno de `N.M.k`). Código embutido
   (`(CARGO 400)`, `(CÓDIGO 400)`, `(CÓDIGOS 200 ATÉ 206)`) é extraído do nome.
2. **`_requirement_value`** casa o subitem `N.M.k Requisitos:` cuja numeração corresponde à
   seção — a **numeração** é a âncora estrutural, não a proximidade textual.
3. **`extract_section_education`** emite `education`/`accepted_courses`/`si_compatibility`
   por seção. Seção **com** código → rótulo por código (identidade pelo fluxo de código).
   Seção **sem** código → rótulo pelo **nome**.

## Associação por nome (nunca por escolaridade)

`reconcile_sections_by_name` liga seções sem código à tabela oficial:

| Estado | Condição | Ação |
|---|---|---|
| `explicita` | nome igual a **um** cargo oficial | associa `role_id` |
| `ambigua` | nome igual a **vários** cargos | não associa; registra candidatos |
| `revisao` | sem igualdade, tokens significativos com **um** cargo | candidata; **não** associa |
| `sem_cargo` | nenhuma correspondência | não associa |
| `sustentada` | (reservado) categoria com correspondência oficial inequívoca | — |

**Regra central:** a escolaridade **nunca** é chave de identidade. Nível superior comum a
vários cargos não os funde. O nome da seção (referência textual explícita) é o sinal.

## Fluxo de produção

`document_fields.extract_field_proposals` chama `extract_education` (Anexo II por código) **e**
`extract_section_education` (seções numeradas). `role_reconciliation.link_contest_proposals`
aplica **duas** camadas na ordem correta (após persistir as propostas): por **código** e,
para as pendentes, por **nome de seção**.

## Preservação

- Códigos individuais/listas/faixas (Fase 15): intactos; `parse_code_group` passou a aceitar
  o marcador `CARGO`.
- Vagas indígenas (`indigenous_vacancies` × `indigenous_reserve_vacancies`): inalteradas.
- Prazos de isenção (`exemption_*`): inalterados; a seção de requisitos não os captura.
- API v1 (18 campos): inalterada. Nada promovido a validado sem revisão humana.

## Limitações

- Seção cujo nome corresponde a vários cargos (variantes de localidade) fica `ambigua`
  (não se propaga indiscriminadamente).
- Seção por **nível/categoria** (ex.: "CARGOS DE NÍVEL SUPERIOR") sem cargo específico
  permanece sem associação — não se usa escolaridade como chave.
- Se a extração de PDF perder o vínculo seção↔subitem, a relação fica pendente.

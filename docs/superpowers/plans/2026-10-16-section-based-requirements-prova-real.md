# Prova real — Fase 16: requisitos por seção sem código

Data: 2026-10-16. Banco **temporário** isolado (`%TEMP%\f16p-*`). Downloads reais.
Script: `%TEMP%\opencode\proof16.py`. Fluxo de produção: analisar → reconciliar
(`link_contest_proposals`, por código e por nome).

## Documentos processados (Quadrix, editais reais)

| Certame | sha256 (12) | bytes | págs | cargos HTML | education | vinculadas |
|---|---|---|---|---|---|---|
| 3073 (Valença) | `40f57dcb5ec0` | 682.861 | 34 | 10 | **10** | 29 |
| 3057 (Cristalina) | `207f0fb0cd4d` | 790.668 | 44 | 30 | **11** | 14 |
| 3056 (Sedes/DF) | `a806bfe7cabd` | 921.728 | 61 | 15 | **10** | 29 |

Antes da Fase 16: **0 requisitos** em todos (dependiam de `(CÓDIGO NNN)` + `a) Requisitos`).

## Caso principal — 3073 (seção **sem** código)

Seções reais: `3.1 PROFESSOR III`, `3.2 PROFESSOR IV – ARTE`, …, `3.10 PROFESSOR IV – MATEMÁTICA`.
Cada uma com `N.M.1 Requisitos: …`.

- `parse_sections` → 10 seções com nome; `extract_section_education` → 10 `education`.
- `reconcile_sections_by_name`: **`explicita=29`, `ambigua=0`, `sem_cargo=0`**, 10 cargos
  persistidos, 29 propostas vinculadas. O nome da seção (`PROFESSOR IV – ARTE`) casa
  exatamente com o cargo oficial (`Professor IV - Arte`).
- Exemplo (PROFESSOR IV – MATEMÁTICA): `education = "Diploma, devidamente registrado, de
  conclusão de curso de nível superior de Licenciatura em Matemática."`.

## Caso com código — 3056 (`(CARGO NNN)` + subitem numerado)

- `reconcile_proposals_by_code`: `assigned=29, created=10` (10 cargos, via código oficial).
- Requisito real: `2.4.2 Requisitos: Diploma … de graduação … em Administração.` associado
  ao cargo 400.

## Caso misto/ambíguo — 3057 (variantes de localidade)

- `by_code assigned=2`; `by_name explicita=12, ambigua=14`.
- As 14 ambiguidades são seções cujo nome corresponde a **vários** cargos oficiais com
  sufixo de localidade (ex.: `Assistente Social Escolar` × `… – Zona Urbana`). Não se
  propaga indiscriminadamente — permanecem pendentes, com candidatos registrados.

## Sistemas de Informação

`si_compatibility` classificado por seção, com evidência. Ex.: seção com requisito
"…área de Tecnologia da Informação, tais como Ciência da Computação, Sistemas de
Informação…" → `aceito_expressamente`; seção de Licenciatura em Matemática →
`incompativel_com_requisito_explicito`/`ambiguo` conforme o texto. Nada validado.

## Integridade

- Vagas indígenas e prazos de isenção: extraídos no mesmo fluxo, sem interferência
  (teste de integração `test_pipeline_includes_section_education_and_exemption`).
- Escolaridade **não** é chave de identidade (teste `test_schooling_alone_does_not_associate`).

## Reprocessamento

`[idem] 3073: propostas vinculadas 29→29 | recon repetida = 0 novas` — idempotente.
Reanálise da versão é recusada ("versão já analisada").

## Limitações

- 3057: 14 seções ambíguas (localidade) permanecem pendentes — conservador.
- 3056: 10 de 15 cargos extraídos (alguns cabeçalhos de seção atravessam páginas).
- Seção por nível/categoria sem cargo específico não é associada (não se usa escolaridade).
- A base habitual do usuário (`data/`) não existe; a prova usa banco temporário.

# Fase 17 — Requisitos entre páginas e associação auditável

Data: 2026-10-16. Base: `8171616` (Fase 16), 512 testes OK.

## Problema

No certame 3056 (Sedes/DF) só 10 de 15 cargos tinham requisitos. A causa: o parser de
seções operava **por bloco de página**, então um cabeçalho de seção no fim de uma página
(`2.3 … (CARGO 202)`) não casava com o subitem `2.3.3 Requisitos:` que caía na **página
seguinte** — a numeração da seção e a dos subitens ficavam em blocos diferentes.

## Frente A — reconstrução do contexto entre páginas

`section_requirements.build_logical_document(blocks)` junta os blocos (páginas) num
**texto lógico**, preservando um mapa de offsets `{block_index, page_number, start, end}`.
A seção passa a ser reconhecida no documento lógico, mas a **evidência continua ancorada
ao bloco/página** onde o requisito aparece.

Duas salvaguardas tornam a junção **conservadora** (sem falsas continuações):

1. **Regex de seção sem ponte**: o nome da seção não pode conter outro `N.M` nem
   atravessar quebra de linha/página, e precisa **começar por letra maiúscula**
   (`[A-ZÀ-Þ]`), como nos cabeçalhos reais de cargo. Sem isso, `finditer` sobre o
   documento inteiro casava referências cruzadas distantes (ex.: "conforme o subitem
   1.2 … 1.2.3") ou números no meio de frases (ex.: "o valor e 3.2 reais") e **engolia**
   ou criava seções.
2. **Ancoragem por numeração**: o subitem de requisitos é casado por `N.M.k` cuja
   numeração corresponde à seção — não por proximidade.

Só blocos de **página** (`page_number` não nulo) entram no documento lógico; linhas de
tabela/parágrafos HTML ficam de fora. O `block_index` da evidência referencia a lista
**original** de blocos (mapeado a partir do índice no documento lógico).

Quando o valor do requisito atravessa a fronteira de página, a evidência é **truncada no
bloco inicial** (nunca se inventam offsets fora do bloco) e a proposta recebe a anotação
"continua na página seguinte".

## Hierarquia e escopo (Frente B/C)

Cada proposta mantém o **rótulo da seção** (`role_label`) que delimita seu escopo. A
hierarquia é preservada pela numeração: `N.M` (cargo/seção) e `N.M.k` (subitem). Uma nova
seção encerra o escopo anterior (`body_end` = início da próxima seção), então requisitos
não se propagam indefinidamente.

**Associação (auditável, nunca por escolaridade):**

| Estado | Condição |
|---|---|
| `explicita` | nome da seção = **um** cargo oficial (ou código oficial) → associa `role_id` |
| `ambigua` | nome = vários cargos, ou conflito de identidade → não associa |
| `revisao` | tokens em comum com **um** cargo → candidata; não associa |
| `sem_cargo` | nenhuma correspondência |

A escolaridade resumida do HTML **não** é chave de identidade nem prova de que cargos
compartilham formação.

## Correção de robustez

`role_reconciliation._clean_label` removia a **primeira anotação da lista**, não a mais à
esquerda no texto. Com a nova anotação de continuidade, o motivo de SI
(`… — continua na página seguinte — requisitos presentes`) mantinha o sufixo e o nome
deixava de casar. Corrigido para cortar na anotação **mais à esquerda**.

## Preservação

- Códigos individuais/listas/faixas (Fases 15–16): intactos.
- Vagas indígenas (`indigenous_vacancies` × `indigenous_reserve_vacancies`) e prazos de
  isenção (`exemption_*`): inalterados (testes de regressão).
- API v1 (18 campos): inalterada. Nada promovido a validado sem revisão humana.

## Limitações

- Seções por **nível/categoria** sem cargo específico (ex.: "CARGOS DE NÍVEL SUPERIOR")
  continuam **não associadas** — não se usa escolaridade como chave. Nos editais reais da
  amostra os requisitos são por cargo, mesmo quando há cabeçalho de nível.
- Nomes de seção que correspondem a vários cargos (variantes de localidade) permanecem
  `ambigua`.
- PDF cujo texto não preserva a numeração da seção não é reconstruído (fica pendente).

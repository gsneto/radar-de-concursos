# Prova real — extração de vagas por cargo (Fase 8)

Data da execução: 2026-10-16

## Objetivo

Demonstrar com **documentos reais** que o Radar extrai cargos e quantidades de vagas
por modalidade, com evidência, deixando o desconhecido explícito. Banco **temporário**
isolado (`%TEMP%\radar8-*`); a base habitual do usuário não é tocada.

## A) Artigo do DOU — texto oficial completo

- Matéria: `EDITAL DE 30 DE SETEMBRO DE 2026` (Seção 3).
- URL: `https://www.in.gov.br/web/dou/-/edital-de-30-de-setembro-de-2026-735872523`
- HTTP 200; **texto-dou = 5.601 bytes** em ~9,7 s (o `content` do JSON da edição é
  truncado em **403 chars** e sem tabelas/links).
- `extract_blocks` → 14 blocos; `extract_field_proposals` → **0 propostas**.
- Interpretação: este aviso **não** contém quadro de vagas; nenhum número foi
  inventado. O campo de vagas permanece **desconhecido**, com o texto integral
  registrado como evidência da versão.

## B) Quadro de vagas real (Anexo I do edital 001/2026, Guajará-Mirim)

- Documento: `Anexo I — Quadro de vagas` (HTML público real do Diário Oficial dos
  Municípios/RO, matéria `3E102D15`).
- Processado ponta a ponta no banco temporário: `register_document` → `record_version`
  → `extract_blocks` (16 blocos) → `extract_field_proposals` → `record_analysis`.
- **12 propostas persistidas**, sem nenhuma confirmação automática
  (`current_values = 0`).

Vagas imediatas por cargo (rótulo do documento; `role_id=None`, reconciliável):

| Rótulo (documento) | Vagas imediatas | Vagas indígenas |
|---|---|---|
| Prof. Magistério Nível II 30 h – Educação Infantil | 69 | 2 |
| Prof. Magistério Nível II – Ens. Fundamental (Anos Iniciais) | 32 | 1 |
| Prof. Magistério Nível II – Intérprete de Libras | 3 | 0 |
| Prof. Magistério Nível II – Professor de Braille | 3 | 0 |
| **TOTAL** (escopo do concurso) | **107** | **3** |

- O quadro de cotas (`VAGAS TOTAIS | PCD | NEGROS | INDÍGENAS | QUILOMBOLAS | AMPLA`)
  fornece vagas imediatas **e** indígenas por cargo; o total (107/3) fica no escopo do
  concurso e **não** é replicado por cargo.
- A tabela simples `CARGO | CARGA HORÁRIA | VAGAS` (com `69 + CR*`) é reconhecida, mas
  o documento tem um quadro de cotas **mais completo**, então só ele é usado — o mesmo
  fato não é contado duas vezes. `CR*` **não** vira `0` nem vaga imediata.
- Hash/versão: a versão guarda o SHA-256 do conteúdo; a identidade é estável.

## C) Identidade de cargo e idempotência

- `ensure_role(...)` criou a identidade do cargo a partir do rótulo do documento de
  forma **idempotente** (`role_id` idêntico na repetição).
- Reprocessar o **mesmo conteúdo** não cria versão nova (`record_version` devolve a
  mesma versão) e não altera a contagem de propostas (12 → 12).

## D) Contrato v1

- A tabela `concursos` (18 campos) **não** existe no banco da fonte DOU: a extração
  documental não escreve no contrato v1. `GET /api/concursos` permanece inalterado
  (verificado pela suíte).

## Casos de cobertura da prova

| Caso pretendido | Resultado real |
|---|---|
| Edital com tabela de cargos e vagas | **Sim** (Anexo I: 69/32/3/3 + TOTAL 107) |
| Vagas indígenas por cargo | **Sim** (2/1/0/0), total 3 no escopo do concurso |
| Cadastro de reserva | **Parcial**: `69 + CR*` reconhecido e **não** convertido; sem número por cargo |
| Indígena global não distribuída | Coberto por teste sintético (coluna só na linha TOTAL) |
| Documento cuja extração é insuficiente | **Sim**: aviso do DOU sem quadro → 0 propostas, campo desconhecido |
| Retificação real associada | **Não comprovado** (nenhuma retificação referenciável nesta amostra); vínculo segue sob revisão humana |

## Limitações observadas

- O DOU frequentemente publica apenas o aviso; o edital completo e a tabela ficam no
  portal do órgão/banca (ex.: `quadrix.org.br`), **fora** da allowlist — não ampliada
  sem necessidade comprovada. Nesses casos o campo permanece desconhecido.
- PDF digitalizado (sem texto) não é lido (sem OCR).
- A associação de retificação a concurso exige evidência (órgão, número, ano) e
  continua sendo decisão humana; não foi comprovada com documento real nesta amostra.

## Reprodução

Script: `%TEMP%\opencode\proof8.py` (fora do repositório). Testes automatizados
equivalentes (sem rede): `tests/test_vacancy_tables.py`, `tests/test_document_extract.py`,
`tests/test_document_extract_real.py`, `tests/test_dou_source.py`,
`tests/test_document_reconcile.py`.

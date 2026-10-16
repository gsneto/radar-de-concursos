# Fase 15 — Códigos agrupados, requisitos multibanca e elegibilidade comprovada

Data: 2026-10-16. Base: `21d875f` (Fase 14), 467 testes OK.

## Causa comprovada dos requisitos ausentes

Os editais da Quadrix agrupam cargos por bloco de código no Anexo II:

```
1.1 PROFISSIONAL DE SUPORTE TÉCNICO (PST)-ASSISTENTE ADMINISTRATIVO (CÓDIGOS 200 ATÉ 206)
    a) Requisitos: ...
2.1 PROFISSIONAL ANALISTA SUPERIOR (PAS)-AGENTE FISCAL (CÓDIGOS 400 ATÉ 406)
    a) Requisitos: ...
```

O parser da Fase 14 só reconhecia o **singular** `(CÓDIGO 404)`. Blocos com `CÓDIGOS … ATÉ …`
não eram interpretados — no certame 3049 (CRECI-ES), isso deixava **14 dos 22 cargos**
sem requisitos (200–206 e 400–406).

## Frente A — parser de códigos individuais, listas e faixas

`radar/edital_requirements.parse_code_group(clause)` interpreta o bloco de códigos com
gramática conservadora:

- **Individual:** `CÓDIGO 404` → `["404"]`.
- **Faixa:** `CÓDIGOS 200 ATÉ 206`, `400 A 403`, `400-403`, `400–403` → expansão.
- **Lista:** `CÓDIGOS 400, 401 E 402` → `["400","401","402"]`.

Guardas: exige o marcador `CÓDIGO(S)`; só expande faixa com marcador explícito entre dois
números e amplitude plausível (≤ 60); zeros à esquerda preservados; **nunca** inventa
códigos. `_CARGO_HEAD` passou a capturar o bloco `(CÓDIGOS …)`; a proximidade de
`a) Requisitos` (≤ 60 chars) continua separando requisitos de **conteúdo programático**
(`... (CÓDIGO NNN): 1 Fundamentos...`).

### Expansão e proveniência

Um bloco vale para **todos** os códigos do conjunto: gera-se uma proposta por código,
todas com a **mesma evidência** cujo `quote` inclui o bloco literal
(`CÓDIGOS 400 ATÉ 406) a) Requisitos: ...`). A associação ao cargo é feita **por código**
(`role_reconciliation`), nunca por nome. Códigos da faixa ausentes no HTML oficial ficam
`pending` e são listados em `missing_codes` (não se cria cargo inexistente).

## Frente B — extração multibanca

Camada comum (`extract_education`, Anexo II por código) + complemento genérico
(`extract_declared_education`) para formatos que declaram a escolaridade por **rótulo**
(ex.: FGV: `Requisitos de escolaridade … Nível Superior – Direito`). O complemento só roda
quando o Anexo II por cargo não produziu requisitos. É conservador: exige rótulo explícito
e palavra de nível; a proposta fica no escopo do concurso (`role_id=None`), sem associação
indevida a cargo. Anexos de conteúdo programático **não** são tratados como requisitos.

## Frente C — elegibilidade

Estados preservados: `aceito_expressamente`, `abrangido_por_categoria`,
`incompativel_com_requisito_explicito`, `ambiguo`, `nao_extraido`, `nao_informado`.
Uma menção a "Sistemas de Informação" em conteúdo programático não é evidência de
elegibilidade. Nada é promovido a validado sem revisão humana.

## Campos preservados

- Vagas indígenas: `indigenous_vacancies` (imediatas) e `indigenous_reserve_vacancies`
  (cadastro de reserva) — semânticas **inalteradas**.
- Isenção da taxa: `exemption_start/end/result_preliminary/appeal/result_final` —
  inalterados (teste de regressão dedicado).
- API v1 (`GET /api/concursos`, 18 campos): **inalterada**.

## Limitações

- A faixa é expandida apenas quando o marcador e a amplitude são plausíveis; expressões
  ambíguas ficam sem expansão.
- O complemento por rótulo cobre formas explícitas; requisitos embutidos em tabelas com
  cabeçalhos intercalados podem exigir revisão.
- Cargos sem `(CÓDIGO NNN)` no Anexo II (ex.: códigos agrupados por nome de seção, sem
  código) permanecem sem requisito — campo desconhecido, nunca "incompatível".

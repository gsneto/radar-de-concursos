# Prova real — Fase 14: reserva indígena, identidade por código, formação e isenção

Data: 2026-10-16. Banco **temporário** isolado (`%TEMP%\f14p-*`); a base habitual não é
tocada. Downloads reais. Script: `%TEMP%\opencode\proof14.py`.

## Documentos processados (Quadrix, editais reais)

| Certame | documento | sha256 (12) | bytes | páginas | cargos HTML | propostas |
|---|---|---|---|---|---|---|
| 3052 (CRQ-9ª/PR) | edital_abertura | `4549b5a3e38e` | 743.673 | 41 | 10 | 62 |
| 3050 (CRQ-RS) | edital_retificado | `7c35c723e770` | 798.671 | 43 | 14 | 84 |
| 3049 (CRECI-ES) | edital_abertura | `58d6fde13390` | 795.700 | 43 | 22 | 117 |

Totais: **46 cargos** criados, **200** reutilizados, **3** ambíguos, **0** pendentes,
**263 propostas**.

## Identidade por código (HTML ↔ PDF)

- Reconciliação por **código oficial**, contextualizada pelo concurso; nome como
  verificação. 3052: `created=10 reused=47 ambiguous=0`; 3049: `created=22 reused=90`.
- **3050** exercitou o caminho ambíguo em dados reais: `ambiguous=3` (nome do PDF
  materialmente incompatível com o do HTML / código com mais de um candidato) — a proposta
  permaneceu **pendente**, sem associação silenciosa.
- **Idempotência:** reexecutar sobre 3052 → cargos 10→10, `reused=1 created=0`.

## Reserva indígena imediata × cadastro de reserva

Exemplos reais (coluna `PI` presente):

| Certame | Cargo | `indigenous_vacancies` (imediato) | `indigenous_reserve_vacancies` (reserva) |
|---|---|---|---|
| 3052 | 404 Analista de Informática | 0 | **1** |
| 3050 | 401 Analista de Informática | 0 | **1** |
| 3049 | 407 PAS-Analista de T.I. | 0 | **2** |

Em **todos** os cargos amostrados a vaga indígena imediata é **0** (zero confirmado,
coluna presente) e a reserva indígena é **1–2** — confirma o achado da Fase 13 de que a
reserva indígena está no cadastro de reserva.

## Formação e Sistemas de Informação

| Certame | Código | Cargo | `si_compatibility` | Evidência (trecho) |
|---|---|---|---|---|
| 3052 | 404 | Analista de Informática | **aceito_expressamente** | "…na área de Tecnologia da Informação, tais como Ciência da Computação, **Sistemas de Informação**, Engenharia da Computação, Engenharia de Software ou outros cursos correlatos…" |
| 3050 | 401 | Analista de Informática | **aceito_expressamente** | "…Tecnologia da Informação, Ciência da Computação, **Sistemas de Informação**, Engenharia da Computação ou área correlata…" |
| 3049 | 407 | PAS-Analista de T.I. | **abrangido_por_categoria** | "…Tecnologia da Informação ou Ciências da Computação, ou curso de denominação e conteúdo equivalentes…" |
| 3049 | 208 | PST-Assistente de T.I. | **abrangido_por_categoria** | "Curso técnico em Informática, Tecnologia da Informação, Redes de Computadores… ou área correlata" |
| 3050 | 203 | Técnico de Informática | **ambiguo** | "Curso de Técnico de Informática, Manutenção de Computadores, Redes de Computadores ou área correlata." |

`accepted_courses` extraído literalmente (ex.: 3052/404 = "Ciência da Computação; Sistemas
de Informação; Engenharia da Computação; …"). Cargos de área alheia (Direito, Contabilidade)
→ `incompativel_com_requisito_explicito`.

## Prazos de isenção (complemento)

| Certame | início | fim | resultado preliminar | recurso | resultado final |
|---|---|---|---|---|---|
| 3052 | 2026-09-21 | 2026-09-22 | 2026-10-07 | 2026-10-08 | 2026-10-14 |
| 3050 | 2026-05-18 | 2026-05-19 | 2026-06-17 | — | 2026-06-24 |
| 3049 | 2026-10-05 | 2026-10-06 | 2026-10-27 | 2026-10-28 | 2026-11-05 |

Distintos do prazo de inscrição (ex.: 3052 inscrições 21/09 a 21/10). Em 3050 o período de
recurso não apareceu como linha de cronograma própria → campo ausente (não zero).

## Limitações

- Só editais cujo Anexo II usa `(CÓDIGO NNN)` produzem `education`/`si_compatibility`
  (3049: 8 de 22 cargos; cargos com códigos agrupados como "400 A 403" ficam sem
  requisito). Quando ausente, o campo é **desconhecido** — nunca "incompatível".
- `accepted_courses` é heurístico (marcador explícito); pode vir incompleto.
- A base habitual do usuário (`data/`) não existe; a prova usa banco temporário.

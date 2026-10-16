# Fase 14 — Reserva indígena, identidade de cargos por código e elegibilidade (Sistemas de Informação)

Data: 2026-10-16. Base: `bacec82` (Fase 13), 423 testes OK.

## Objetivo

Conectar três informações antes separadas: (1) o quadro de vagas do PDF; (2) a identidade
do cargo da página HTML oficial da Quadrix; (3) os requisitos de formação — com foco em
vagas indígenas (imediatas **e** cadastro de reserva), identidade por código oficial e
compatibilidade com o bacharelado em Sistemas de Informação. Inclui, por decisão do
usuário, a extração dos **prazos de isenção da taxa**.

## Frente A — Cadastro de reserva indígena (`indigenous_reserve_vacancies`)

Campo aditivo, distinto de `indigenous_vacancies` (que permanece **exclusivamente**
vagas indígenas imediatas):

- `indigenous_vacancies`: coluna indígena (`PI`/`IND`) do grupo **imediato**.
- `indigenous_reserve_vacancies`: coluna indígena do grupo **cadastro de reserva**.

Semântica preservada (não colapsar): **C** zero confirmado (coluna existe, `-` = 0);
**D** campo ausente (sem coluna indígena → **nenhuma** proposta, não zero); **F** cadastro
de reserva sem número (não vira número). Nunca se infere reserva indígena de percentual
geral.

## Frente B — Identidade de cargo por código oficial

- `cargos_identidade.code` (coluna aditiva, migração **v7**).
- `ensure_role(..., code=...)`: identidade **contextualizada pelo concurso** —
  `(contest_id, code)` quando há código; senão `(contest_id, name, specialty)`. Idempotente;
  adota um cargo homônimo ainda sem código; **levanta erro** se o código já estiver
  associado a nome materialmente diferente (não funde em silêncio).
- `radar/quadrix_source.parse_cargo_table`: lê a tabela HTML `Cód. | Vaga | Escolaridade`.
- `radar/role_reconciliation.reconcile_proposals_by_code`: associa propostas (rótulo com
  código) aos cargos do HTML **por código**; o nome é só verificação de consistência
  (tolerante a variação de formatação). Sem correspondência → `pending`; código com mais
  de um candidato ou nome incompatível → `ambiguous`. Nunca funde por similaridade.

## Frente C — Requisitos de formação e compatibilidade com SI

`radar/edital_requirements.extract_education` lê o Anexo II (`X.Y CARGO (CÓDIGO NNN) a)
Requisitos: ...`) e propõe:

- `education` — texto literal dos requisitos (com evidência).
- `accepted_courses` — cursos/categoria citada (só com marcador explícito "tais como"/
  "curso ... em"; evita capturar "curso de nível médio").
- `si_compatibility` — classificação explicável:
  `aceito_expressamente`, `abrangido_por_categoria`, `incompativel_com_requisito_explicito`,
  `ambiguo`, `nao_extraido`, `nao_informado`.

Regra-chave: **não** se conclui que um cargo de TI aceita SI só pelo título; a evidência é
o texto dos requisitos. Categoria ampla só é `abrangido_por_categoria` com abertura
explícita ("correlatos", "tais como", "ou outros"). Cabeçalhos de **conteúdo programático**
(`... (CÓDIGO NNN): 1 Fundamentos...`) não são requisitos (exige-se "a) Requisitos" logo
após o cabeçalho).

## Complemento — Prazos de isenção da taxa

`radar/edital_requirements.extract_exemption_dates` lê o **cronograma** e separa, com
campos e significados distintos (nunca confundidos com inscrição/pagamento):

- `exemption_start` / `exemption_end` (período de solicitação de isenção)
- `exemption_result_preliminary` (resultado preliminar)
- `exemption_appeal` (recurso contra o indeferimento)
- `exemption_result_final` (resultado definitivo)

A ancoragem exige **proximidade** entre a atividade e a data (a linha do cronograma), para
não capturar o texto corrido que só menciona a isenção. Datas em `YYYY-MM-DD`; o horário
fica no trecho comprobatório. Retificação posterior gera **nova** proposta (histórico
preservado), nunca sobrescreve.

## Classificação de oportunidade (explicável)

`confirmation.classify_opportunity` combina, sem pontuação opaca:

| Tier | Condição |
|---|---|
| 1 | vaga indígena **imediata** + SI compatível |
| 2 | vaga indígena em **cadastro de reserva** + SI compatível |
| 3 | vaga indígena imediata (formação não confirmada) |
| 4 | vaga indígena em cadastro de reserva (formação não confirmada) |
| 5 | SI compatível, sem vaga indígena |
| 6 | demais |

`confirmation.role_opportunities` + CLI `confirmacao-oportunidades` expõem por cargo.
Um cargo com vagas indígenas **apenas** em cadastro de reserva nunca aparece como imediato,
mas não é descartado.

## Compatibilidade

- API v1 (`GET /api/concursos`, 18 campos) **inalterada**.
- Migração v7 aditiva; leitura aceita 2..7; `code` ausente degrada para `NULL`.
- Nada promovido a validado sem revisão humana; proposta ≠ valor validado.
- Histórico documental preservado; reprocessamento idempotente.

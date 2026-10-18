# Prova real — Fase 36: carteira operacional, prazos atuais e revalidação

Data: 2026-10-18. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` — **v20 → v21**, sem perda. Backup de início (API de backup,
WAL/conexões): `data/radar.sqlite3.bak-20261018-121059` (61.444 KB, `integrity ok`, v20).

## A. Estado inicial verificado

| Item | Valor |
|---|---|
| Diretório | `C:/Users/anton/OneDrive/Desktop/radar-de-concursos` |
| Branch / HEAD | `radar-configuracao` / `1fe3741` |
| Git | limpo e sincronizado com `origin/radar-configuracao` |
| Suíte | **1.587 testes, OK** (skipped=1) |
| Schema | v20, `integrity ok`, FK vazia |
| Certames / documentos | 634 / **1.190** (o ciclo de 11:19 local já havia adicionado 240 documentos) |
| Versões / blocos / propostas | 1.055 / 16.276 / 7.585 |
| Revisões / valores vigentes / reconciliações | **0 / 0 / 0** |
| Tarefa agendada | "Radar de Concursos - Ciclo", a cada 6 h, última 11:19 local, próxima 17:19 |
| Prazos candidatos | **110** (71 expirados, 16 futuros, 14 sem data, 15 em conflito) |
| Documentos nominais | **287** (o ciclo adicionou novos) |

A base mudou entre a referência da Fase 35 (950 documentos / 6.199 propostas / 104 prazos) e a
auditoria: o ciclo agendado rodou às 11:19 local. Todos os números desta prova são do estado
de 12:11–16:45 local, com hora registrada em cada relatório.

## B. Prazos: investigados, revalidados e pendentes

Foram examinados os **16 prazos futuros** (referência 2026-10-18, America/Recife):

- **10 revalidados na fonte oficial** (`fonte_inalterada`): o documento servido hoje é
  byte-idêntico ao da coleta. São 6 de isenção (resultado/recurso) e 4 de resultado final,
  em 4 concursos (Quadrix 3049/3053/3072 e FGV TJAP).
- **6 permanecem em conflito documental** e **não foram revalidados** porque a divergência é
  de leitura, não de documento:
  - `4f495c42` — fim das inscrições: `2026-10-21`, `2026-11-26`, `2027-04-18`; início:
    `2026-10-19`, `2027-04-18`. **O menor candidato é amanhã.**
  - `4b5579c4` — fim: `2026-11-13`, `2026-10-15`, `2027-04-11`; início: `2026-10-13`,
    `2027-04-11`.
  - `637c7a90` — fim: `2026-09-28`, `2027-04-04`, `2027-02-21`; início: `2027-04-04`,
    `2026-08-28`, `2027-02-21`.
  - `7c54d7df`, `ddb0dac5`, `f4235e23` e `4a271ba4` também têm datas divergentes.
- **71 prazos passados** preservados como histórico (`passado_com_evidencia`).
- **14 sem data** (`nao_localizado`): nenhum documento autoritativo sustenta o prazo.
- **15 em conflito** no total (inclui passados).

Nenhuma proposta foi alterada. As 10 verificações foram gravadas em `revalidacoes_prazo`
(autor "operador local (Fase 36)", data 2026-10-18T15:30–15:31Z), apenas metadados.

## C. Carteira

**285 oportunidades** (concurso × cargo/rótulo) em 28 concursos.

| Prontidão | Itens |
|---|---|
| `oportunidade_historica` | 174 |
| `identidade_cargo_pendente` | 82 |
| `conflito_documental_pendente` | 26 |
| `campos_decisivos_ausentes` | 3 |

Não há `prazo_precisa_revalidacao` porque todos os futuros não conflitantes foram
revalidados. Não há `informacao_confirmada` porque não há decisão humana na base — e a fase
não fabricou nenhuma.

**Destaques**: 12 itens em 8 concursos, no máximo 2 cargos por concurso. A ordem
desempata por relevância geográfica (UF de interesse), sem excluir oportunidades distantes. Critério: edital
oficial + prazo futuro, SI expresso/categoria/correlato ou reserva indígena; rótulo que não é
cargo fica fora. Motivo de inclusão exibido por item.

## D. Conflitos

**56 grupos** (eram 53 na Fase 35; a base cresceu).

| Causa | Grupos |
|---|---|
| `documentos_diferentes_sem_ordem` | 17 |
| `mesmo_documento_valores_distintos` | 13 |
| `escopo_diferente` | 9 |
| `retificacao_posterior` | 6 |
| `cargos_diferentes_sem_identificacao` | 6 |
| `documentos_com_data_distinta` | 5 |

Por campo: `exam_location` 15, `registration_end` 14, `education` 13, `registration_start` 9,
`si_compatibility` 3, isenção 2. Prioridade: P2 16, P3 25, P4 15.

Os conflitos decisivos aparecem na carteira como `conflito_documental_pendente` (26) e no
calendário com todos os candidatos. Nenhum foi resolvido automaticamente.

## E. Campos decisivos

**Sistemas de Informação (por cargo):**

| Estado | Cargos |
|---|---|
| `explicito` | 3 (404 Analista de Informática em duas variantes de rótulo + agregado do concurso) |
| `categoria_inclui_curso` | 5 (208/407 de T.I. no Quadrix 3049) |
| `area_correlata_interpretacao` | 53 |
| `outras_formacoes` | 80 |
| `nao_encontrado` | 144 |

Aceitação expressa comprovada: **404 Analista de Informática** (Quadrix 3052), cujo edital cita
"Sistemas de Informação" no requisito. Um cargo de T.I. não contamina os demais: a carteira usa
o estado do cargo e, sem leitura, retorna `nao_encontrado`.

**Vagas indígenas:**

| Estado | Oportunidades |
|---|---|
| `apenas_reserva` | 103 |
| `mencao_sem_quantidade` | 168 |
| `nao_mencionado` | 14 |
| `explicito_imediato` | **0** |

Nenhum concurso da base atual tem vaga imediata indígena explicitamente comprovada. O estado é
do concurso (`ambito: "concurso"`), não do cargo; total agregado nunca foi convertido.

**Local de prova:** separado de lotação em todo o dossiê; `a_divulgar` é declarado, não
ausência.

## F. Documentos nominais

**287** documentos (131 só metadados, 156 com arquivo já baixado). Permanece **simulação**:
nada arquivado, apagado ou movido; nenhum conteúdo copiado. O crescimento em relação aos 191
da Fase 35 vem dos documentos adicionados pelo ciclo.

## G. UI verificada (Chromium, servidor local)

- Carteira: 25 linhas na página 1 de 285, referência 2026-10-18 (America/Recife).
- Destaques: 12 em 8 concursos.
- Prazos: 110 linhas, colunas de situação operacional, urgência e revalidação; os 10
  revalidados mostram `fonte_inalterada · 2026-10-18`.
- Dossiê: 13 seções (documentos, vagas, vagas imediatas, reserva, indígenas, formação,
  requisito, cursos, prazos, localização, lacunas, próxima ação).
- "Abrir na mesa de revisão" abre o dossiê da mesa na própria página (não JSON).
- Botão "Revalidar" testado em **cópia isolada** com uma verificação removida: gravou
  `fonte_inalterada`, autor "operador local (interface)", e a linha voltou ao estado
  revalidado.

## H. Revisão independente e correções

Achados corrigidos antes do commit:

1. **Crítico** — conflito com três leituras expunha um valor único porque a retificação tinha
   precedência. Agora retificação só resolve quando o único valor anterior é o edital de
   abertura; com terceiro valor, `valor` e `valor_candidato` ficam nulos.
2. **Importante** — dossiê herdava o SI agregado do concurso para cargos com rótulo. Agora o
   nome do cargo vem do escopo e, sem leitura, o estado é `nao_encontrado`.
3. **Importante** — indígena do concurso era usado como prioridade de cargo. Agora tem
   `ambito: "concurso"` e não entra na prioridade/destaque de cargo.
4. **Importante** — redirecionamento HTTP para outro host passava pela política. Agora é
   recusado (mesmo host e HTTPS).
5. **Importante** — filtro "sem data" no estado operacional retornava 400. Removido (a
   urgência "sem data" continua).
6. **Importante** — "Abrir na mesa" abria JSON. Agora abre o dossiê na página.
7. **Menor** — badge "confirmado" para `revalidado_na_fonte`; trocado por neutro.
8. **Menor** — índice v21 não era reparado em base já migrada; agora é garantido.
9. **Menor** — `deadline_review` usava fuso do sistema; alinhado a `America/Recife`.

## I. Testes

- Inicial: **1.587 OK** (skipped=1).
- Final: **1.637 OK** (skipped=1) — +50 em `tests/test_portfolio_f36.py`.
- Contrato `GET /api/concursos` v1 (18 campos): inalterado (teste de contrato verde).

## J. Integridade final

| Item | Valor |
|---|---|
| Schema | **v21** |
| Documentos / versões / blocos | 1.190 / 1.055 / 16.276 |
| Propostas | 7.585 |
| Revisões / valores vigentes / reconciliações | **0 / 0 / 0** |
| Revalidações registradas | **10** |
| `integrity_check` | ok |
| `foreign_key_check` | vazia |

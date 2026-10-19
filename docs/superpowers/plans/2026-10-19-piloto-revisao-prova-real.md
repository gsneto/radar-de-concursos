# Prova real — Fase 43: piloto de revisão da SEDUC-PA

Data: 2026-10-19. Base `data/radar.sqlite3`, schema v21. Branch `radar-configuracao`.

## Antes

- HEAD `7f758d9` (F42), árvore limpa, sincronizada.
- Suíte: **1.833 testes**, 1 skip, OK.
- Backup: `data/radar.sqlite3.bak-20261019-011318` (v21, `integrity ok`, FK vazia).
- Base: 1.232 documentos, 1.072 versões, 9.211 propostas, 0 revisões, 0 valores vigentes,
  0 reconciliações, 0 lotes.
- Snapshot: 2026-10-19T01:12:56-03:00.

## Depois

- Suíte: **1.867 testes**, 1 skip, OK (`RESULT OK`). 34 testes novos.
- `PRAGMA integrity_check`: `ok`; `foreign_key_check`: vazio.
- 9.211 propostas, **0 revisões, 0 valores vigentes, 0 reconciliações, 0 lotes**.
- Nenhuma decisão humana foi criada na base real.

## Piloto (16 linhas)

| Página | Regional | Cargo / formação | Casos | Total |
|---|---|---|---|---|
| 63 | REGIÃO METROPOLITANA | Professor / Matemática | PI exclusivo, modalidades diversas | 14 |
| 63 | REGIÃO METROPOLITANA | Analista de Gestão Governamental e / Administraçã o | PI/PQ, **cargo continuado** | 6 |
| 64 | ABAETETUBA | Professor / Língua Portuguesa | PI/PQ | 9 |
| 65 | ABAETETUBA | Assistente de Gestão Governamental e Educacional / Assistente de Gestão Governament al e Educacional | zero explícito | 1 |
| 65 | AFUÁ | Professor / Matemática | PPIQ | 2 |
| 66 | AFUÁ | Assistente de Gestão Governamental e Educacional / Assistente de Gestão Governament al e Educacional | zero explícito | 1 |
| 66 | ALTAMIRA | Professor / Educação Especial - AEE | PPIQ | 3 |
| 66 | ALTAMIRA | Professor / História | PI/PQ | 8 |
| 67 | BRAGANÇA | Professor / Geografia | PI/PQ | 6 |
| 67 | BRAGANÇA | Analista de Gestão Governamental e Política Educacional / Ciências Contábeis | zero explícito | 1 |
| 68 | BREVES | Professor / Filosofia | PPIQ | 3 |
| 68+69 | CACHOEIRA DO ARARI | Professor / Física | PPIQ, **multipágina (68+69)** | 3 |
| 69 | CAMETÁ | Professor / Matemática | PI/PQ | 8 |
| 70+71 | CAPANEMA | Especialista em Educação / Especialista em Educação | PI/PQ, **multipágina (70+71)** | 5 |
| 71 | CAPITÃO POÇO | Assistente de Gestão Governamental e Educacional / Assistente de Gestão Governament al e Educacional | zero explícito | 1 |
| 71 | CASTANHAL | Professor / Matemática | PI/PQ | 10 |
- **64 campos reais** (16 linhas × 4) com trecho literal, mais **18 notas sintéticas**
  (rótulos/legendas sem proposta própria) contadas à parte, nunca no denominador.
- `compromissos` registra qualquer exceção à diversidade (teto de 2 linhas por regional);
  no piloto atual a lista está vazia.
- 11 regionais, 5 cargos, 2 linhas multipágina, 1 cargo com palavra partida.
- Determinístico: duas execuções produzem os mesmos `linha_id`.

## Reconciliação assistida

- 381 linhas → **26 identidades candidatas** (cargo + formação) em **24 regionais**.
- 14 identidades de Professor (13 formações + LIBRAS), 1 Especialista, 1 Assistente,
  10 Analistas (3 Política, 3 Infraestrutura, 3 Suporte, 1 Administração).
- Todas as sugestões são `criar_identidade` (o concurso ainda não tem `cargos_identidade`).
- Avisos: `especialidade_repetida` (Assistente/Especialista), `cargo_continuado_na_formacao`
  e `formacao_recomposta` (Analista … Administração), `identidade_pendente` em todas.
- A regional **não** entra na chave da identidade; cada linha continua oportunidade própria.
- Nenhuma identidade foi criada ou reconciliada.

## Auditoria da revisão agrupada (UI real, Chromium)

Validado contra o servidor local:

| Item | Resultado |
|---|---|
| Concurso, órgão, documento, versão, hash | exibidos |
| Cargo, formação, regional, página(s) | exibidos; multipágina mostra `68+69` |
| Cabeçalho e trecho literal | exibidos |
| Valores por coluna e natureza | 8 colunas, com “exclusiva”/“unificada”/“total” |
| Total publicado | exibido separado da soma |
| Notas/legendas | PI, PPIQ e PI/PQ com o trecho da definição |
| Aviso de unificada | explícito: não é vaga exclusiva e não soma à PI |
| Efeito de confirmar | por campo |
| Histórico | aparece após a decisão (`Histórico (1)`) |
| Progresso | `1/64` após uma decisão; linha aberta não conta; nota sintética não entra |
| Retomada | recarregar com `#piloto=…&linha=…` reabre o contexto |
| Ação em lote | inexistente (um `proposal_id` por ação) |

## Decisões independentes (cópia isolada)

| Cenário | Resultado |
|---|---|
| Confirmar o total | só `immediate_vacancies` vira `validado`; PI, PPIQ e PI/PQ seguem pendentes |
| Confirmar PI | PPIQ e PI/PQ seguem pendentes |
| Rejeitar PI | decisão registrada; proposta e trecho preservados |
| Corrigir PI | original intacto (`quadro-colunas-pdf`); derivada `correcao_humana` criada |
| Marcar PPIQ ambíguo | demais campos intactos |
| Reabrir | histórico `validado → reaberto` preservado |
| Selecionar valor vigente | recusado antes de `validado`; aceito depois |
| Decidir todos os campos | identidade continua pendente (0 reconciliações) |
| Decidir uma linha | outra linha permanece intacta |

## Concorrência e evidência obsoleta

| Cenário | Resultado |
|---|---|
| Hash de evidência errado | decisão recusada |
| Decisão pela interface sem `evidence_sha256` | HTTP 400; nada gravado |
| Decisão pela interface sem evidence_sha256 | HTTP 400; nada gravado |
| Valor da proposta alterado após a abertura | decisão recusada (`evidência mudou desde a exportação`) |
| Lote aberto e valor alterado | decisão recusada pelo snapshot do item |
| Lote aberto e nova proposta no mesmo escopo | decisão recusada (`surgiu nova proposta…`) |
| Linha aberta e nova proposta no mesmo escopo | recusada por `scope_snapshot` |
| UI com evidência alterada | mensagem “Falha: evidência mudou desde a exportação”; 0 decisões gravadas |

A prova de UI foi feita numa **cópia** (`data/pilot-test-copy.sqlite3`, removida ao final);
a base real permaneceu com 0 decisões.

## Desempenho

| Operação | Frio | Quente |
|---|---|---|
| `groups` (contexto, 20 linhas) | 3,45 s | 0,33 s |
| `pilot.report` (16 fichas) | 3,60 s | 0,37 s |

Causa do frio: leitura posicional do PDF por versão (PyMuPDF) + vocabulário do edital.
Mitigação: cache em processo por `(banco, versão, parser)` e `revisao-prewarm`
(`gravacoes: 0`). O servidor passou a `ThreadingHTTPServer`, para que um painel lento não
bloqueie os demais.

## Decisões humanas reais

**Nenhuma.** 0 revisões, 0 valores vigentes, 0 reconciliações. O piloto está preparado,
não revisado (`piloto_revisado: false`).

## Arquivos, rotas, comandos

Novos: `radar/pilot.py`, `radar/identity_suggestions.py`, `tests/test_pilot_f43.py`, 4 docs.
Alterados: `radar/review_groups.py` (histórico, consequência, filtro `linha`, cache stats,
limite interno), `radar/server.py` (threads + 3 rotas), `radar/__main__.py` (4 comandos),
`web/app.js` e `web/index.html` (painel do piloto), `tests/test_ui.py` (harness).

Rotas: `GET /api/revisao/pilotos`, `/api/revisao/piloto?contest_id=&size=`,
`/api/revisao/identidades?contest_id=`, `/api/revisao/grupos?linha=`.
Comandos: `piloto-revisao`, `pilotos`, `identidades-sugeridas`, `revisao-prewarm`.

## Testes

1.833 → **1.867** (34 novos): seleção determinística e diversa, fichas, granularidade,
recomposição com prova, decisões independentes, correção/rejeição/reabertura, valor vigente,
stale por hash, lote por valor e por nova proposta, retomada, prewarm sem escrita, rotas,
contrato e UI estática + harness Node.

## Como iniciar a revisão manual

```
cd C:/Users/anton/OneDrive/Desktop/radar-de-concursos
python -m radar serve --db .\data\radar.sqlite3
```

Abrir `http://127.0.0.1:8000/`, seção **Revisão humana → Piloto de revisão**. Escolher o
edital da SEDUC-PA, clicar **Próxima linha pendente** (ou **Abrir linha**), ler cabeçalho,
trecho e avisos, preencher a justificativa e decidir **campo a campo**. Recarregar mantém a
linha aberta. Opcional: `python -m radar revisao-prewarm --contest-id f4235e23-…` antes.

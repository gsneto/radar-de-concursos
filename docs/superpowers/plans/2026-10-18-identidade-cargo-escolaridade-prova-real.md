# Prova real — Fase 39: identidade por código, escolaridade mínima e elegibilidade formal

Data: 2026-10-18. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` — **v21, sem migração**. Backup de início (API de backup):
`data/radar.sqlite3.bak-20261018-164402` (61.468 KB, `integrity ok`, v21).

## A. Estado inicial real

| Item | Valor |
|---|---|
| Diretório | `C:/Users/anton/OneDrive/Desktop/radar-de-concursos` |
| Branch / HEAD | `radar-configuracao` / `34bd380` |
| Git | limpo e sincronizado |
| Suíte | **1.702 OK** (skipped=1) |
| Schema | v21, `integrity ok`, FK vazia |
| Documentos / propostas | 1.190 / 7.593 |
| Revisões / valores / reconciliações | **0 / 0 / 0** |
| Referência | 2026-10-18T16:44-03:00 (`America/Recife`) |

## B. Diagnóstico dos rótulos pendentes

**166 rótulos** pendentes (eram 84 linhas de elegibilidade na Fase 38), por causa:

| Causa | Rótulos |
|---|---|
| `aguarda_decisao_humana` | 89 |
| `duplicata_de_identidade` | 36 |
| `sem_cargo_canonico` | 23 |
| `codigo_sem_nome` | 18 |

**125 têm sugestão estrutural**; 41 não têm candidato. A diferença 84 → 166 é de unidade: a
Fase 38 contava **linhas da matriz**; a auditoria conta **rótulos**, incluindo os só-código e os
que não geram linha de cargo. Nenhum foi reconciliado: 0 decisões humanas.

Por concurso, os maiores: quadrix-3056 (29), quadrix-3049 (44 rótulos, 22 linhas), ibfc-490
(18), quadrix-3057 (12), quadrix-3071 (12), quadrix-3073 (10), quadrix-3052 (20).

## C. Piloto Quadrix 3049 (CRECI-ES)

Documento armazenado: `Edital nº 1 (abertura)`, `anexos-r2.selecao.net.br/…/d9b6bbe8-….pdf`.

O quadro de vagas é uma tabela por código. A fase extraiu, por linha:

| Código | Cargo | Localidade | Vagas imediatas | Indígenas |
|---|---|---|---|---|
| 200 | PST-Assistente Administrativo | Cachoeiro de Itapemirim | 1 | 0 |
| 201 | PST-Assistente Administrativo | Colatina | 1 | 0 |
| 202 | PST-Assistente Administrativo | Guarapari | 1 | 0 |
| 203 | PST-Assistente Administrativo | Linhares | 1 | 0 |
| 204 | PST-Assistente Administrativo | Venda Nova do Imigrante | 1 | 0 |
| 205 | PST-Assistente Administrativo | Vila Velha | 1 | 0 |
| 206 | PST-Assistente Administrativo | Vitória | 6 | 0 |
| 207 | PST-Assistente Especializado | Vitória | 1 | 0 |
| 208 | PST-Assistente de T.I. | Vitória | 1 | 0 |
| 400–406 | PAS-Agente Fiscal | várias | 1 cada | 0 |
| 407 | PAS-Analista de T.I. | Vitória | 2 | 0 |
| 408–412 | PAS-Especialista | — | — | — |

**Cada código é uma oportunidade distinta**, com família, código, município e vagas próprios.
Nenhum foi fundido. Nenhuma vaga foi transferida entre códigos.

### Requisitos e classificação

| Código | Requisito (literal, resumido) | Nível | Classificação |
|---|---|---|---|
| 200–206 | "conclusão de curso de nível médio" | médio | **compatível por nível mínimo** (via código) |
| 207 | nível médio + curso técnico em Design Gráfico, Comunicação Visual, Produção Multimídia | técnico | **incompatível** (área específica) |
| 208 | nível médio + curso técnico em Informática/TI/Redes/Desenvolvimento ou área correlata, **ou** 6 meses de experiência em TI | técnico | **potencial** (nível difere de bacharelado) |
| 407 | graduação superior nas áreas de TI ou Ciências da Computação, ou curso equivalente | superior | **compatível por categoria** |
| 408–412 | Administração, Contábeis, Direito | superior | **incompatível** |

A leitura dos códigos 200–206 estava pendurada no rótulo só-código; a junção por código a
atribuiu ao cargo nomeado (`atribuicao: codigo_do_cargo`).

## D. Escolaridade mínima × formação específica

O classificador passou a separar nível e área. Efeito na base:

| Requisito | Antes | Depois |
|---|---|---|
| "curso de nível médio" | ambiguidade → não avaliado | **compatível por nível mínimo** |
| "superior em qualquer área" | ambiguidade | **compatível por nível mínimo** |
| "curso técnico em Design" | ambiguidade | incompatível (área específica) |
| "licenciatura com habilitação/magistério" | nível mínimo | **incompatível** (formação específica) |
| "direito de dirigir" (CNH) | exigência de Direito | **nível mínimo** |

## E. Os três candidatos "compatíveis" da Fase 38

| Cargo | Antes | Depois | Motivo |
|---|---|---|---|
| 404 Analista de Informática (Quadrix 3052) | compatível | **compatível (expresso)** | o edital cita "Sistemas de Informação" |
| 407 Analista de T.I. (Quadrix 3049) | compatível | **compatível (categoria)** | "áreas de TI … ou curso equivalente", nível superior |
| 208 Assistente de T.I. (Quadrix 3049) | compatível | **potencial (interpretação)** | exige curso **técnico**; bacharelado é outro nível |

O 208 foi o ajuste relevante: a categoria era de cursos técnicos, não de graduação.

## F. Mudanças na carteira

| Métrica | Fase 38 | Fase 39 |
|---|---|---|
| Cargos na matriz | 159 | **159** |
| Incompatíveis | 44 | **61** |
| Compatíveis (expresso/categoria) | 3 | **2** |
| Compatíveis por nível mínimo | — | **16** |
| Potenciais (interpretação) | 1 | **1** |
| Identidade pendente | 84 | **51** |
| Informação insuficiente | 28 | **28** |
| Destaques | 3 | **11 em 6 concursos** |

O aumento de destaques vem dos 16 cargos de **nível mínimo** — todos com motivo explícito
("escolaridade mínima publicada, sem curso específico exigido; nível medio"). Eles entram depois
dos compatíveis sustentados na ordenação. Nenhum incompatível entrou.

A queda de 84 para 51 em identidade pendente vem da junção por código (200–206, 400–406 etc.),
que deu leitura de formação a cargos antes sem ela.

## G. Reserva indígena

Mantido o escopo das fases anteriores: **1** cargo com vaga imediata (TJSC), **55** com reserva
sem imediata, **9** linhas de concurso com distribuição por cargo, **3** zero explícito,
**89** menções sem quantidade, **2** ausentes. Nenhuma quantidade do concurso foi distribuída
por cargo.

## H. Testes

- Inicial **1.702 OK** → final **1.748 OK** (skipped=1), +46 em
  `tests/test_eligibility_f39.py`.
- Contrato `GET /api/concursos` v1: inalterado.

## I. Revisão independente e defeitos corrigidos

1. **Crítico** — licenciatura ("Licenciatura Plena com habilitação para o magistério", "na área
   de atuação") era lida como nível mínimo. Corrigido: qualificadores de licenciatura são
   formação específica.
2. **Importante** — decisão humana `validado`/`corrigido` era sobrescrita pela releitura.
   Corrigido: decisão vigente prevalece.
3. **Importante** — aceitação explícita era rebaixada por um segundo candidato ambíguo.
   Corrigido: `explicito` é protegido como a incompatibilidade.
4. **Importante** — a educação exibida vinha da primeira evidência, não da que sustenta o
   estado. Corrigido: `_education_for`.
5. **Menor** — atribuição `codigo_do_cargo` sem leitura de SI; rótulos do cargo vazios; versão
   do contrato. Corrigidos.

## J. Mudanças do ciclo automático durante a fase

O ciclo agendado rodou às **20:19Z** (17:19 local), durante a fase, e estava **em andamento**
no momento do fechamento:

| Origem | Mudança |
|---|---|
| Fase 39 | +55 propostas `vaga_municipio` (reprocessamento idempotente de 6 editais) |
| Fase 39 | nenhuma revisão, valor vigente ou reconciliação |
| Ciclo | **+42 documentos** e **+17 versões** (concurso novo 05d9f661, Controladoria Geral do Município), **0 propostas** até o fechamento |

A matriz foi recalculada após o ciclo e não mudou (159 cargos, mesmos estados), porque os
documentos novos ainda não geraram propostas. Nenhuma alteração do ciclo foi atribuída à fase.

## K. Banco e API

| Item | Valor |
|---|---|
| Schema | v21 (sem migração) |
| Documentos / propostas | 1.232 (+42 do ciclo) / **7.648** (+55 `vaga_municipio`) |
| Revisões / valores / reconciliações | **0 / 0 / 0** |
| `integrity_check` | ok |
| `foreign_key_check` | vazia |

## L. Pendências para a fase seguinte

1. **89 rótulos aguardando decisão humana** — a sugestão existe; falta confirmar na mesa.
2. **36 duplicatas de identidade** — consolidar exige decisão (207/208/407 têm variantes de
   caixa).
3. **23 rótulos sem cargo canônico** — concursos sem identidade de cargo cadastrada.
4. **18 rótulos só-código** — sem nome; dependem de outra fonte do mesmo concurso.
5. **55 cargos com reserva indígena sem vaga imediata** e **89 menções sem quantidade** —
   investigar distribuição quando houver fonte.
6. **16 cargos de nível mínimo** — confirmar que não há exigência adicional no edital.

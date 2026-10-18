# Prova real — Fase 37: auditoria de prazos, contagens e ficha de decisão

Data: 2026-10-18. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` — **v21, sem migração**. Backup de início (API de backup):
`data/radar.sqlite3.bak-20261018-140658` (61.464 KB, `integrity ok`, v21).

## A. Estado inicial real

| Item | Valor |
|---|---|
| Diretório | `C:/Users/anton/OneDrive/Desktop/radar-de-concursos` |
| Branch / HEAD | `radar-configuracao` / `9252d94` |
| Git | limpo e sincronizado com `origin/radar-configuracao` |
| Suíte | **1.637 OK** (skipped=1) |
| Schema | v21, `integrity ok`, FK vazia |
| Documentos / versões / propostas | 1.190 / 1.055 / 7.585 |
| Revisões / valores vigentes / reconciliações | **0 / 0 / 0** |
| Revalidações | 10 |
| Prazos no calendário | 110 |
| Tarefa agendada | ciclo 6 h; última 11:19 local (14:19Z), próxima 17:19 local |
| Referência temporal | 2026-10-18T14:07-03:00 (`America/Recife`), 17:07Z |

A base **não mudou durante a fase**: o último ciclo foi às 14:19Z, antes do início; o
próximo (20:19Z) ocorre depois do encerramento. Nenhum documento, versão ou proposta foi
adicionado pela fase.

## B. Caso `4f495c42` (TJSC — Juiz Substituto)

Concurso `4f495c42-c489-41b3-985d-43cc2b129847` (`tjscjuiz26`), edital de abertura de
2026-10-13, versão `92b65e7a`, sha256 `85bd7cfe4818b4bf…`, 895.243 bytes.

Cinco propostas de `registration_end` e quatro de `registration_start`, todas do **mesmo
documento e da mesma versão**:

| Valor | Página | Evento do trecho | Extrator atual | Conclusão |
|---|---|---|---|---|
| 2026-11-26 | 7, 12, 14 | inscrição | reproduzido | fim de inscrições |
| 2026-10-21 | 17 | **isenção** | não reproduz | fim do pedido de isenção |
| 2027-04-18 | 33 | **prova** | não reproduz | data da prova discursiva |
| 2026-10-19 | 7, 12, 14 | inscrição | reproduzido | início de inscrições |
| 2027-04-18 | 33 | prova | não reproduz | data da prova |

Trechos:

- p7/p12/p14: `dia 19 de outubro de 2026 até às 16h do dia 26 de novembro de 2026`, precedido
  de "As inscrições para o Concurso Público estarão abertas no período das 16h do…".
- p17: `dia 19 de outubro de 2026 às 16h do dia 21 de outubro de 2026`, precedido de
  "10.2 A isenção mencionada no subitem 10.1 poderá ser solicitada no período das 16h do…".
- p33: `dia 18 de abril de 2027, no período da manhã, das 8h às 12h, prova discursiva…`,
  precedido de "As provas serão aplicadas nas datas prováveis de…".

**Causa**: `evento_diferente` + `extracao_obsoleta`. Os candidatos de 21/10 e 18/04/2027 são
extrações anteriores à regra de contexto (propostas criadas em 2026-10-16T20:14:26Z; a regra
entrou na Fase 33, commit `1679159`, em 2026-10-18).

**Verificação do documento**: `fonte_inalterada`, HTTP 200, sha256 observado idêntico ao
armazenado (`85bd7cfe…`), host `conhecimento.fgv.br` (política `persistencia_permitida`).
Isso confirma apenas que o arquivo não mudou; **não** valida a interpretação.

**Resposta à pergunta da missão**: a data de **19/10/2026 é sustentada como início de
inscrições** por texto literal explícito em três passagens do edital ("As inscrições …
estarão abertas no período de 19 de outubro de 2026 a 26 de novembro de 2026"), e o fim é
**26/11/2026**. Ela **não está confirmada** (nenhuma decisão humana) e **não prova inscrição
aberta**: em 18/10/2026 o período começa no dia seguinte. O `19/10` não vem da janela de
isenção (que coincide no início, mas termina em 21/10).

**Proposta de correção (não executada)**: rejeitar, por decisão humana, as propostas
`73cd3565…` (21/10) e `a6a1bf69…` (18/04/2027). Nada foi alterado.

## C. Demais conflitos de prazo

**15 conflitos** (9 expirados + 6 futuros), em 9 concursos. Causas: **10 `evento_diferente`**
e **5 `divergencia_real`**.

| Concurso | Grupo | Temporal | Valores | Sustentados | Causa |
|---|---|---|---|---|---|
| 4f495c42 | inscricao_fim | futuro | 21/10, 26/11, 18/04/27 | **26/11** | evento_diferente |
| 4f495c42 | inscricao_inicio | futuro | 19/10, 18/04/27 | **19/10** | evento_diferente |
| 4b5579c4 | inscricao_fim | futuro | 13/11, 15/10, 11/04/27 | **13/11** | evento_diferente |
| 4b5579c4 | inscricao_inicio | futuro | 13/10, 11/04/27 | **13/10** | evento_diferente |
| 637c7a90 | inscricao_fim | futuro | 28/09, 04/04/27, 21/02/27 | **28/09** | evento_diferente |
| 637c7a90 | inscricao_inicio | futuro | 28/08, 04/04/27, 21/02/27 | **28/08** | evento_diferente |
| 1e5cafb4 | inscricao_fim | expirado | 25/01/23, 19/01/23 | 25/01 e 19/01 | divergencia_real |
| 4a271ba4 | inscricao_fim | expirado | 30/10, 22/09 | **30/10** | evento_diferente |
| 784d730a | inscricao_fim | expirado | 10/03/23, 10/04/23 | 10/03 e 10/04 | divergencia_real |
| 7c54d7df | inscricao_fim | expirado | 14/10, 21/09, 14/03/27 | **14/10** | evento_diferente |
| 7c54d7df | inscricao_inicio | expirado | 15/09, 14/03/27 | **15/09** | evento_diferente |
| ddb0dac5 | inscricao_fim | expirado | 17/09, 10/09, 12/08, 14/08 | 17/09 e 10/09 | evento_diferente + divergencia_real |
| f4235e23 | inscricao_fim | expirado | 03/09, 01/10, 07/10 | 3 valores | divergencia_real |
| f4235e23 | recurso_isencao | expirado | 18/09, 21/09 | 2 valores | divergencia_real |
| f4235e23 | resultado_isencao_preliminar | expirado | 17/09, 18/09 | 2 valores | divergencia_real |

**Sobre os "sete identificadores"**: a Fase 36 disse "seis permaneceram em conflito" referindo-se
aos **6 itens futuros** (3 concursos × início/fim). A lista de sete identificadores incluía
`7c54d7df`, `ddb0dac5`, `f4235e23` e `4a271ba4`, que estão em conflito **expirado** — não no
recorte futuro. Não há inconsistência no banco: há 15 itens em conflito, 6 futuros e 9
passados, distribuídos em 9 concursos.

**Conflitos que exigem decisão humana (divergência real, não erro de extração)**:
`1e5cafb4` (duas retificações com fins diferentes), `784d730a` (duas versões),
`f4235e23` (três valores em documentos distintos) e `ddb0dac5` (4ª retificação 10/09 vs
cronograma 17/09). Nenhum foi resolvido por recência.

## D. Reconciliação das contagens

O relatório da Fase 36 somou 10 + 6 + 71 + 14 = 101 e não fechava com 110. A investigação:

- `por_estado` do código **somava 110** (10 revalidados + 15 conflitos + 71 passados + 14 sem
  data).
- O "6" era o recorte de conflitos **futuros**; o total de conflitos é **15**.
- O erro era de **relatório**, não de dados: misturou um recorte com o universo.

A fase separou as dimensões. Estado atual:

| Dimensão | Contagem | Soma |
|---|---|---|
| temporal | futuro 16 · expirado 80 · sem_data 14 | **110** |
| revalidação | fonte_inalterada 11 · sem_verificacao 99 | **110** |
| conflito | conflito 15 · sem_conflito 95 | **110** |
| revisão humana | sem_decisao 110 | **110** |
| situação (derivada) | revalidado 10 · conflito 15 · passado 71 · sem data 14 | **110** |
| urgência | até 7 dias 4 · até 30 dias 6 · vencido 71 · sem data 29 | **110** |
| grupo | inscrição fim 24 · início 24 · recurso 16 · resultado preliminar 14 · final 13 · isenção início 12 · isenção fim 7 | **110** |

Unidade: **prazo** (concurso × grupo × escopo de cargo); universo: todo grupo com ao menos uma
proposta, incluindo passados e sem data; propostas rejeitadas não sustentam valor, mas o grupo
continua contado.

## E. Os 11 registros `fonte_inalterada`

| Item | Valor |
|---|---|
| Total | **11** (10 da Fase 36 + 1 da Fase 37) |
| Resultado | 11 × `fonte_inalterada` |
| HTTP | 11 × 200 |
| sha armazenado = observado | 11 × sim |
| Hosts | `anexos-r2.selecao.net.br` (10, Quadrix) e `conhecimento.fgv.br` (1, FGV) |
| Política | `persistencia_permitida` para documento nos dois |
| Redirecionamento recusado | nenhum caso |
| Decisão humana posterior | **0** |
| Conflito interpretativo | 1 (o de `4f495c42`, verificado na Fase 37) |

Nenhum foi convertido em "campo confirmado".

## F. Destaques da carteira

**12 destaques em 8 concursos** (106 candidatos). Amostra com os campos exigidos:

| Concurso | Cargo | Prontidão | SI | Indígena | Prova |
|---|---|---|---|---|---|
| quadrix-3053 | concurso | campos ausentes | correlata | apenas reserva | Palmas/TO |
| quadrix-3053 | 200 Assistente Administrativo | identidade pendente | correlata | apenas reserva | Palmas/TO |
| quadrix-3072 | concurso | campos ausentes | não encontrado | apenas reserva | Macapá/AP |
| quadrix-3049 | 208 PST Assistente de T.I. | identidade pendente | categoria inclui | apenas reserva | Colatina, Guarapari, Vitória/ES |
| Prefeitura de Salvador | concurso | conflito | não encontrado | não mencionado | Salvador/BA |
| TJ AP | concurso | conflito | outras formações | menção sem quantidade | Macapá/AP |
| TJ SC | concurso | conflito | outras formações | menção sem quantidade | Florianópolis/SC |
| XVI Concurso | concurso | conflito | não encontrado | menção sem quantidade | a divulgar |
| quadrix-3052 | 404 Analista de Informática | histórica | **expresso** | apenas reserva | Curitiba, Maringá/PR |

Motivo de inclusão legível em cada item; três deles entram por **prazo em conflito** (texto
corrigido nesta fase: "fim das inscrições em conflito documental (sem valor único)").

## G. SI e reserva indígena por escopo

**Sistemas de Informação** (285 oportunidades):

| Escopo | explicito | categoria | correlata | outras | não encontrado |
|---|---|---|---|---|---|
| cargo | 2 | 4 | 41 | 78 | 131 |
| concurso | 1 | 1 | 12 | 2 | 13 |
| **total** | **3** | **5** | **53** | **80** | **144** |

Os números da Fase 36 (3/5/53/80/144) estão confirmados; agora separados por escopo. Aceitação
expressa: **404 Analista de Informática** (Quadrix 3052) e o agregado do concurso. Nenhum
cargo herda o estado de outro.

**Reserva indígena** (todas as 285 têm `ambito: "concurso"`):

| Estado | Cargo | Concurso | Total |
|---|---|---|---|
| apenas_reserva | 97 | 6 | **103** |
| mencao_sem_quantidade | 147 | 21 | **168** |
| nao_mencionado | 12 | 2 | **14** |
| explicito_imediato | 0 | 0 | **0** |

Nenhuma vaga imediata indígena comprovada; nenhum total agregado convertido.

## H. Documentos nominais

**287** pendências (131 manter metadados, 156 retirar da fila), modo **simulação**.

A diferença em relação aos 191 da Fase 35 (+96) vem dos documentos descobertos pelo ciclo
depois daquela fase: 636 documentos em 2026-10-16, 153 em 2026-10-17 e 401 em 2026-10-18.
Nada foi arquivado, apagado ou movido; nenhum conteúdo foi baixado para a interface.

## I. Mudanças atribuíveis à fase e ao ciclo

| Origem | Mudança |
|---|---|
| Fase 37 | 1 registro em `revalidacoes_prazo` (verificação do edital TJSC) |
| Fase 37 | nenhuma proposta, revisão, valor vigente ou reconciliação |
| Ciclo automático | nenhuma durante a fase (último às 14:19Z, antes do início; próximo às 20:19Z) |
| Código | `document_fields` (contexto de evento), `deadline_calendar` (dimensões), `deadline_audit`, `deadline_revalidation.verify_version`, rotas, CLI, UI |

## J. Testes

- Inicial: **1.637 OK** (skipped=1).
- Final: **1.668 OK** (skipped=1) — +31 em `tests/test_deadline_audit_f37.py`.
- Contrato `GET /api/concursos` v1 (18 campos): inalterado.

## K. Integridade final

| Item | Valor |
|---|---|
| Schema | v21 (sem migração) |
| Documentos / versões / propostas | 1.190 / 1.055 / 7.585 |
| Revisões / valores / reconciliações | **0 / 0 / 0** |
| Revalidações | **11** |
| `integrity_check` | ok |
| `foreign_key_check` | vazia |

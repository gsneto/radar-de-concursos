# Prova real — Fase 38: matriz de elegibilidade por cargo e escopo indígena

Data: 2026-10-18. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` — **v21, sem migração**. Backup de início (API de backup):
`data/radar.sqlite3.bak-20261018-152203` (61.464 KB, `integrity ok`, v21).

## A. Estado inicial real

| Item | Valor |
|---|---|
| Diretório | `C:/Users/anton/OneDrive/Desktop/radar-de-concursos` |
| Branch / HEAD | `radar-configuracao` / `36db3fd` |
| Git | limpo e sincronizado |
| Suíte | **1.668 OK** (skipped=1) |
| Schema | v21, `integrity ok`, FK vazia |
| Documentos / versões / propostas | 1.190 / 1.055 / 7.585 |
| Revisões / valores / reconciliações | **0 / 0 / 0** |
| Revalidações | 11 |
| Ciclo | última 11:19 local; próxima 17:19 local |
| Referência | 2026-10-18T15:22-03:00 (`America/Recife`) |

## B. Caso TJSC Juiz Substituto 2026

Concurso `4f495c42-c489-41b3-985d-43cc2b129847` (`tjscjuiz26`), edital de 13/10/2026, versão
`92b65e7a`, sha256 `85bd7cfe…`.

**O que a base tinha antes**: nenhuma proposta de vaga (nem imediata, nem indígena), apenas o
requisito "Nível Superior - Direito" e os prazos. O quadro de vagas do edital é **texto
corrido** e o extrator antigo não o lia.

**Depois do parser novo** (página 4, trecho literal):

```
QUADRO DE VAGAS
Cargo | Ampla Concorrência | Pessoa com Deficiência | Negros | Indígenas | Quilombolas | Total de vagas
Juiz Substituto 9 1 4 1 CR 15+ CR
```

| Fato | Valor | Escopo |
|---|---|---|
| Vagas imediatas | **15** | cargo "Juiz Substituto" |
| Vaga indígena imediata | **1** | cargo "Juiz Substituto" |
| Cadastro de reserva | "CR" (sem número) | não vira quantidade |
| Requisito | bacharelado em Direito + 3 anos de atividade jurídica | cargo (cargo único) |
| Inscrições | 19/10/2026 a 26/11/2026 | concurso |

Resultado da matriz:

```
Juiz Substituto | incompativel_por_requisito | indigenous=cargo_imediata | identity=pendente
                | si=outras_formacoes (atribuicao=unico_cargo_do_concurso)
```

Os cinco requisitos da missão:

1. **Vaga indígena imediata do cargo reconhecida** — `cargo_imediata`, evidência
   "Juiz Substituto 9 1 4 1 CR 15+ CR", página 4. ✔
2. **A reserva não torna o cargo compatível** — `incompativel_por_requisito`; o cargo **não**
   aparece nos destaques. ✔
3. **Requisito de Direito representado** — `si=outras_formacoes`, trecho "ter concluído o
   curso de bacharelado em Direito". ✔
4. **Início de inscrição no evento correto** — `inscricao_inicio=2026-10-19`,
   `inscricao_fim=2026-11-26`; a janela de isenção (19–21/10) não vira inscrição. ✔
5. **A evidência não cria decisão** — 0 revisões, 0 valores, 0 reconciliações após rodar a
   matriz e os destaques. ✔

Filtro da UI "Indígena = vaga imediata do cargo" retorna **1 cargo** (TJSC) exibido como
**Incompatível por requisito explícito** — exatamente o comportamento exigido.

## C. Modelo de elegibilidade implementado

`radar/eligibility.py` — seis estados exclusivos, com precedência:

1. `incompativel_por_requisito`
2. `compativel_com_vaga_indigena_cargo`
3. `compativel_sem_vaga_indigena`
4. `compativel_por_interpretacao`
5. `identidade_pendente`
6. `informacao_insuficiente`

Guardas de texto: o trecho precisa ser de formação e, para "potencial", citar área de
computação/TI. "Conhecimentos básicos em informática" não conta.

## D. Âmbito concurso × cargo

Nove estados de escopo indígena, com `ambito` explícito. A linha do concurso **não** distribui
quantidade: quando a informação está por cargo, ela declara `distribuido_por_cargo`.

## E. Carteira antes e depois

| Métrica | Fase 37 | Fase 38 |
|---|---|---|
| Destaques | **12 em 8 concursos** | **3 em 2 concursos** |
| Critério | edital + prazo/SI/reserva | requisito **sustentado** (expresso, categoria ou correlato) |
| Cargo incompatível nos destaques | 1 (Direito, por reserva) | **0** |
| Cargos sem requisito nos destaques | vários | **0** |

Os 3 destaques: 208 e 407 (Quadrix 3049, "categoria inclui curso") e 404 Analista de
Informática (Quadrix 3052, aceitação expressa de Sistemas de Informação).

## F. Candidatos de elegibilidade por estado

**159 cargos** na matriz:

| Estado | Cargos |
|---|---|
| `incompativel_por_requisito` | **44** |
| `compativel_sem_vaga_indigena` | **3** |
| `compativel_com_vaga_indigena_cargo` | 0 |
| `compativel_por_interpretacao` | 0 |
| `identidade_pendente` | **84** |
| `informacao_insuficiente` | **28** |

Escopo indígena:

| Estado | Cargos |
|---|---|
| `cargo_sem_imediata_com_reserva` | 55 |
| `mencao_sem_quantidade` | 89 |
| `distribuido_por_cargo` | 9 |
| `cargo_explicito_zero` | 3 |
| `cargo_imediata` | **1** |
| `ausente_no_documento` | 2 |

Situação temporal (dimensão separada): 33 revalidado na fonte, 118 expirado, 5 em conflito,
2 sem candidatura. Identidade: 129 pendentes, 29 reconciliadas.

## G. Rótulos reconciliados

- **Decisão humana**: 0 (a fase não fabricou nenhuma).
- **Sugestões/pendências**: 84 cargos com identidade pendente; a matriz mostra os rótulos
  originais (`rotulos`) e não funde cargos por similaridade.

## H. Efeito sobre os destaques e falsos positivos evitados

1. **TJSC** — tinha vaga indígena e prazo futuro; entraria nos destaques antigos. Agora fica
   fora por requisito de Direito.
2. **"Concurso Público para a Receita Federal"** — entrada por menção genérica; agora
   `informacao_insuficiente`.
3. **"FORMAÇÃO QUÍMICA LICENCIATURA"** — trecho de currículo classificado como "ambíguo";
   agora `informacao_insuficiente` pela guarda de requisito.
4. **"ASSISTENTE DE EDUCAÇÃO"** — "conhecimentos básicos em informática" virava "potencial";
   agora não conta como formação.
5. **Assembleia Legislativa** — linha do concurso agregava 6 cargos; não é cargo e não entra.

## I. Quadro de vagas: documentos afetados

| Concurso | Documento | Vagas imediatas | Indígenas |
|---|---|---|---|
| 4f495c42 (TJSC) | Edital | 15 | **1** |
| 637c7a90 (TRF5) | Edital retificado 17/09 | 11 | 0 (explícito) |
| ddb0dac5 | 3ª Retificação | 1 e 5 | 0 e 0 |

+8 propostas candidatas (6 na primeira aplicação, 2 na segunda linha do quadro), 0 decisões,
0 exclusões. Nenhuma proposta existente foi reescrita.

## J. Testes e revisão independente

- Inicial **1.668 OK** → final **1.702 OK** (skipped=1), +34 em
  `tests/test_eligibility_f38.py`.
- Contrato `GET /api/concursos` v1: inalterado.

Revisão independente apontou dois críticos, corrigidos:

1. **Leitura ambígua apagava incompatibilidade explícita** — um cargo com "Direito"
   (incompatível) + "área de computação" (ambíguo) virava "potencial" e entrava nos destaques.
   Agora `outras_formacoes` vence qualquer leitura concorrente.
2. **Atribuição de cargo único disparava em concurso multi-cargo** quando só um cargo tinha
   propostas. Agora exige **um único cargo no quadro de vagas** além do rótulo único.

Também corrigidos: coluna extra no quadro (rejeita em vez de mapear errado), múltiplas linhas
do quadro (lia só a primeira), `conflito` fora do allowlist da API, `si`/`identity` sem
validação, e reprocessamento emitindo quadro de concurso para documento restrito a cargo.

## K. Banco e API

| Item | Valor |
|---|---|
| Schema | v21 (sem migração) |
| Documentos / versões / propostas | 1.190 / 1.055 / **7.593** |
| Revisões / valores / reconciliações | **0 / 0 / 0** |
| Revalidações | 11 |
| `integrity_check` | ok |
| `foreign_key_check` | vazia |

## L. Commit, branch e sincronização

Pendente de execução ao final da fase.

## M. Pendências restantes

1. **84 cargos com identidade pendente** — reconciliar os que interessam ao perfil (ex.: os
   códigos "200–206" do Quadrix 3049, cujo requisito está no rótulo do código).
2. **Categoria vs correlato** — revisar os 3 compatíveis para confirmar a leitura da categoria.
3. **Vagas indígenas por cargo** — 55 cargos têm apenas reserva; conferir se há distribuição
   de vaga imediata em retificação.
4. **89 menções sem quantidade** — buscar o quadro completo nos editais.
5. **Decisões humanas** — nenhuma foi criada; a mesa de revisão continua sendo o caminho.

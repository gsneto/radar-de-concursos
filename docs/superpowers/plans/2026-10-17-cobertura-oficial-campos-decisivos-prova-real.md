# Prova real — Fase 33: cobertura oficial, aquisição e campos decisivos

Data: 2026-10-17/18. Cobertura lida em **2026-10-18T08:49Z**. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` (schema v18, **sem migração**). Backup de início:
`data/radar.sqlite3.bak-20261017-225612` (`integrity ok`, FK vazia, v18).

## Suíte de testes

- Baseline: **1.434 testes, OK** (skipped=1).
- Final: **1.481 testes, OK** (+47; 1 pulado quando há motor de OCR).
- Contrato `GET /api/concursos` v1 (18 campos): inalterado (testes de contrato verdes).

## Cobertura documental: antes e depois

Universo: **634 certames** (o container de fonte não entra no denominador).

| Métrica | Início (backup) | Fim |
|---|---|---|
| Documentos | 789 | **950** (911 com versão; 39 só metadado) |
| Concursos com documento qualquer | 540 (85,2%) | **548 (86,4%)** |
| Concursos com documento oficial | **36 (5,7%)** | **44 (6,9%)** |
| Concursos com edital oficial | **21 (3,3%)** | **28 (4,4%)** |
| Concursos com edital extraído | 21 (3,3%) | **28 (4,4%)** |
| Concursos com campos candidatos | 20 (3,2%) | **27 (4,3%)** |
| Concursos com campos confirmados | 0 | **0** |

Estados (exclusivos):

| Estado | Início | Fim |
|---|---|---|
| `campos_confirmados` | 0 | 0 |
| `conflito` | 1 | 1 |
| `campos_candidatos` | 20 | **25** |
| `edital_extraido` | 0 | 0 |
| `oficial_sem_extracao` | 0 | 0 |
| `oficial_sem_edital` | 15 | 15 |
| `identidade_pendente` | 0 | 0 |
| `obtencao_nao_autorizada` | 0 | 0 |
| `oficial_nao_importado` | **94** | **89** |
| `apenas_agregador` | 504 | 504 |
| `sem_documento` | 0 | 0 |

Leitura honesta: **504 certames (79,5%) só têm página de agregador**; 15 têm documento oficial
que não é edital; 89 continuam com fonte oficial conhecida e sem documento. O número de 85%
"com documento" nunca foi cobertura oficial — era notícia de agregador.

## Origem do avanço (+5 certames com edital)

O avanço **não veio todo do piloto**. A tarefa agendada do Windows
`Radar de Concursos - Ciclo` (`ops-ciclo`, a cada 6 h) rodou às 23:19 local (02:19 UTC) durante a
fase e importou **97 documentos em 3 certames** (TJMS juiz 51, PCPR 23, PMS 23). O piloto desta
fase importou **4 documentos em 2 certames**. Total: +101 documentos, +5 certames com edital.

Isso está registrado porque o relatório de cobertura não pode atribuir ao trabalho manual o que
veio do ciclo automático.

## Piloto de aquisição controlada (FGV)

Fonte: `fgv-conhecimento` (habilitada, persistência de documento autorizada, custo zero).
Política: `robots.txt` de `conhecimento.fgv.br` consultado — `/concursos/` e
`/sites/default/files/concursos/` permitidos.

| Certame | Documentos | Tamanho | Blocos | Propostas |
|---|---|---|---|---|
| MP-RJ — XXXIX Concurso (Promotor) `14c68b75` | edital de abertura + 1 retificação | 543 KB + 1,8 MB | 153 | 18 |
| Prefeitura de São José dos Campos `044cc967` | edital retificado + 1ª retificação | 477 KB + 149 KB | 36 | 325 |

- Registrados: **4**; baixados: **4**; versões analisadas: **4**; falhas: **0**.
- Consumo: 5 chamadas, 6 itens, **R$ 0,00**, execução `concluida`.
- Checkpoint: `data/acquisition-f33.json` (`next_index=2`).
- Segunda execução: **0** documentos novos (idempotente).

Propostas úteis do piloto (São José dos Campos): `registration_start=2026-01-05`,
`registration_end=2026-02-03`, `exam_location="São José dos Campos/SP"`,
`exam_municipio="São José dos Campos"`, `exam_uf="SP"`, 3 `education`, 3 `si_compatibility`
(ambíguos). MP-RJ: inscrição `2026-03-18` a `2026-04-16` e conteúdo programático.

### Incidente: lista nominal rotulada de "Retificação"

A página da FGV listou **"Retificação - Relação de inscritos provisórios"** como retificação. O
documento é uma **lista de 106 páginas com nome e número de inscrição de candidatos**. O piloto
o registrou, baixou e extraiu antes da guarda existir. Providências:

1. `document_types.is_nominal_title` + guarda em `acquisition` e em `monitoring`: metadados
   ficam, **corpo não é baixado nem extraído** em execuções futuras.
2. `documentos-nominais` lista os **206** documentos de lista nominal da base para decisão
   humana. Nada foi apagado (política do projeto).
3. O documento não gerou proposta de campo (é lista, não regra) e não conta como edital.

## Conflitos entre versões

`conflitos-versao` na base: **18** itens.

| Tipo | Quantidade | Leitura |
|---|---|---|
| `divergencia_mesmo_documento` | 11 | o documento mais recente traz mais de um valor (ex.: prazo de inscrição × isenção no mesmo edital); exige revisão |
| `escopo_diferente` | 5 | `a_divulgar` × local concreto; não é divergência de valor |
| `retificacao_posterior` | 2 | retificação alterou prazo de isenção (recurso/resultado preliminar) |
| `divergencia_sem_ordem` | 0 | — |

Nenhum valor foi sobrescrito; o anterior fica registrado como substituído.

## Quatro campos decisivos (fim)

| Grupo | Estados |
|---|---|
| Vagas indígenas | `apenas_reserva` 6 · `mencao_sem_quantidade` 18 · `nao_mencionado` 2 · `nao_pesquisado` 608 |
| Sistemas de Informação | `explicito` 1 · `categoria_inclui_curso` 1 · `area_correlata_interpretacao` 9 · `outras_formacoes` 2 · `nao_encontrado` 13 · `extracao_incompleta` 608 |
| Prazos (fim da inscrição) | `candidato` 6 · `ambiguo` 7 · `nao_localizado` 13 · `nao_pesquisado` 608 |
| Local de prova | `extraido_nao_revisado` 14 · `ambiguo` 8 · `nao_informado` 4 · `nao_extraido` 608 |

- **Nenhuma vaga indígena imediata** foi declarada na base; há 6 certames com reserva indígena
  explícita (Quadrix, coluna PI) e 18 com menção sem quantidade extraída. Nenhum total agregado
  virou vaga indígena.
- SI por cargo: 1 explícito, 2 por categoria, 32 correlatos, 55 outras formações. O caso
  explícito é o cargo 404 de um edital Quadrix ("... Sistemas de Informação ...").
- Prazos: 6 candidatos com valor vigente; 7 ambíguos (o documento mais recente tem mais de um
  valor) — 4 deles com `candidato_majoritario`.
- Local: 14 extraídos; 8 ambíguos (a_divulgar + local concreto); 4 não informados.

## Correções reais de extração

| Correção | Efeito |
|---|---|
| Travessão em "cidade de Porto Alegre – RS" | `exam_municipio=Porto Alegre`, `exam_uf=RS` (antes: valor truncado sem UF) |
| "Rio de Janeiro/RJ" e "São Paulo/SP" | passam a ser município (antes: recusados por coincidir com o nome do estado); sem UF continuam estado |
| Período de isenção como inscrição | `_TEXT_PERIOD` exige contexto de inscrição e rejeita isenção próxima |

## Revisão humana

- Revisões humanas reais: **0** (nenhuma decisão fictícia criada).
- Valores vigentes: **0**.
- Candidatos disponíveis para revisão: **6.199 propostas** (todas candidatas).
- O fluxo oficial continua sendo `revisao-fila` / `revisao-decidir`; esta fase **não** aprova
  nada automaticamente.

## Banco e contrato

- `PRAGMA integrity_check`: **ok**; `foreign_key_check`: **vazia**; schema **v18**.
- Contagens: 635 identidades (634 certames + 1 container), **950 documentos** (911 versões;
  39 sem byte por serem listas nominais), **14.823 blocos**, **6.199 propostas/evidências**,
  0 revisões, 0 valores vigentes.
- `GET /api/concursos` v1: 18 campos preservados.

## Limitações

1. **`historico` não é atribuído**: não há prova de encerramento no modelo; um certame com
   inscrições passadas continua `campos_candidatos`.
2. **Camada municipal da Fase 32 segue diagnóstica**: não vira local de prova.
3. **Documentos nominais já persistidos** (191) não são apagados; ficam listados para decisão.
4. **Ciclo agendado** continua ativo (6 h) e pode alterar a base entre execuções; a cobertura
   deve ser lida com data/hora.
5. **Prioridade de aquisição sem documento** é conservadora: sem edital não há evidência
   temática, então não se presume relevância.

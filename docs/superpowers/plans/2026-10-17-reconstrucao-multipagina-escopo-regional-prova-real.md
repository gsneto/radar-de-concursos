# Prova real — Fase 32: reconstrução multipágina e escopo regional

Data: 2026-10-17. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` (schema v18, **sem migração**). Backup de início: `-213823`.

## Suíte de testes

- Baseline: **1404 testes, OK** (skipped=1).
- Final: **1434 testes, OK** (+30): `tests/test_multipage.py`.
- Nenhuma regressão em 789 documentos / 11.552 blocos.

## Quadro de vagas do IBFC 004/2026

Versão `b86226e9-eebd-4398-8e3b-77c150ed80b3` (documento `c59c2747…`, 611.399 B).

| Métrica | Antes (F31) | Agora |
|---|---|---|
| Cabeçalho | não localizado | **p21** |
| Páginas de linha | tratadas isoladas | **p21–p29** (9 páginas) |
| `TOTAL` | não associado | **p29**, 2.500 |
| NTEs | 26 (NTE 06 ausente) | **27 (01–27)** |
| Soma dos NTEs | **2.466** | **2.500** |
| Certeza da continuidade | `provavel` | **`forte`** |
| Ambiguidades | NTE 06 ausente; soma ≠ total | **nenhuma** |

A diferença de **34** era o **NÚCLEO 06 - VALENÇA 34**: o documento rotula esse núcleo como
`NÚCLEO`, não `NTE`, e sem `SEDE:`. O reconhecimento do rótulo alternativo fechou a conta
(2.466 + 34 = 2.500) sem qualquer ajuste manual.

Transições (todas as 8): 21→22 … 27→28 com score 5 (`ntes_continuam`,
`inicia_no_meio_da_lista`, `pagina_adjacente`); 28→29 com score 7 (`ntes_continuam`,
`fecha_com_total`, `total_encerra`, `nota_de_rodape`, `pagina_adjacente`).

### Cargo do escopo

| Item | Valor |
|---|---|
| Cargo | **Técnico de Nível Médio** |
| Página | 1 |
| Trecho | "Função temporária de Técnico de Nível Médio" |
| Certeza do escopo | `escopo_edital_unico` |
| Candidatos | 1 |

O padrão fraco "função de X" não disputa com o forte: sem essa precedência, "função de jurado"
(critério de pontuação) seria lido como cargo.

### Camada de município

| Métrica | Valor |
|---|---|
| Municípios lidos | **417** |
| NTEs cuja soma de municípios fecha | **27 de 27** |
| `soma_municipios_confere` | **true** |
| Trecho por linha | sim (`quote` + offsets absolutos) |

Depois de remover o sub-cabeçalho repetido pelo **prefixo de palavra da sede** (aceitando
`F. DE SANTANA` × `FEIRA DE SANTANA`), a leitura passou a fechar em todos os NTEs: NTE 01, por
exemplo, tem 20 municípios somando exatamente 84 (AMERICA DOURADA 3, BARRA DO MENDES 4, …,
IRECÊ 30, …, XIQUE-XIQUE 8). Cada linha carrega o trecho literal e a página.

A camada continua **diagnóstica**: nenhuma proposta de município é emitida e o nome do
indicador é estreito — `soma_municipios_confere` confere a soma, não cada linha.

### Propostas que seriam geradas

Por padrão, **1 proposta**: o `TOTAL` do quadro (2.500), com `role_id` nulo, motivo "total
agregado publicado (ampla + negros + pcd); não distribuir por modalidade; quadro p21–p29
(forte)". Com `include_ntes=True`, os 27 totais de NTE também são emitidos, cada um marcado
como **recorte do NTE — não é o total do concurso**. Toda evidência aponta para o bloco real e
o offset do trecho (verificado por teste); quadro com certeza inferior a `provavel` não gera
proposta.

**Nenhuma foi gravada na base real**: não existe caminho de escrita de proposta isolada
testado, e o projeto não confirma campo automaticamente. O relatório é o entregável; a
gravação continua dependendo de revisão.

## PDFs longos: 13 parciais justificados

| Classificação | Documentos |
|---|---|
| `dados_pessoais_lista_resultado` | **13** |
| `conteudo_util` | 0 |
| `sem_conteudo_util` | 0 |

Todos os 13 são atos de resultado/homologação/isenção (309 a 3.094 páginas, prefixo de 40 já
lido). A justificativa registrada cita o ato e o marcador nominal observado (nome do candidato,
data de nascimento, CPF, nota, classificação). Nenhum é processado adiante.

Quadros multipágina na base: **14** (1 reconstruído com NTE + 13 falsos positivos de lista de
resultado, marcados `irreconstruivel` e sem total).

## Superfície nova

CLI:

- `pipeline-continuidade --db` — quadros que atravessam páginas.
- `pipeline-regional --db --version-id [--propostas]` — escopo, NTEs e propostas.
- `documentos-parciais --db` — parciais com decisão justificada.
- `documentos-paginas --db --version-id [--pages 1-10,25]` — índice por página.
- `documentos-lote --db --version-id [--start-page --max-pages --checkpoint --apply]` — lote
  idempotente, `dry_run` por padrão.

API: `/api/pipeline/continuidade`, `/api/pipeline/parciais`,
`/api/pipeline/escopo-regional?version_id=…` (400 sem versão).

## Verificação

- `append_page_analysis` idempotente por página: segunda aplicação grava 0 blocos; propostas
  de páginas já gravadas são contadas em `dropped_proposals`, e índice malformado é erro (não
  descarte silencioso).
- Evidência de proposta em lote aponta para a **página nova** após o remapeamento (teste
  dedicado), e citação inválida continua rejeitando a gravação inteira.
- PDF criptografado falha com código (`pdf_criptografado`), sem exceção crua da biblioteca.
- Checkpoint grava `next_page` e permite retomada.
- `page_index` amostra só páginas não lidas (60 por padrão), sem ler 3.000 páginas.
- Backup `-213823` com `integrity ok`, FK vazia, schema v18 inalterado.

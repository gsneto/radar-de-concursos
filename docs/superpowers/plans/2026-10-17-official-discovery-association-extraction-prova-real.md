# Prova real — Fase 26: descoberta oficial, associação e extração

Data: 2026-10-17. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.

## Suíte de testes

- Baseline observada (antes de implementar): **1062 testes, OK**.
- Final: **1120 testes, OK** (58 novos): `test_exam_location.py` (22),
  `test_association.py` (13), `test_reprocess.py` (11), `test_program_content.py` (+8),
  `test_enrichment.py` (+4).

## Diagnóstico comprovado (não presumido)

| Sintoma reportado | Causa comprovada | Evidência |
|---|---|---|
| `conteudo_programatico` 0% | `document_extract` faz `" ".join(...split())` e apaga `\n`; o parser percorria `text.split("\n")` | 74 páginas do TJ-AP = 74 blocos = **74 linhas**; `is_content_heading` falso em todas |
| `local_prova` 0% | **não existia extrator**; `location.py` só interpreta propostas | `exam_location` só aparecia em leitura |
| 9 atos do DOU em 1 concurso, 0 propostas | `DOU_COMPETITION_ID = "DOU-S3"` (seção) usado como identidade de certame | concurso `54568dbc`: obs `DOU-S3`, 10 docs, 9 "editais" de órgãos diferentes |

## Antes e depois (banco real, `data/radar.sqlite3`)

| Métrica | Antes | Depois | Denominador |
|---|---|---|---|
| Propostas de campo | 751 | **1887** | — |
| Evidências | 751 | **1887** | — |
| `local_prova` com algum dado | **0,0%** | **87,5%** | 16 concursos com edital |
| `conteudo_programatico` com algum dado | **0,0%** | **31,2%** | 16 concursos com edital |
| `cargos` com algum dado | 81,2% | **93,8%** | 16 |
| Documentos com `tipo_documental` nulo | **487** | **0** | 636 documentos |
| Associações suspeitas | não medido | **3** (1 concurso) | 593 concursos |
| Campos confirmados por humano | 0 | **0** | — (inalterado, por desenho) |

Blocos (`6617`), documentos (`636`), versões (`636`) e identidades de cargo (`125`)
permaneceram **exatamente iguais**. `revisoes_campo` e `valores_atuais` continuam **0**: nada foi
confirmado automaticamente.

Distribuição da classificação nova (487 documentos antes sem tipo): 477 `pagina_agregador`,
7 `edital_abertura`, 1 `pagina_orgao`, 1 `convocacao`, 1 `comunicado`. `kind` alterado: **0**.

## Locais extraídos (amostra verificada)

| Concurso | Valor extraído | Trecho de origem |
|---|---|---|
| TJ-AP | `Macapá/AP` + `a_divulgar` | "2.1 As provas serão realizadas preferencialmente na cidade de Macapá… (AP)" |
| PMS Guarda | `Salvador` + `a_divulgar` | "9.1 A Prova Objetiva … será realizada na cidade do Salvador, Bahia" |
| CRQ-9 | `Curitiba/PR; Maringá/PR` | "1.4 … serão realizadas nas cidades de Curitiba/PR e Maringá/PR" |
| Município ES | `Colatina/ES; Guarapari/ES; Vitória/ES` | lista de unidades de aplicação |
| MS/MT/SP | `Campo Grande/MS; Cuiabá/MT; São Paulo/SP` | lista de cidades |

Casos rejeitados corretamente: "procedimentos presenciais … na cidade de Macapá"
(heteroidentificação), "horário oficial da cidade de Brasília" (fuso), "lotação … na cidade de X"
(local de exercício), "locais foram divulgados" (passado).

## Conteúdo programático extraído

5 dos 16 concursos passaram a ter itens: 21 seções, 33 disciplinas, 1031 tópicos (1.085
propostas). Os 11 restantes **não têm seção de conteúdo programático no edital** — os anexos são
cronograma, atribuições e requisitos. Verificado por busca textual: `conteúdo programático`
ausente em 11 documentos. Zero não é falha do parser nesses casos.

## Segurança e integridade

```
backup: radar.sqlite3.bak-20261017-130146 | integrity: ok
backup: radar.sqlite3.bak-20261017-131921 | integrity: ok
dry-run: 19 propostas, contagens inalteradas
apply: +19 propostas, +19 evidências, blocos intactos
2ª execução: 0 (idempotente)
citações inválidas: 0
propostas sem ambiguity_reason: 0
foreign_key_check: []
revisoes_campo / valores_atuais: 0 / 0
```

Protocolo seguido: configuração explícita (`--config` real, sem arquivo temporário presumido),
`dry_run` primeiro, cópia isolada antes da base real, backup consistente com `integrity_check`,
comparação de contagens antes/depois e preservação dos backups.

## Revisão independente

**3 críticos, 9 importantes, 6 menores.** Todos os críticos e importantes corrigidos:

1. **Crítico** — clamp de offset corrompia a citação quando o título era longo; `record_analysis`
   recusaria o documento inteiro. Corrigido (`line_start = remainder_start`) + teste de regressão.
2. **Crítico** — `exam_location` **não estava ligado** em `extract_field_proposals` (a edição
   anterior não aplicou). Corrigido e verificado por `git diff`.
3. **Crítico** — local de prova era inferido de **lotação** ("A lotação … Macapá e as provas …
   Belém/PA" → Macapá). Corrigido com ancoragem na cláusula da prova + guarda de lotação.
4. UF perdida em `cidade de X/UF` (6 valores reais) — corrigido.
5. UF falsa (`em`, `as`, `de`) aceita como unidade — corrigido com whitelist das 27 UFs.
6. Lista "Macapá e Santana" virava um município só — corrigido.
7. `_PENDING` não reconhecia "serão" (classe sem `ã`) e aceitava passado — corrigido.
8. `BLOCO I` com prosa/fórmula virava disciplina — corrigido.
9. Seleção de versão pegava a mais antiga e não determinística — corrigido (`fetched_at DESC`,
   desempate por id) e páginas de agregador/banca excluídas.
10. Idempotência só era verificada fora da transação — revalidada dentro de `BEGIN IMMEDIATE`.
11. `ambiguity_reason` não era exigido no limite de escrita — agora é.
12. Testes não cobriam os casos acima — adicionados.

Menores corrigidos: `locator` da evidência usa o do bloco; `a_divulgar` tem estado próprio na
projeção; truncagem silenciosa de valor removida do caminho de local.

## Limitações honestas

- `conteudo_programatico` em 31,2% **não** significa 31,2% do país: o denominador são os 16
  concursos com edital analisado.
- 577 concursos continuam sem edital oficial. Nenhum scraper novo foi adicionado; a justificativa
  e a métrica que a mudaria estão registradas na pesquisa da fase.
- A associação do DOU está **diagnosticada, não corrigida**: mudar a identidade da fonte afeta
  criação de concursos e exige decisão própria. O diagnóstico aponta o concurso e o motivo.
- A primeira leva de propostas (1117) foi gerada antes dos ajustes da revisão; os ajustes
  acrescentaram 19 variantes mais qualificadas (com UF, listas separadas). As antigas permanecem
  como candidatas — substituí-las é decisão humana, não automática.
- Nenhum campo foi confirmado: 0 revisões, 0 valores vigentes. O ganho é de **candidatos
  rastreáveis**, não de confirmação.

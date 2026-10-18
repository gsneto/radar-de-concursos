# Prova real — Fase 31: OCR, vagas agregadas e requisitos inline

Data: 2026-10-17. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` (schema v18, sem migração).

## Suíte de testes

- Baseline: **1368 testes, OK**.
- Final: **1397 testes, OK** (+29): `tests/test_ocr_and_extraction.py` (28), `test_ui.py` (+1).
  1 teste é pulado quando o motor de OCR está instalado (`test_ocr_recusa_sem_motor`).

## OCR — diagnóstico e piloto

Documento: `b9f1ad9a…` / versão `e02eae03…` / `ibfc-485` (TJPE).

| Verificação | Valor |
|---|---|
| Producer | `Microsoft: Print To PDF` |
| Páginas | 2 |
| Fontes | **0** |
| Spans de texto | **0** |
| Imagens | **0** |
| Desenhos vetoriais | **4.645** |

Conclusão: texto em contornos vetoriais. Não é scan, não é corrupção.

Piloto (motor Windows OCR, `pt-BR`, 300 dpi):

| Métrica | Valor |
|---|---|
| Páginas processadas | 2 de 2 |
| Caracteres reconhecidos | **4.960** (2.712 + 2.248) |
| Duração | 1.530 ms (562 + 483 ms por página) |
| Blocos gravados | 2 (um por página) |
| Propostas geradas | 0 (o ato é decisão judicial, sem campo do Radar) |
| Hash do original | **inalterado** (`e0834d70…`) |
| Estado da versão | `falhou/pdf_sem_texto` → `parcial` |
| Evento de análise | engine, idioma, dpi, duração, chars, `derived_layer`, `source_sha256` |

Qualidade observada: texto legível e utilizável, com erros previsíveis de OCR em acentos e
maiúsculas ("JURíDlCO" em vez de "JURÍDICO"). Por isso a proposta derivada sempre nasce com o
motivo "texto reconhecido por OCR — conferir no documento original".

`pdf_sem_texto` restantes na base: **0**.

## Quadro de vagas

Base real, `ibfc-490`:

| Métrica | Valor |
|---|---|
| Linhas do quadro | 27 |
| Soma das linhas | 228 |
| TOTAL publicado | 228 |
| Confere | **sim** |
| Modalidades no cabeçalho | ampla, negros, pcd |
| Nota de rodapé detectada | sim |
| `vagas_total_publicado` criadas | **44** (27 linhas + total, em 2 quadros: 002/2026 e 003/2026) |
| `immediate_vacancies` / indígenas criadas a partir do total | **0** |

Nenhum total foi dividido por percentual; nenhuma vaga indígena foi inferida.

## Requisitos inline

| Métrica | Valor |
|---|---|
| Propostas `education` por `requisito-inline` | **10** |
| `accepted_courses` (cursos citados) | **8** |
| `si_compatibility` (candidatos) | **10** |
| Citações inválidas | **0** |

Exemplos extraídos: "Enfermagem", "Administração", "Arquitetura", "Engenharia Civil",
"Engenharia Agrimensura", "Engenharia Elétrica" — sempre com o cargo do cabeçalho no motivo.

Distribuição de `si_compatibility` na base (inclui fases anteriores): 74
`incompativel_com_requisito_explicito`, 38 `ambiguo`, 2 `abrangido_por_categoria`, 1
`aceito_expressamente` — este último com trecho literal "…tais como Ciência da Computação,
Sistemas de Informação".

## Duplicidades

| Classificação | Grupos | Propostas |
|---|---|---|
| Duplicidade textual (mesmo trecho e valor) | **8** | 47 (39 excedentes) |
| Repetição legítima (mesmo valor, trechos diferentes) | 12 | — |

Nada foi apagado. O relatório histórico da Fase 30 (18 grupos/49 excedentes) usa chave sem
offsets e permanece disponível como métrica anterior.

## Antes e depois (base real)

| Item | Antes | Depois | Δ |
|---|---|---|---|
| Documentos | 789 | 789 | 0 |
| Versões | 789 | 789 | 0 |
| Blocos | 11.550 | **11.552** | +2 (OCR) |
| Propostas | 4.750 | **4.822** | +72 |
| Evidências | 4.750 | **4.822** | +72 |
| Documentos com texto | 788 | **789** | +1 |
| `pdf_sem_texto` | 1 | **0** | −1 |
| Extrações parciais (prefixo) | 13 | **13** | 0 |
| Revisões humanas | 0 | **0** | 0 |
| Valores vigentes | 0 | **0** | 0 |

Composição do delta (72 propostas): 44 `vagas_total_publicado`, 10 `education`,
8 `accepted_courses`, 10 `si_compatibility`.

Durante a revisão independente, 2 propostas de `vagas_total_publicado` criadas por engano no
quadro do `004/2026` (layout por NTE/município, sem cargo na tabela) foram **removidas
precisamente** — identificadas por `extraction_method` + motivo, sem revisão e sem valor vigente
associado — e o parser passou a não emitir linha quando o cargo não é identificável. A
reexecução confirmou 0 novas.

## Integridade

```
backup: radar.sqlite3.bak-20261017-204553 (início) e -210200 (antes do apply) | integrity ok
apply em cópia isolada: +72; 2ª execução 0
apply na base real: +72; 2ª execução 0
integrity_check: ok | foreign_key_check: []
revisoes_campo / valores_atuais: 0 / 0
GET /api/concursos: contrato v1 (18 campos) intacto
hash do PDF original: inalterado
```

## Revisão independente

Ver seção J do relatório final; achados críticos e importantes corrigidos antes do commit.

## Limitações honestas

- OCR depende do motor do Windows com modelo `pt-BR`. Em máquina sem o modelo, o comando recusa
  com `ocr_modelo_ausente` e o documento continua `pdf_sem_texto`.
- O OCR foi aplicado a **1 documento** (2 páginas). Não houve varredura indiscriminada.
- Qualidade de OCR não é perfeita (acentos e maiúsculas); toda proposta derivada é marcada.
- Os 13 PDFs longos continuam **parciais** (prefixo de 40 páginas), agora com contagem explícita.
- O quadro de vagas do IBFC publica total agregado: **não** há vagas imediatas nem indígenas
  derivadas dele. Para o Radar, esses concursos continuam sem `immediate_vacancies`.
- `si_compatibility` é candidato; 74 marcações de "incompatível" exigem revisão humana — não são
  parecer jurídico.

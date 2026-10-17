# Prova real — Fase 30: pipeline documental end-to-end

Data: 2026-10-17. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` (schema v18).

## Suíte de testes

- Baseline: **1333 testes, OK**.
- Final: **1368 testes, OK** (+35): `test_pipeline.py` (32), `test_document_extract.py` (+3).

## Estado dos 48 anexos IBFC

| Etapa | Antes | Depois |
|---|---|---|
| Descoberto | 48 | 48 |
| Baixado (versão com hash) | 48 | 48 |
| Validado (assinatura/MIME/tamanho) | 48 | 48 |
| Registrado no repositório | 48 | 48 |
| Identidade + concurso | 48 | 48 |
| Classificado (`tipo_documental`) | 48 | 48 |
| Extraído (blocos) | **0** | **48** |
| Com evidência por página | **0** | **48** |
| Com propostas | **0** | **4** (os 4 editais) |
| Pronto para revisão | 0 | 4 |

Os 44 restantes são resultados, comunicados, convocações e retificações: têm texto e blocos, mas
não produzem campo do Radar — resultado de lista não contém vaga, requisito, prazo ou local.

## Extração

| Métrica | Antes | Depois | Δ |
|---|---|---|---|
| Blocos | 9.536 | **11.550** | +2.014 |
| Propostas | 3.608 | **4.750** | +1.142 |
| Evidências | 3.608 | **4.750** | +1.142 |
| Versões extraídas | 732 | **788** | +56 |
| Revisões humanas | 0 | **0** | 0 |
| Valores vigentes | 0 | **0** | 0 |

Propostas dos anexos IBFC: `conteudo_topico` 1.210, `conteudo_disciplina` 47,
`conteudo_secao` 10, `exemption_start` 4, `exemption_appeal` 4, `exam_location`/`exam_uf`/
`exam_municipio` 1 cada.

## PDFs longos e sem texto

| Caso | Quantidade | Tratamento |
|---|---|---|
| PDF com 404–3.094 páginas | **13** | prefixo de 40 páginas, `truncated: true`, `total_pages`, limitação no evento |
| PDF sem camada de texto (texto vetorial, 4.645 desenhos) | **1** | `pdf_sem_texto` + `ocr-pendentes` com motivo |

O documento sem texto é "Edital nº 11 - Cumprimento de Decisão Judicial" (2 páginas, 521 KB):
`pypdf` 0 caracteres, `pymupdf` 0 caracteres, 0 imagens, 4.645 desenhos. O texto é vetorial —
só OCR resolve. O motor **não** está instalado (`tesseract` ausente) e não foi instalado.

## Cobertura (base real)

| Indicador | Valor | Denominador |
|---|---|---|
| Concursos (certames) | 634 | — |
| Com documento | 540 | 634 (85,2%) |
| Com edital principal | 21 | 634 (3,3%) |
| Documentos | 789 | — |
| Com texto | 788 | 789 (99,9%) |
| Versões extraídas | 788 | 789 (99,9%) |
| Propostas | 4.750 | — |
| Campos confirmados | 0 | — |

Categorias por concurso (exclusivas): `texto_sem_campo` 519, `sem_documento` 94,
`campo_candidato` 19, `proposta_sem_campo_decisivo` 2.

Documentos por bloqueio: `sem_propostas` 714, `pronto_para_revisao` 74, `sem_texto` 1.

## Duplicidades

- Novas duplicatas por extração: **0** (chave escopo+campo+valor+bloco+citação+offsets).
- Históricas: **18 grupos / 49 propostas excedentes**, todas em documentos já existentes
  (`anexos-r2` e outros), **preservadas** e listadas por `pipeline-duplicados` para decisão
  humana. Nada foi apagado.
- URL repetida no mesmo concurso: 0. Hash repetido por documento: 0.

## Idempotência

- Cópia isolada: 1ª execução 56 extraídas; 2ª execução **0** novas.
- Base real: apply 56; 2ª execução **0** novas (`total: 0`).
- Versão nova preserva a versão anterior (teste dedicado).
- Decisão humana sobrevive a reprocessamento (teste dedicado).

## IBFC: o que cada certame tem hoje

| Certame | Docs | Com texto | Editais | Propostas | Campo decisivo |
|---|---|---|---|---|---|
| ibfc-485 | 49 | 48 | 6 | 384 | — |
| ibfc-490 | 14 | 14 | 3 | 758 | — |
| ibfc-497 | 2 | 2 | 1 | 6 | `exam_location` |
| ibfc-496 | 1 | 1 | 0 | 0 | — |
| ibfc-498 | 1 | 1 | 0 | 0 | — |

**Por que não há vagas/requisitos dos editais IBFC:** o "Quadro de Vagas" do IBFC publica um
**total agregado** ("Total de Vagas (Ampla, Negros e PCD)") — somar modalidades é proibido pelo
domínio, então não existe `immediate_vacancies` legítimo nesse formato. Os requisitos usam
`2.6.2. PROFESSOR … Requisito: Diploma …` (inline, sem subitem numerado), formato que o extrator
de seções não cobre. Registrado como pendência, não inventado.

## Integridade

```
backup: radar.sqlite3.bak-20261017-193913 | integrity: ok | v18
backup: radar.sqlite3.bak-20261017-195229 | integrity: ok | v18
apply: 56 versões extraídas, 1 falha permanente (pdf_sem_texto)
2ª execução: 0
integrity_check: ok | foreign_key_check: []
revisoes_campo / valores_atuais: 0 / 0
GET /api/concursos: contrato v1 (18 campos) intacto
```

## Revisão independente

**1 crítico, 7 importantes, menores.** Todos corrigidos com teste:

1. **Crítico** — `ocr-pendentes` respondia "0 precisam de OCR" quando não conseguia inspecionar
   (sem `pymupdf`), escondendo o único PDF que precisa de OCR. Agora `needs_ocr=None` +
   `inspecao_indisponivel`, fallback de contagem com `pypdf`, e o caso já confirmado por
   `pdf_sem_texto` aparece com motivo próprio.
2. Documento que falhou era reportado como "extração não executada" → `blocked_at` deriva do
   estado/`error_code` (`sem_texto`, `paginas_excedidas`, `falhou`, `nao_iniciada`).
3. `falhas_extracao` contava truncamento bem-sucedido como falha → conta só falha real.
4. `pypdf` importado fora do `try` deixava a versão presa em `nao_iniciada` → código
   `extrator_indisponivel` e evento de falha.
5. CLI legada gravava `error_code='ExtractionError'` e ignorava o prefixo → usa `error.code` e
   `PREFIX_PAGES`.
6. Dry-run abortava com traceback em id inválido → erro isolado por versão (e a lista de falhas
   não é mais sobrescrita).
7. Teste do prefixo não provava truncamento (1 página, `max_pages` 400) → teste com 3 páginas,
   `max_pages=2`, `prefix_pages=1`, verificando `truncated`, `total_pages` e página do bloco.
8. `documento_sem_texto` era atribuído a documento nunca analisado → separado por `error_code`.

Menores corrigidos: balde por `review_ready`; `—` em percentual nulo na UI; `total/returned/
truncated` na auditoria; `campos_com_proposta` separado de `propostas`; truncamento por
`json_extract`; constantes mortas removidas; `tesseract_path` fora da API; `ocr_report` não
derruba com PDF corrompido; `record_analysis` recusa blocos vazios; `would_write` só sem citação
inválida; `pending` validado na rota; `--version-id` não truncado por `--limit`; `stages` na ordem
canônica.

## Limitações honestas

- **Nenhum campo foi confirmado.** 4.750 propostas são candidatas; 0 revisões, 0 valores vigentes.
- 1 PDF continua sem texto: OCR não está instalado e a instalação é decisão de sistema.
- 13 PDFs foram lidos só no prefixo (limitação registrada); o restante não é processado.
- Os editais IBFC não produzem vagas/requisitos pelos motivos de formato acima.
- 519 concursos têm texto mas nenhum campo relevante: são páginas de agregador/banca, não editais.
- A fila de revisão tem 4.750 itens; a priorização já ordena por conflito, prazo e campo decisivo.

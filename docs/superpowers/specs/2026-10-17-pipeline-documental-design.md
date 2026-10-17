# Design — Fase 30: pipeline documental end-to-end, cobertura oficial e priorização

Data: 2026-10-17. Base: Fase 29 publicada (`d9941a6`), schema v18, 1333 testes.

## Diagnóstico comprovado

Os 48 anexos IBFC recuperados na Fase 29 estavam **baixados e não processados**:
`extraction_state='nao_iniciada'` em 48 de 48, zero blocos, zero propostas. O pipeline parava
entre "baixado" e "extraído" — e nada distinguia isso de "documento sem conteúdo".

Duas falhas adicionais apareceram na auditoria:

1. **13 PDFs legítimos eram recusados por limite de páginas** (404 a 3.094 páginas) com
   `error_code='ValueError'` — um código genérico que não dizia nada e ainda ficava **preso** na
   versão mesmo depois de uma extração bem-sucedida.
2. **Um PDF de 2 páginas não tem camada de texto nem imagem**: 4.645 desenhos vetoriais. O texto
   existe visualmente, mas nenhum extrator de texto o alcança — só OCR.

## Decisões

### 1. Extração declarada, não silenciosa

`extract_document()` substitui o retorno nu por um resultado com `blocks`, `truncated`,
`total_pages`, `limitation` e `extractor_version`. Códigos estáveis:

| Código | Significado |
|---|---|
| `pdf_sem_texto` | sem camada de texto (digitalização ou texto vetorial) — exige OCR |
| `pdf_paginas_excedidas` | acima do limite **e** sem autorização de prefixo |
| `pdf_criptografado` / `pdf_ilegivel` | arquivo inválido |
| `html_sem_texto` / `html_invalido` / `tipo_invalido` | HTML/assinatura |

`extract_blocks()` continua existindo (compatibilidade) e recusa PDF acima do limite.

### 2. Prefixo documentado em vez de recusa

Listas de resultado chegam a 3.094 páginas. Ler o **prefixo** (40 páginas) é melhor que recusar:
o cabeçalho do ato identifica órgão, número, data e natureza, e a limitação fica gravada na
versão e no evento de análise (`"truncated": true`, `"total_pages": N`, `limitation`). O restante
do arquivo **não** é lido — não há processamento de 3.000 páginas para achar nada.

Alternativas rejeitadas: elevar o limite (memória e tempo sem ganho), ignorar o documento
(perde o ato), extrair tudo (custo desproporcional para listas de nomes).

### 3. `extractor_version` no evento de análise

`record_analysis(..., note=)` grava `extractor_version`, `truncated`, `total_pages`, `limitation`
e `blocks` no evento `analise`. Mudança de extrator fica rastreável sem alterar o esquema, e a
evidência antiga continua intacta.

### 4. Estado por documento, oito categorias por concurso

`radar/pipeline.py` audita cada documento em etapas (`descoberto`, `baixado`, `extraido`,
`validado`, `classificado`, `propostas`, `revisavel`) e aponta o **primeiro bloqueio**
(`sem_versao`, `nao_iniciada`, `sem_propostas`).

Por concurso, a categoria é **exclusiva** e explícita: `sem_documento`,
`documento_sem_texto`, `documento_nao_extraido`, `texto_sem_campo`, `campo_candidato`,
`proposta_sem_campo_decisivo`, `campo_confirmado`. Nunca "sem dados".

### 5. Deduplicação intra-versão, relatório para o histórico

`record_analysis` descarta propostas idênticas **dentro da mesma versão** (mesmo escopo, campo,
valor, bloco e citação). Duplicidades históricas (49 propostas excedentes em 18 grupos,
pré-existentes) **não** são apagadas: `duplicate_report` lista para decisão humana. Apagar
histórico é proibido pelo projeto.

### 6. OCR: detectar e declarar, não executar

`radar/ocr.py` mede a necessidade real e a disponibilidade do motor:

- `sem_texto_sem_imagem`, `pagina_imagem`, `texto_vetorial_sem_camada_de_texto`,
  `texto_parcial`, `texto_suficiente`;
- `availability()` informa Tesseract/PyMuPDF/pytesseract/OCRmyPDF;
- `ocr_version()` **recusa** com `ocr_indisponivel` quando o motor não existe.

Pesquisa (2026-10-17): a documentação do PyMuPDF recomenda exatamente esta triagem (imagem,
ausência de texto, milhares de vetores) antes de acionar OCR; OCR é ~1000x mais lento que
extração de texto; OCRmyPDF é MPL-2.0 mas exige Ghostscript (AGPLv3) e Tesseract. Instalar o
motor é decisão de sistema, não efeito colateral de uma fase.

### 7. Nenhuma etapa confirma campo

Extração cria **candidatos com evidência** (página, trecho, versão, hash). `revisoes_campo` e
`valores_atuais` continuam em 0 após o processamento dos 48 anexos — provado por teste.

## Contratos

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/pipeline` | indicadores com denominadores explícitos |
| GET | `/api/pipeline/cobertura` | cobertura por concurso (7 categorias) |
| GET | `/api/pipeline/documentos` | auditoria por documento (etapas e bloqueio) |
| GET | `/api/pipeline/duplicidades` | duplicidades históricas (somente leitura) |
| GET | `/api/pipeline/ocr` | PDFs que precisam de OCR + disponibilidade do motor |

CLI: `pipeline`, `pipeline-documentos`, `pipeline-cobertura`, `pipeline-duplicados`,
`documentos-pendentes`, `documentos-extrair [--apply]`, `ocr-pendentes`.

`GET /api/concursos` permanece com os 18 campos.

## Critérios de aceite

- 48 anexos IBFC extraídos, com blocos e evidência por página.
- PDF longo tratado por prefixo, com limitação registrada.
- PDF sem texto classificado com motivo real, sem OCR indiscriminado.
- Reprocessar não duplica nada; versão nova preserva a anterior.
- Decisão humana sobrevive a reprocessamento.
- Cobertura distingue as oito situações, com denominadores.
- Contrato v1 intacto, base íntegra, suíte e revisão aprovadas.

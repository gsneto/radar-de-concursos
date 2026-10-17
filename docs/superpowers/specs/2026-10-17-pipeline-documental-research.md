# Pesquisa — Fase 30: extração de PDF, OCR, classificação e cobertura

Data das consultas: 2026-10-17. Nenhum código de terceiros foi copiado nesta fase.

## 1. Extração de texto de PDF

| Abordagem | Verificação real | Decisão |
|---|---|---|
| `pypdf` 6.18.1 (já usado) | extrai texto por página; falha em texto vetorial e em digitalização | **mantido** — é o extrator do projeto |
| `pypdf` com `extraction_mode="layout"` | preservaria colunas, mas mudaria todo o texto dos blocos já gravados | rejeitado (quebraria evidências) |
| `pdfplumber` / `PyMuPDF` (`page.get_text`) | disponíveis? `pymupdf` **sim**, `pdfplumber` **não** | `pymupdf` usado apenas para **diagnóstico** (contar texto/vetores/imagens), não para substituir o texto dos blocos |
| `pymupdf` como extrator principal | mudaria offsets e o texto de todas as evidências | rejeitado para extração; aceito para triagem |
| OCR (Tesseract) | binário **ausente** (`shutil.which("tesseract")` → `None`) | detectar e declarar, não executar |

## 2. Limite de páginas

Medição real: 13 PDFs legítimos entre 404 e 3.094 páginas (listas de resultado/isenção).
`pypdf` abre e conta páginas sem problema; extrair 3.000 páginas de nomes não produz campo do
Radar. Decisão: **prefixo de 40 páginas**, com `truncated`, `total_pages` e `limitation`
gravados no evento de análise. Nada é silencioso.

## 3. Texto vetorial sem camada de texto

O documento "Edital nº 11 - Cumprimento de Decisão Judicial" (2 páginas, 521 KB):

```
pypdf: 0 caracteres
pymupdf: get_text() = '' | imagens = 0 | desenhos = 4.645
```

É texto desenhado como caminhos vetoriais. A documentação do PyMuPDF lista exatamente esse
critério ("thousands of small vector graphics (indicating simulated text)") entre os sinais que
justificam OCR. Sem camada de texto e sem imagem, a única saída é rasterizar + OCR.

## 4. OCR: alternativas e custo

| Opção | Licença | Requisitos | Avaliação |
|---|---|---|---|
| **Tesseract + PyMuPDF** (`page.get_textpage_ocr`) | Tesseract Apache-2.0; PyMuPDF AGPL/comercial | binário Tesseract + idioma `por` | menor atrito; integra-se ao PyMuPDF já presente |
| **OCRmyPDF** | MPL-2.0 (software); exige Ghostscript **AGPLv3** | Tesseract + rasterizador + fpdf2/uharfbuzz | poderoso, porém traz AGPL e mais binários |
| `pytesseract` | Apache-2.0 (wrapper) | Tesseract + Pillow | equivalente ao primeiro, uma dependência a mais |
| Serviço em nuvem | comercial | chave, custo por página, envio de documento | rejeitado: dado público, mas custo e privacidade sem justificativa |

Fatos que sustentam "não executar por padrão" (documentação oficial):

- OCR é ~1000× mais lento que extração de texto (PyMuPDF, "OCR");
- Tesseract não reconhece ordem de leitura, colunas, parágrafos nem estrutura (OCRmyPDF,
  "Limitations") — para um edital com tabelas, o resultado exige revisão humana de qualquer forma;
- Tesseract "does not recognize vector graphics" — o caso acima precisa de rasterização em DPI
  alto, com custo de memória por página.

Implementação: `radar/ocr.py` mede e declara. `ocr_version()` recusa com `ocr_indisponivel`
enquanto o motor não estiver instalado.

## 5. Classificação documental e cobertura

| Referência observada | Adoção |
|---|---|
| Pipeline de estágios (descoberta → download → extração → campos → revisão) usada em sistemas documentais | auditoria por documento com **primeiro bloqueio** |
| Funil com denominador explícito (Fase 25, já no projeto) | mantido e estendido às 8 categorias |
| "Ausência ≠ zero" (regra do projeto) | categorias exclusivas; campo ausente nunca vira zero |

Rejeitado: framework de orquestração (Airflow/Prefect) para um pipeline local de 789 documentos;
segunda tabela de estado (o estado é derivável de versões, blocos, propostas e eventos).

## 6. Deduplicação

Chave adotada: `(escopo, campo, valor, bloco, citação, offsets)`. É a mesma chave usada por
`reprocess.py` desde a Fase 26, agora aplicada **na escrita** de `record_analysis`. Duplicidade
histórica não é apagada — é relatada (`duplicate_report`) porque o histórico é imutável.

## 7. Referências consultadas

- `https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html` (triagem de OCR, custo ~1000×,
  texto vetorial não reconhecido)
- `https://ocrmypdf.readthedocs.io/en/latest/installation.html` (dependências: Tesseract,
  Ghostscript/pypdfium2, fpdf2, uharfbuzz)
- `https://ocrmypdf.readthedocs.io/en/latest/introduction.html` (limitações do Tesseract;
  OCRmyPDF MPL-2.0; Ghostscript AGPLv3)
- `https://github.com/ocrmypdf/OCRmyPDF` (licença e instalação por sistema)
- Código do projeto: `document_extract`, `document_fields`, `reprocess`, `monitoring`,
  `data_quality`, `review`, `document_store`.

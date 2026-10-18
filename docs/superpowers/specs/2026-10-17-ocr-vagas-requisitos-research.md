# Pesquisa — Fase 31: OCR, tabelas de vagas e requisitos

Data das consultas: 2026-10-17. Nenhum código de terceiros foi copiado.

## 1. Por que não havia texto

Medição direta no arquivo (não inferência):

| Verificação | Resultado |
|---|---|
| `producer` | `Microsoft: Print To PDF` |
| Fontes na página | **0** |
| Spans de texto (`rawdict`) | **0** |
| Imagens | **0** |
| Desenhos vetoriais | **4.645** (2 páginas) |
| `pypdf` / `pymupdf` `get_text()` | string vazia |

Conclusão: texto convertido em contornos. Não é scan, não é corrupção, não é limitação do
`pypdf`.

## 2. Motores de OCR avaliados

| Motor | Licença | Requisitos | Medição | Decisão |
|---|---|---|---|---|
| **Windows.Media.Ocr** | capacidade do SO | `powershell.exe` 5.1 (WinRT) | `pt-BR` presente; 562 ms e 483 ms para 2 páginas a 300 dpi; 4.960 caracteres | **adotado** |
| Tesseract | Apache-2.0 | binário + `por.traineddata` | binário ausente (`shutil.which` → `None`) | suportado, não instalado |
| OCRmyPDF | MPL-2.0; Ghostscript AGPLv3 | Tesseract + rasterizador + fpdf2 + uharfbuzz | não instalado | rejeitado (peso e AGPL extra) |
| pytesseract | Apache-2.0 (wrapper) | Tesseract + Pillow | não instalado | redundante com o caminho direto |
| Serviço em nuvem | comercial | chave, custo/página, envio do documento | — | rejeitado |

Referências consultadas:

- `https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html` — OCR integrado depende de
  Tesseract externo; recomenda triagem prévia (imagem, ausência de texto, milhares de vetores);
  OCR ~1000× mais lento que extração de texto.
- `https://ocrmypdf.readthedocs.io/en/latest/installation.html` — dependências obrigatórias
  (Tesseract 4.1.1+, Ghostscript ou pypdfium2, fpdf2, uharfbuzz).
- `https://ocrmypdf.readthedocs.io/en/latest/introduction.html` — limitações do Tesseract
  (ordem de leitura, colunas, ausência de estrutura, sem grafia manuscrita); OCRmyPDF MPL-2.0 e
  Ghostscript AGPLv3.
- `https://learn.microsoft.com/uwp/api/windows.media.ocr` — API `OcrEngine`,
  `AvailableRecognizerLanguages`, `TryCreateFromLanguage`, `RecognizeAsync`.

Observação prática: o `pwsh` 7 falha ao carregar WinRT ("Operation is not supported on this
platform"); o `powershell.exe` 5.1 funciona. O módulo força 5.1 e trata a ausência como
`ocr_indisponivel`.

## 3. Rasterização

PyMuPDF 1.28.2 (`get_pixmap(dpi=300)`) — já usado na Fase 30 para diagnóstico; agora também
para renderizar. Licença AGPL-3.0 (ou comercial): uso local, sem distribuir binário nem
oferecer serviço de rede, registrado em `requirements.txt`.

Alternativas: `pypdfium2` (Apache/BSD) exigiria instalação nova; `pdf2image` exige Poppler
(binário externo). Nenhuma vantagem que justifique a instalação nesta fase.

## 4. Tabelas de vagas

| Referência | Aprendizado | Aplicação |
|---|---|---|
| Extrator genérico do projeto (`vacancy_tables`) | opera em células `" | "`; PDF do IBFC vem em linha corrida | não serve para o IBFC; recebeu guarda contra cabeçalho agregado |
| `quadrix_tables` | layout de duas linhas de cabeçalho por modalidade | mantido; não se aplica ao IBFC |
| Prática de domínio do projeto | não somar modalidades sobrepostas nem replicar total | `vagas_total_publicado` isolado; sem distribuição |

O quadro do IBFC tem **um total por linha** que já inclui ampla + negros + PCD e **não menciona
indígenas**. Qualquer divisão seria invenção.

## 5. Requisitos em texto corrido

O extrator de seções exige `N.M.k Requisitos:`; o de rótulos exige "requisitos de
escolaridade". O IBFC usa `Requisito:` no fim do parágrafo do cargo. Solução própria:
rótulo + cargo do cabeçalho anterior **no mesmo bloco** + corte em `Atribuições:`.

Teste de qualidade: `accepted_courses` capturava "instituição" porque `_courses_from` casa
"curso … em". Corrigido com padrão dedicado (`curso de nível superior em X`) e lista de
genéricos proibidos.

## 6. Duplicidade

Chave adotada: `(escopo, campo, valor, bloco, citação, offsets)`. Incluir os offsets separa
duplicidade real de repetição legítima no mesmo bloco (sumário e corpo). O relatório histórico
da Fase 30 (18 grupos/49 excedentes) usava chave sem offsets e por isso conta mais; ambos são
somente leitura.

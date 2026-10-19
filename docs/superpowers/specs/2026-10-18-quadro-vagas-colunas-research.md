# Pesquisa — Fase 41: extração de quadros de vagas complexos

Data: 2026-10-18. Consultas feitas nesta data.

## Fontes oficiais consultadas

| Uso | URL |
|---|---|
| Página oficial SEDUC-PA | https://conhecimento.fgv.br/concursos/seducpa26 |
| Edital consolidado SEDUC-PA (usado no Radar) | https://conhecimento.fgv.br/sites/default/files/concursos/edital-consolidado-01.10-minuta.pdf |
| Página oficial TJAP | https://conhecimento.fgv.br/concursos/tjap26 |
| Edital retificado TJAP (usado no Radar) | https://conhecimento.fgv.br/sites/default/files/concursos/tjap.versao-final.13.10.pdf |
| Página oficial TJRS | https://conhecimento.fgv.br/concursos/tjrsjuiz26 |
| Edital consolidado TJRS (usado no Radar) | https://conhecimento.fgv.br/sites/default/files/concursos/sei_9998416_edital_consolidado.pdf |

As três versões já estavam armazenadas e foram conferidas por SHA-256 antes de qualquer
leitura:

| Concurso | sha256 | bytes | páginas |
|---|---|---|---|
| SEDUC-PA | `bd30f562442e…` | 2.447.614 | 151 |
| TJAP | `b8faf5646486…` | 912.420 | 74 |
| TJRS | `5aead3396e64…` | 401.337 | 54 |

Nenhum documento foi substituído por cópia externa: a identidade foi verificada contra o
hash da versão armazenada.

## Alternativas avaliadas

| Alternativa | Licença/dependência | Avaliação |
|---|---|---|
| **pypdf (já usado)** | BSD, instalado | Extrai texto por página, mas **achata** a tabela: perde a célula. Foi a causa dos 42/406 erros na primeira tentativa de reconstrução por texto. Mantido para o texto/evidência. |
| **PyMuPDF (já declarado para OCR)** | AGPL-3.0/comercial, instalado | Dá `get_text("words")` com caixa delimitadora por palavra. Determinístico, sem OCR, sem modelo. Adotado **apenas** para coordenadas. |
| pdfplumber | MIT, nova dependência | `extract_tables` depende de linhas/réguas; o Anexo II usa células mescladas e sem grade. Não resolve melhor que o agrupamento posicional e adiciona dependência. |
| Camelot | MIT, requer Ghostscript/OpenCV | Pesado para Windows, pensado para tabelas com grade; mesmo limite de células mescladas. |
| Tabula | MIT, requer Java | Runtime externo; não se justifica para um quadro. |
| Modelos de detecção de tabela (LayoutLM etc.) | Pesos e runtime adicionais | Não determinístico, sem garantia de coordenada para a evidência; proibido como autoridade pela missão. |
| LLM para decidir distribuição | — | Proibido pela missão: a distribuição precisa ser auditável por cabeçalho, célula, linha, legenda e página. |

Decisão: **nenhuma biblioteca nova**. O problema foi resolvido estendendo o parser existente
com uma camada posicional sobre uma dependência já declarada.

## Técnicas aplicadas

### Extração posicional por cabeçalho

O cabeçalho é a âncora: as siglas (`AC`, `PcD`, …) são localizadas por palavra e suas
coordenadas x definem as fronteiras das colunas (ponto médio entre centros vizinhos). Isso
funciona com cabeçalho repetido a cada página e com colunas de largura irregular.

### Células mescladas e multilinha

Cada célula de identificação (cargo, formação, escolaridade) é um bloco de linhas contíguas
da mesma coluna. O bloco pertence à linha cujo número está no **centro vertical** do bloco.
Testado contra o Anexo II real: 381 linhas, 24 regionais e total geral fechando em 2.000.

### Tabelas distribuídas entre páginas

O cabeçalho repete em todas as páginas; a linha cortada na quebra tem a célula continuada no
topo da página seguinte. O parser costura o rótulo com essas palavras e mantém a evidência
na página dos números, com nota `[rotulo completado na pagina seguinte]`.

### Notas de rodapé e abreviações

As siglas são resolvidas pelas definições do próprio edital (`modality_legend`), não por um
dicionário global. O asterisco é procurado como nota curta que fale de vaga/reserva; a linha
`RENDA*` do formulário socioeconômico é descartada por não falar de vaga.

### Valores numéricos e separadores

Células são inteiros simples (`0`–`2000`). A notação de reserva (`10+CR`, `CR*`) é
interpretada separadamente, sem conversão de percentual e sem rateio.

### Categorias exclusivas × unificadas

A distinção vem da definição no documento (`vaga unificada`). `PPIQ` e `PI/PQ` são
persistidas em campos próprios e nunca somadas a `PI`. O teste de soma valida que
`AC + PcD + PP + PI + PQ + PPIQ + PI/PQ = Total`, o que confirma que as colunas são posições
distintas e não subconjuntos.

### Proveniência e revisão

Toda proposta carrega `block_index`, `quote` literal, `start_offset`/`end_offset`,
`page_number`, cabeçalho, rótulo e motivo. O reprocessamento revalida a citação contra o
bloco antes de gravar. Nenhuma proposta é confirmada automaticamente.

## Medições na base real

| Concurso | Linhas | Regionais | Total geral | PI | PPIQ | PI/PQ |
|---|---|---|---|---|---|---|
| SEDUC-PA | 381 | 24 (todas fecham) | 2.000 (fecha) | 30 | 180 | 138 |
| TJAP | 1 | — | 15 imediatas + CR | — | — | — |
| TJRS | 1 | — | 30 (fecha) | 1 | — | — |

As 24 regionais do Anexo II fecham individualmente contra a linha `TOTAL – DRE - …`, e a
soma das 24 fecha contra `TOTAL GERAL` (1.169 / 169 / 284 / 30 / 30 / 180 / 138 / 2.000).
Esse é o teste mais forte de que o mapeamento de colunas está correto: um deslocamento de
coluna quebraria a soma.

## Limitações registradas

- 4 linhas do Anexo II têm a célula de escolaridade cortada pela quebra de página
  (`escolaridade_incompleta`); o cargo está completo e a linha é proposta.
- O asterisco do TJAP não tem nota no edital (`asterisco_sem_nota`).
- O Anexo II-A é delimitado e excluído: a matriz descreve a ordem de convocação.

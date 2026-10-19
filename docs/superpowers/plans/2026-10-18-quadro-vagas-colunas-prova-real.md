# Prova real — Fase 41

Data: 2026-10-18. Base `data/radar.sqlite3`, schema v21. Branch `radar-configuracao`.

## Antes

- HEAD `78b4a36` (F40), árvore limpa, sincronizada.
- Suíte: 1.775 testes, 1 skip, OK.
- Backup: `data/radar.sqlite3.bak-20261018-201435` (63.340.544 bytes, v21, `integrity ok`).
- Base: 1.232 documentos, 1.072 versões, 7.648 propostas, 0 revisões, 0 valores atuais,
  0 reconciliações, 11 revalidações.

## Depois

- Suíte: **1.815 testes**, 1 skip, OK (`RESULT OK`). 40 testes novos.
- `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: vazio.
- 1.232 documentos, 1.072 versões, **9.211 propostas** (+1.563), 0 revisões,
  0 valores atuais, 0 reconciliações, 11 revalidações.
- Nenhuma decisão humana criada ou alterada.

## SEDUC-PA (`f4235e23`, versão `08f0dcaf…`, sha256 `bd30f562…`)

Documento: `edital-consolidado-01.10-minuta.pdf`, 151 páginas. O Anexo II ocupa as páginas
impressas 63–83, que coincidem com o índice do PDF nesta versão (verificado página a
página). O Anexo II-A começa na página 84 e foi **excluído** da leitura.

| Métrica | Resultado |
|---|---|
| Linhas lidas | 381 |
| Regionais | 24 (todas fecham contra `TOTAL – DRE - …`) |
| Total geral | 2.000 (soma das 24 regionais confere) |
| PI (indígenas exclusivas) | **30** |
| PPIQ (unificada PP+PI+PQ) | **180** |
| PI/PQ (unificada PI+PQ) | **138** |
| AC / PcD / PP / PQ | 1.169 / 169 / 284 / 30 (no relatório e no trecho) |
| Propostas persistidas | 1.524 (381 × 4 campos) |
| Pendências | 4 `escolaridade_incompleta` (célula cortada na quebra de página) |

Validação aritmética: cada linha fecha (`AC+PcD+PP+PI+PQ+PPIQ+PI/PQ = Total`), cada regional
fecha contra sua linha de totalização e a soma das regionais fecha contra `TOTAL GERAL`
(1.169 / 169 / 284 / 30 / 30 / 180 / 138 / 2.000). Um deslocamento de coluna quebraria
essas somas.

Cada linha é um escopo próprio: 381 escopos distintos, incluindo
`Professor / Educação Especial AEE / DRE …` e `Professor / Educação Especial LIBRAS / DRE …`
separados (o rótulo não usa `" - "`, que a revisão truncaria).

## TJAP (`4b5579c4`, versão `1654878b…`, sha256 `b8faf564…`)

| Célula publicada | Leitura | Proposta |
|---|---|---|
| `10+CR` | 10 imediatas + reserva | total da linha |
| `1+CR` | 1 imediata + reserva | — |
| `4+CR` | 4 imediatas + reserva | — |
| `CR*` (indígenas) | reserva, quantidade não publicada | `indigenous_reserve_notation = "CR*"` |
| `CR*` (quilombolas) | reserva, quantidade não publicada | — |
| `15 + CR` | 15 imediatas + reserva | `immediate_vacancies = 15` |

- Soma das modalidades imediatas (10+1+4) = 15 = total ✓.
- **Nenhuma** vaga indígena imediata foi criada; 3% de 15 não foi calculado.
- O asterisco **não tem nota localizável** no edital (a única ocorrência de `*` é o campo
  `RENDA*` do formulário socioeconômico): pendência `asterisco_sem_nota`.
- Matriz: cargo `Juiz de Direito Substituto` com `reserva_sem_quantidade` e elegibilidade
  `incompativel_por_requisito` (bacharelado em Direito).

## TJRS (`7c54d7df`, versão `aa55ea79…`, sha256 `5aead339…`)

Trecho literal (p. 1):

> … para provimento de 30 (trinta) vagas no cargo de JUIZ DE DIREITO SUBSTITUTO … restando
> a seguinte distribuição: 19 (dezenove) vagas para ampla concorrência, 01 (uma) vaga para
> pessoas com deficiência, 08 (oito) vagas para negros, 1 (uma) vaga para indígenas e 1
> (uma) vaga para quilombolas.

| Métrica | Resultado |
|---|---|
| Total | 30 |
| Indígenas | **1** |
| Soma das modalidades | 19+1+8+1+1 = 30 ✓ |
| Cargo | JUIZ DE DIREITO SUBSTITUTO (mesma frase do total) |

A retificação armazenada (`sei_9940985_edital-retificativo.pdf`) é a que deu origem ao
consolidado; não há outra versão que altere a distribuição. A matriz mostra
`cargo_imediata` para o cargo (identidade ainda pendente de reconciliação humana).

## Revisão independente

Foram corrigidos, antes do fechamento:

| Achado | Correção |
|---|---|
| **Crítico** — cabeçalho de 5 de 6 modalidades deslocava colunas e criava vaga indígena falsa | `_notation_header` exige as 6 na ordem canônica; pendência `cabecalho_incompleto` |
| **Crítico** — "1 vaga para indígenas e quilombolas" virava vaga exclusiva | rótulo com dois grupos vai para `combined`; pendência `modalidade_combinada` |
| **Alto** — 14 linhas idênticas em regionais diferentes eram deduplicadas e uma regional perdia vagas | offsets não reutilizados (`skip`) + marcador da regional; 381/381 trechos únicos |
| **Alto** — costura entre páginas aplicada a qualquer linha incompleta | só a última linha da página costura; palavras de continuação não entram no rótulo seguinte |
| **Alto** — linha sem valor na primeira coluna era absorvida pela anterior | âncora em qualquer coluna numérica + pendência `celula_nao_numerica` |
| **Alto** — definição com dois grupos sem a palavra "unificada" virava exclusiva | `len(groups) > 1` ⇒ unificada |
| **Alto** — trecho com cadastro de reserva era lido como vaga imediata | pendência `cadastro_de_reserva_no_trecho`; total não é proposto como imediato |
| **Médio** — `reprocess.py` com texto duplamente codificado | restaurado do HEAD e reaplicado em UTF-8 |
| **Médio** — carteira ignorava a notação `CR*` | `indigenous_reserve_notation` em `decisive_fields` → `apenas_reserva` |
| **Médio** — divergência de regional/total geral não chegava às pendências | `regional_divergente` e `total_geral_divergente` |
| **Médio** — célula `-` descartava a linha | `-` é zero explícito |
| **Médio** — rótulo com `" - "` fundia AEE e LIBRAS | travessões internos normalizados; escopos separados |
| **Médio** — `0+CR` perdia a reserva | emite zero imediato **e** notação |
| **Médio** — `_artifact_path` não validava contenção | compara com `<db>.documents` |
| **Baixo** — Anexo II-A podia ser lido como quadro | intervalo termina no Anexo II-A e cabeçalho precisa estar numa única linha |

## Limitações remanescentes

- O asterisco do TJAP continua sem explicação documental.
- A matriz de convocação (Anexo II-A) não é lida como vagas — por decisão, não por falha.
- 4 linhas do Anexo II têm a escolaridade cortada pela quebra de página; o cargo está
  completo e a linha é proposta com a pendência registrada.

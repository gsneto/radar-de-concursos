# Prova real — Fase 42

Data: 2026-10-18. Base `data/radar.sqlite3`, schema v21. Branch `radar-configuracao`.

## Antes

- HEAD `e0709c6` (F41), árvore limpa, sincronizada com o remote.
- Suíte: **1.815 testes**, 1 skip, OK.
- Backup: `data/radar.sqlite3.bak-20261018-224221` (64.610.304 bytes, v21, `integrity ok`,
  FK vazia).
- Base: 1.232 documentos, 1.072 versões, 9.211 propostas, 0 revisões, 0 valores vigentes,
  0 reconciliações, 0 lotes.
- Snapshot: 2026-10-18T22:42:10-03:00.

## Depois

- Suíte: **1.833 testes**, 1 skip, OK (`RESULT OK`). 18 testes novos.
- `PRAGMA integrity_check`: `ok`; `foreign_key_check`: vazio.
- 9.211 propostas (inalteradas), 0 revisões, 0 valores vigentes, 0 reconciliações,
  0 lotes; **8 eventos documentais** novos (reparo de rótulo).
- Nenhuma decisão humana foi criada pela fase.

## Grupos de revisão (linha documental)

| Concurso | Grupos | Com quadro | Propostas |
|---|---|---|---|
| SEDUC-PA (`f4235e23`) | 629 | **381** | 1.801 |
| TJAP (`4b5579c4`) | 359 | 1 (notação) | 370 |
| TJRS (`7c54d7df`) | 275 | 1 (texto) | 18 |

O grupo é a evidência: versão, bloco, página e offsets. Linhas com o mesmo valor em trechos
diferentes continuam separadas (teste `test_mesmo_valor_em_trechos_diferentes_nao_agrupa`).

## Quatro linhas de escolaridade incompleta

`quadro-auditoria` sobre a versão `08f0dcaf…` (SEDUC-PA), com o parser sem e com costura:

| Página | Páginas | Antes | Depois |
|---|---|---|---|
| 68 | 68+69 | Física / "Nível" | Física / **"Nível Superior"** |
| 71 | 71+72 | "Língua" / "Nível" | **"Língua Portuguesa"** / **"Nível Superior"** |
| 73 | 73+74 | Biologia / "Nível" | Biologia / **"Nível Superior"** |
| 76 | 76+77 | Filosofia / "Nível" | Filosofia / **"Nível Superior"** |

A continuação está no topo da página seguinte, na **mesma faixa de coluna**, e a linha é a
última da página anterior — por isso a costura é comprovada (`continuacao_comprovada: true`).
A evidência permanece na página em que os números foram publicados.

Uma quinta linha (p. 70/71, "Especialista em" / "Especialista") também foi completada; ela
não estava na lista das quatro porque o defeito era no cargo, não na escolaridade.

## Defeito encontrado e corrigido: contaminação entre páginas

A costura da F41 usava todas as palavras acima da primeira linha da página seguinte. Como o
rótulo da primeira linha também é multilinha, ele era colado na linha anterior:

- `Especialista em Educação / Especialista em Educação **Assistente de** / DRE CAPANEMA`
  (rótulo contaminado, e a nota de costura entrava no escopo);
- `Professor / **Língua** / DRE CASTANHAL` (formação truncada).

Correção: blocos de rótulo (gap 14 pt) e exclusão do bloco da primeira linha; nota após
`" - "`, fora do escopo; evidência localizada pelo rótulo bruto.

Reparo aplicado (`label_repair_v1`): **8 propostas** (2 linhas × 4 campos), com evento
`analise` de antes/depois. Idempotente (segunda passada: 0). Guardas: sem decisão, sem valor
vigente, sem lote. Resultado: 381 escopos distintos na SEDUC-PA — um por linha física —,
sem escopo fantasma e sem proposta nova.

## Validação aritmética

- SEDUC-PA: 381 linhas, 24 regionais, total geral 2.000; **PI 30, PPIQ 180, PI/PQ 138**;
  todas as regionais fecham e a soma das regionais fecha contra o total geral.
  Nenhuma linha divergente (`linhas_divergentes: 0`).
- TJAP: total publicado `15 + CR`; células `10+CR / 1+CR / 4+CR / CR* / CR*`; soma das
  imediatas 15 = total; `CR*` permanece reserva sem quantidade.
- TJRS: total 30 e distribuição 19+1+8+1+1 = 30; indígena = 1 (publicado, não calculado).

## Carteira preparada para revisão (sem decisão)

Destaques de elegibilidade: **11 em 6 concursos** (inalterado). Fila priorizada por
evidência existente, não por score de confiança:

1. vaga indígena imediata do cargo (quando publicada);
2. SI aceito expressamente / categoria sustentada;
3. identidade pendente que basta para decidir;
4. conflitos que afetam prazos;
5. reserva indígena com escopo documentado.

O TJRS (1 vaga indígena, cargo de Direito) **não** entra como recomendação para o perfil de
Sistemas de Informação: a reserva não altera a incompatibilidade do requisito. O TJAP não
recebe vaga imediata indígena por inferência.

## Limitações remanescentes

- `CR*` do TJAP continua sem nota explicativa no edital.
- 248 grupos da SEDUC-PA não têm quadro (escolaridade, prazos, conteúdo): são contexto
  documental, não linha de tabela.
- Nenhum reparo é aplicado automaticamente a propostas com decisão humana.

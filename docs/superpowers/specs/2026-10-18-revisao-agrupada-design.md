# Design — Fase 42: revisão agrupada por linha documental

Data: 2026-10-18. Base: Fase 41 (`e0709c6`), schema v21 (inalterado). 1.815 testes.

## Problema

A Fase 41 deixou 1.528 propostas candidatas (1.524 da SEDUC-PA, 2 do TJAP, 2 do TJRS)
e a Mesa de Revisão continuava **por proposta**. Revisar um quadro de vagas assim perde o
contexto que dá sentido ao número: cabeçalho, coluna, total, regional, notas, páginas.
Pior: convida a confirmar um total sem olhar a quantidade indígena ao lado.

Além disso, a inspeção do estado real encontrou um defeito de dados da Fase 41: a costura
entre páginas usava **todas** as palavras acima da primeira linha da página seguinte, o que
contaminou o rótulo de uma linha da SEDUC-PA com o rótulo da linha seguinte
("Especialista em Educação / Especialista em Educação **Assistente de**"). Outra linha ficou
com a formação truncada ("Língua" em vez de "Língua Portuguesa"). A nota de costura também
entrava no rótulo de escopo, porque não havia separador.

## Decisões

### 1. Grupo = linha documental, não valor

`radar/review_groups.py` agrupa por `(version_id, block_id, page_number, start_offset,
end_offset)` — a identidade da evidência. Duas propostas com o mesmo valor em trechos
diferentes ficam em grupos diferentes; quatro campos do mesmo trecho ficam juntos. Nunca se
agrupa por igualdade de valor nem por proximidade na base.

### 2. O grupo é contexto; a decisão é por campo

Cada proposta do grupo mantém `state`, `last_decision`, `selected`, `evidence_sha256` e
histórico próprios. O grupo não tem botão de aprovação: a interface oferece Confirmar /
Rejeitar / Ambíguo / Adiar **por campo**, cada um chamando o endpoint existente
(`POST /api/revisao/proposta/<id>`), com justificativa obrigatória. O estado do grupo
(`pendente` / `parcial` / `decidido`) é derivado, nunca gravado.

### 3. Contexto vem do parser atual, em leitura

Para grupos de quadro, o contexto é recalculado do parser atual (`vacancy_columns`), sem
gravar nada: colunas com valor e natureza (exclusiva, unificada, total), cabeçalho, páginas
(inclusive a página de continuação), regional, notas de legenda, trecho literal. Quando o
rótulo gravado difere do parser, o grupo expõe `rotulo_divergente` — não corrige sozinho.

### 4. Validação aritmética separada da semântica

`validacao` publica `publicado`, `soma`, `diferenca`, `estado` e a `regra` do edital. A
regra da SEDUC-PA é explícita: `AC+PcD+PP+PI+PQ+PPIQ+PI/PQ = Total`, com as unificadas como
posições distintas. Consistência é registrada como consistência; não confirma interpretação.
Divergência mantém o total publicado e apresenta o conflito.

### 5. Costura entre páginas corrigida por bloco

O rótulo da primeira linha da página também é multilinha e fica acima dos números. A
costura agora usa **blocos** de linhas contíguas (gap 14 pt): só os blocos acima do bloco da
primeira linha continuam a página anterior. A evidência é localizada pelo rótulo **bruto**
(o texto que está de fato na página); a costura altera o rótulo do escopo, não o trecho.

### 6. Reparo de rótulo rastreável

`radar/label_repair.py` repara somente `ambiguity_reason` das propostas afetadas, com
guardas: só `quadro-colunas-pdf`; só quando o rótulo do parser **comprova** (prefixo de
palavras do rótulo bruto ou marca legada de costura); nunca com decisão humana, valor
vigente ou lote; idempotente; cada alteração gera evento `analise` com antes/depois. Nada
mais é tocado — valor, evidência, offsets e histórico permanecem.

### 7. Superfície aditiva

- `GET /api/revisao/grupos?contest_id=&document_id=&version_id=&state=&field=&limit=&offset=`
- `python -m radar revisao-grupos …`
- `python -m radar quadro-auditoria …` (antes/depois das linhas que atravessam página)
- UI: seção "Revisão por linha documental" dentro da Revisão humana, paginada por grupo.

## Limites declarados

- Grupo não é confirmação; prioridade não é probabilidade.
- A soma correta não valida a semântica; a divergência não autoriza trocar o total.
- `CR*` continua reserva sem quantidade; nenhum percentual vira vaga.
- O reparo de rótulo não cria, apaga ou reescreve propostas.

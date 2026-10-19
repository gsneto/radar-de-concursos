# Pesquisa — Fase 42: revisão humana agrupada de tabelas

Data: 2026-10-18. Consultas feitas nesta data.

## Perguntas

1. Como agrupar propostas sem inventar relação (por linha real, não por valor)?
2. Como manter decisão independente por campo dentro de um grupo?
3. Como detectar decisão sobre snapshot obsoleto?
4. Como validar aritmeticamente sem transformar soma em confirmação?

## Fontes e padrões consultados

| Fonte | Uso |
|---|---|
| W3C — *Data on the Web Best Practices* (DWBP) | proveniência por registro, versão e evidência; não publicar derivado como original |
| W3C — PROV-O | cadeia `entity → wasDerivedFrom → activity`; inspirou o evento de reparo com antes/depois |
| NIST — *Human-in-the-loop* / automação com revisão | decisão humana explícita, sem aprovação implícita por score |
| Google — *Rules of Machine Learning* (regras antes de modelos) | heurística determinística e explicável para prioridade |
| Martin Fowler — *Optimistic Offline Lock* | detectar alteração desde a abertura (snapshot) e rejeitar a gravação |
| Martin Fowler — *Audit Log* / *Event Sourcing* (append-only) | histórico preservado; nada é sobrescrito |
| SQLite — `PRAGMA integrity_check`, `foreign_key_check`, API de backup | consistência e cópia consistente |
| Documentação MDN — ARIA `aria-expanded`, `aria-live`, foco | acessibilidade do painel agrupado |

Alternativas avaliadas:

- **Framework de tabela (AG Grid, TanStack Table)**: pesado para uma tabela paginada de 20
  linhas; exigiria dependência e build. Rejeitado: a UI atual é vanilla e não tem bundler.
- **Agrupar por `role_id`**: perderia a linha (um cargo tem várias linhas/regionais) e
  juntaria propostas de trechos distintos. Rejeitado.
- **Agrupar por valor + proximidade**: proibido pela missão e arriscado (dois cargos podem
  publicar os mesmos números). Rejeitado.
- **Confirmação em lote**: reduziria cliques ao custo de aprovar sem ler. Rejeitado; a
  missão proíbe aprovação em massa.
- **Nova tabela de grupos**: exigiria migração e criaria um segundo sistema de revisão.
  Rejeitado: o grupo é derivado da evidência e calculado a cada leitura.

## Decisões técnicas

1. **Identidade da linha pela evidência**: versão, bloco, página e offsets. É o único dado
   que liga as propostas ao trecho publicado sem inferência.
2. **Contexto recalculado, não persistido**: o parser atual é a fonte do cabeçalho/colunas/
   total; divergência com o gravado é exposta, não corrigida.
3. **Snapshot por impressão**: `evidence_sha256` (já existente) + `scope_snapshot` do lote
   continuam sendo o mecanismo de concorrência; o grupo apenas exibe o estado.
4. **Validação com a regra do edital**: a soma só é aplicada às colunas que o Anexo II
   define como aditivas; unificadas são posições, não subconjuntos.
5. **Reparo auditado**: evento `analise` com antes/depois no `eventos_documentais`
   (o `CHECK` de `event_type` não permite novo tipo sem migração; a nota identifica o
   reparo). Guardas impedem tocar proposta com decisão.

## O que não foi adicionado

Nenhuma biblioteca nova. Nenhuma migração de schema. Nenhuma coleta externa.

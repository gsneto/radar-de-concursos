# Pesquisa — Fase 43: piloto de revisão humana e reconciliação assistida

Data: 2026-10-19.

## Perguntas

1. Como preparar um lote pequeno e representativo sem escolher só os casos fáceis?
2. Como separar identidade canônica de dimensão (regional) e de oportunidade (linha)?
3. Como provar que a decisão de um campo não confirma os demais?
4. Como validar o fluxo real da UI, não só a API?
5. Como impedir decisão sobre evidência obsoleta quando o ciclo roda?

## Fontes e padrões consultados

| Fonte | Uso |
|---|---|
| W3C PROV-O | cadeia de proveniência; evidência → proposta → decisão |
| W3C WCAG 2.2 (foco, status, progressbar) | `role="status"`, `aria-live`, `<progress>` com rótulo |
| NIST AI RMF — human oversight | decisão humana explícita, sem aprovação implícita |
| Fowler — Optimistic Offline Lock / Audit Log | snapshot por impressão de evidência e histórico append-only |
| SQLite — `PRAGMA integrity_check`, backup API | integridade e cópia consistente |
| Playwright (já disponível no ambiente) | validação do fluxo real no Chromium |

Alternativas avaliadas:

- **Seleção aleatória** do lote: não garante casos-limite e não é reproduzível. Rejeitada.
- **Selecionar pelas maiores prioridades**: concentraria em poucos concursos e esconderia
  casos de zero/unificada. Rejeitada.
- **Agrupar por nome do cargo**: fundiria regionais e requisitos diferentes. Rejeitada pela
  missão.
- **Similaridade textual para identidade**: não é prova; rejeitada. A sugestão usa partes
  explícitas do contexto + vocabulário do próprio edital.
- **Framework de UI**: desnecessário; a página já é vanilla e o fluxo reusa os componentes.
- **Redis/cache externo**: rejeitado; cache em processo com limite e invalidação por versão.

## Decisões técnicas

1. **Cotas de caso + diversidade**: 7 casos obrigatórios, depois cargo/formação/regional, com
   teto de 2 linhas por regional.
2. **Identidade = cargo + formação**: regional vira dimensão; linha vira oportunidade.
3. **Recomposição com prova lexical**: a palavra só é juntada se existir no documento.
4. **Decisão unitária**: um `proposal_id` por ação; `evidence_sha256` sempre enviado.
5. **ThreadingHTTPServer**: remove bloqueio entre painéis; escritas seguem serializadas.
6. **Prewarm opcional**: CLI somente leitura; mede antes/depois.

## O que não foi adicionado

Nenhuma biblioteca nova. Nenhuma migração. Nenhuma coleta externa. Nenhuma decisão humana
artificial.

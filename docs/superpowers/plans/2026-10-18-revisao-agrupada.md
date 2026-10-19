# Plano — Fase 42: revisão agrupada, auditoria do quadro e preparação da carteira

Data: 2026-10-18. Base `e0709c6` (F41), schema v21, 1.815 testes.

## Objetivo

Permitir revisar as propostas da Fase 41 no contexto da linha documental, com decisão
independente por campo, validação aritmética explícita e auditoria das linhas que atravessam
página — sem criar decisões humanas.

## Passos

1. **Corrigir a costura entre páginas** em `radar/vacancy_columns.py`:
   blocos de rótulo (gap 14 pt), exclusão do bloco da primeira linha, costura apenas da
   última linha e apenas quando a célula está incompleta, nota após `" - "` (fora do escopo),
   evidência localizada pelo rótulo bruto.
2. **Reparo de rótulo** `radar/label_repair.py` com guardas e evento auditável.
3. **Auditoria** `vacancy_columns.audit_schooling`: antes/depois por linha, páginas e
   continuação comprovada.
4. **Grupos** `radar/review_groups.py`: agrupamento por evidência, contexto, validação,
   resumo com denominadores distintos.
5. **Superfície**: rota `/api/revisao/grupos`, CLI `revisao-grupos` e `quadro-auditoria`,
   seção na Revisão humana com ações por campo.
6. **Testes** `tests/test_review_groups_f42.py`.
7. **Documentação e prova real**; revisão independente; commit e push.

## Critérios de aceite

- 381 linhas da SEDUC-PA com contexto; nenhuma linha agrupada por valor.
- 4 linhas de escolaridade incompleta resolvidas com continuação comprovada e páginas.
- Rótulos contaminado/truncado reparados, sem proposta nova e sem escopo fantasma.
- Decisão em um campo não altera os demais.
- Validação separa publicado/soma/diferença e não troca o total.
- Suíte verde; contrato v1 e schema inalterados; zero decisões criadas pela fase.

## Fora de escopo

- Aprovação em lote, confirmação automática, rateio de unificadas, nova tabela de grupos.

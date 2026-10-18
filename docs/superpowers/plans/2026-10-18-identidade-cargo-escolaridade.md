# Plano — Fase 39: identidade por código, escolaridade mínima e elegibilidade formal

Data: 2026-10-18. Base: `34bd380` (Fase 38), 1.702 testes, schema v21.

## Etapas

1. **Auditoria de partida** — diretório, branch, HEAD, remotes, sincronização, suíte, backup
   via API de backup, `integrity_check`, `foreign_key_check`, snapshot com fuso, inspeção de
   `role_identity`, requisitos, carteira e ciclo agendado.
2. **Diagnóstico dos pendentes** — 166 rótulos, causa por rótulo (decisão humana, duplicata,
   sem cargo canônico, só código), priorizando Quadrix 3049.
3. **Piloto Quadrix 3049** — quadro por código, localidade por linha, requisito por código,
   conferência contra o documento armazenado.
4. **Classificador** — nível educacional, cláusula de área, licenciatura, `nivel_minimo_sem_area`.
5. **Localidade** (`quadrix_tables.vaga_municipio`) — leitura após a linha validada, evidência
   da linha inteira, reprocessamento idempotente.
6. **Junção por código** — `_code_of`, `by_code`, guarda de ambiguidade, atribuição registrada.
7. **Elegibilidade** — novo estado `compativel_por_nivel_minimo`, precedência explícita,
   releitura a partir do texto, proteção de decisão humana e de aceitação explícita.
8. **Relatórios** — `pending_audit` (causa por rótulo) e `compatibility_review` (fichas).
9. **Superfície** — 2 rotas aditivas, 2 comandos CLI, colunas de código/localidade/requisito,
   painéis de pendências e de revisão.
10. **Testes** — `tests/test_eligibility_f39.py` (45), incluindo o piloto com sete códigos.
11. **Revisão independente**, correções, documentação, commit e push.

## Critérios de aceite

- 200–206: sete cargos distintos, cada um com código, município e vagas próprios, classificados
  como nível mínimo.
- 208: interpretação (curso técnico ≠ bacharelado). 407: categoria. 404: expresso.
- Nenhum cargo incompatível nos destaques, mesmo com vaga indígena.
- Licenciatura não vira nível mínimo.
- Nenhuma decisão humana criada; histórico preservado.
- Contrato `GET /api/concursos` v1 inalterado.
- Suíte verde; schema inalterado (v21).

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Fundir códigos por título-base | família é só leitura; testes de não-transferência |
| Localidade errada | linha validada por soma + evidência da linha inteira |
| Requisito de outro código | junção por código no mesmo concurso, com guarda |
| Licenciatura como nível mínimo | qualificadores explícitos + testes |
| Releitura sobrescrever decisão humana | `validado`/`corrigido` prevalecem |
| Reprocessamento duplicar | chave idempotente; evidência única por linha |

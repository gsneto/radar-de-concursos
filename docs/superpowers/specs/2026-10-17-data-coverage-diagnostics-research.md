# Pesquisa — Fase 25: cobertura, fontes e enriquecimento

Data: 2026-10-17. Pesquisa documental, de código e de licenças. Nenhum código de terceiros foi
copiado nesta fase.

## 1. Medir cobertura: bibliotecas de qualidade de dados

| Alternativa | O que oferece | Decisão |
|---|---|---|
| Great Expectations | suíte de expectativas, validação de dataframe | **Rejeitada**: dependência pesada, orientada a pipeline de dados, não a SQLite local |
| Soda Core | checks declarativos em YAML | **Rejeitada**: nova dependência e linguagem de config para 14 dimensões |
| dbt tests | testes em modelos SQL | **Rejeitada**: exigiria adotar dbt no projeto |
| SQL próprio + módulo Python | consultas determinísticas, sem dependência | **Adotada** |

O padrão útil importado das ferramentas acima é conceitual, não código: **denominador explícito
por expectativa** e **separação entre "não avaliado" e "falhou"**. Isso foi implementado em
`radar/data_quality.py` sem dependências.

## 2. Fontes oficiais adicionais (Frente C)

Auditoria das integrações reais em `ciclos_fontes` e no código:

| Fonte | Papel hoje | Resultado observado | Limitação |
|---|---|---|---|
| DOU (`in.gov.br`) | descoberta de atos | 2 ciclos, 20 docs, 10 novos | edições diárias misturam atos de vários órgãos; vínculo documento↔concurso é frágil |
| FGV (`conhecimento.fgv.br`) | descoberta + edital | 2 ciclos, 35 docs, 34 novos | cobertura só da própria banca |
| Quadrix (`quadrix.org.br`) | descoberta + anexos | 3 ciclos, 185 docs, 115 novos | anexos em CDN; exige autorização de host (já implementada) |
| PCI Concursos (MCP) | descoberta complementar | 3 ciclos, 477 docs | **agregador**: não é prova oficial; gera muitas páginas de notícia |
| Portal municipal (Guajará-Mirim) | fonte oficial específica | 4 ciclos, 0 docs | página sem estrutura estável |

Avaliação de candidatos levantados para expansão:

| Candidato | Viabilidade | Decisão nesta fase |
|---|---|---|
| Cebraspe | site com listas de concursos e editais em PDF; sem API pública | **Não integrar agora**: exigiria scraper frágil sem ganho comprovado antes de medir a lacuna de edital |
| IBFC | idem, HTML por concurso | **Não integrar agora** |
| Instituto AOCP | idem | **Não integrar agora** |
| FCC | idem | **Não integrar agora** |
| Portais estaduais | altamente heterogêneos | **Não integrar agora** |

Motivo declarado: a lacuna dominante é "não existe edital oficial localizado" (577 concursos), e
o gargalo imediato é **associar corretamente** os documentos que já chegam (594 `kind='outro'`,
incluindo 9 atos avulsos do DOU presos a um único concurso). Adicionar quatro scrapers de banca
antes de corrigir associação aumentaria volume sem aumentar confirmação — exatamente o que a
missão proíbe. A decisão fica registrada para a próxima fase, com a métrica que a justificaria:
`concursos_com_edital_oficial / concursos_com_oportunidade_ativa`.

Projetos open source de conectores avaliados: nenhum foi reaproveitado nesta fase porque a
melhoria implementada é de **diagnóstico e materialização de identidade**, não de coleta. Nenhuma
licença foi violada.

## 3. Reconciliação de cargo

Investigação do fluxo existente:

- `document_fields` marca linhas de tabela com `LABEL_PREFIX + rótulo` quando o documento é de
  escopo do concurso (`role_id IS NULL`) — comportamento correto e conservador.
- `document_review.reconcile_role_label` exige `reviewer` e `reason` e um `role_id` **já
  existente** no concurso. É decisão humana por desenho.
- `document_store.ensure_role` cria identidade a partir de `(contest_id, code)` ou
  `(contest_id, name, specialty)`, mas exige `observation_id` do fluxo de descoberta.
- `role_reconciliation.py` casa por **código** de cargo em página HTML — não cobre editais PDF.

Conclusão: faltava o elo entre "rótulo evidenciado no edital" e "identidade de cargo". Sem ele,
`cargos_identidade` fica vazio e o humano não tem alvo. A solução implementada cria a identidade
com o nome literal do rótulo, sem similaridade e sem tocar nas propostas.

Alternativa rejeitada: casar automaticamente por similaridade textual (`_similar` já existe em
`document_store`). Rejeitada porque a regra do domínio proíbe fundir cargos por semelhança, e
porque `PROFESSOR IV – MATEMÁTICA` e `PROFESSOR IV – LÍNGUA PORTUGUESA` colidiriam.

## 4. Diagnóstico de causa

Padrões considerados: árvore de decisão explícita (adotada), score probabilístico (rejeitado —
sem rótulos para treinar) e LLM para classificar causa (rejeitado — custo, não determinístico e
sem ganho sobre regras auditáveis para 8 causas discretas).

## 5. Referências consultadas

- Documentação de `sqlite3` (leitura consistente, `PRAGMA integrity_check`).
- Estrutura real das tabelas do schema v14 (`PRAGMA table_info`).
- Código do próprio projeto: `priority.py`, `ranking.py`, `document_fields.py`,
  `document_review.py`, `document_store.py`, `role_reconciliation.py`, `monitoring.py`.
- Conceitos de data quality (denominador explícito, estado "não avaliado" ≠ "falhou") de Great
  Expectations e Soda Core, usados como referência conceitual.

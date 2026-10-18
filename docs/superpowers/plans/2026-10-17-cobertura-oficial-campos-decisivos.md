# Plano — Fase 33: cobertura oficial, aquisição controlada e campos decisivos

Data: 2026-10-17. Base: `767ca31` (Fase 32), 1.434 testes, schema v18.

## Etapas

1. **Auditoria de partida** — branch/HEAD/remoto, suíte, backup consistente (WAL), integridade,
   contagens reais, catálogo de fontes e tarefas agendadas.
2. **Diagnóstico de cobertura** (`radar/coverage_states.py`)
   - 11 estados exclusivos por certame + próxima ação;
   - funil com `com_documento_qualquer` × `com_documento_oficial` × edital;
   - atribuição por fonte, fontes restritas, documentos sem identidade e nominais;
   - container fora do denominador.
3. **Conflitos de versão** (`radar/version_conflicts.py`)
   - retificação posterior, divergência no mesmo documento, escopo diferente, equivalência;
   - prazo só entre documentos autoritativos; local normalizado.
4. **Campos decisivos** (`radar/decisive_fields.py`)
   - indígenas (sem derivar de agregado), SI por cargo, prazos com vigente/anterior,
   - local de prova × lotação, `a_divulgar` e UF recuperada do trecho.
5. **Aquisição controlada** (`radar/acquisition.py`)
   - alvos, plano (dry-run), execução com orçamento, checkpoint e idempotência;
   - recusa de lista nominal por título;
   - recusa de fonte não habilitada / sem adaptador.
6. **Correções de extração** — travessão em local de prova, município com nome de estado,
   isenção confundida com inscrição.
7. **Superfície** — CLI `cobertura-estados`, `editais-faltantes`, `aquisicao-planejar`,
   `aquisicao-executar`, `campos-decisivos`, `conflitos-versao`, `documentos-nominais`;
   API `/api/cobertura/estados`, `/api/campos-decisivos`, `/api/conflitos`,
   `/api/editais-faltantes`; painel "Cobertura oficial e campos decisivos".
8. **Testes** — `tests/test_coverage_f33.py`, `tests/test_acquisition_f33.py`, ajustes em
   `test_location.py`, `test_document_extract_pdf.py`, `test_monitoring.py`, `test_ui.py`.
9. **Piloto real** — 2 certames FGV sem documento, 2 documentos cada, com análise; medir
   cobertura antes/depois e registrar o que veio do ciclo agendado.
10. **Revisão independente**, correções, documentação, commit e push.

## Critérios de aceite

- Cobertura oficial separada de agregador, com numerador/denominador e percentual.
- Nenhum total agregado vira vaga indígena; ausência de modalidade não é zero.
- SI agrupado por cargo (ou rótulo), sem contaminação entre cargos.
- Prazo de retificação não sobrescreve em silêncio; documento de resultado não compete.
- Lotação nunca vira local de prova.
- Aquisição só de fonte habilitada, só edital/retificação, com limite, simulação e checkpoint.
- Lista nominal não é baixada nem processada; já persistida fica visível para decisão humana.
- Suíte verde; contrato v1 intacto; base íntegra.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Inflar cobertura com agregador | Dois denominadores; agregador tem estado próprio |
| Baixar lista nominal por rótulo enganoso | Guarda por título + `documentos-nominais` |
| Aquisição sem limite | `max_contests`, `max_documents`, orçamento, checkpoint |
| Retificação tratada como valor absoluto | Conflito explícito com vigente/substituído |
| Falso conflito de local | Normalização município/UF e escopo `a_divulgar` |
| Alterar extração e quebrar dados antigos | Correções aditivas e testes de regressão |

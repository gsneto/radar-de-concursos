# Prova real — Fase 17: requisitos entre páginas

Data: 2026-10-16. Banco **temporário** isolado (`%TEMP%\f17*`). Downloads reais. Script:
`%TEMP%\opencode\proof16.py` (fluxo de produção: analisar → reconciliar por código e nome).

## Caso principal — 3056 (Sedes/DF), cabeçalho entre páginas

Documento: edital **`a806bfe7cabd…`**, 921.728 bytes, 61 páginas.

Causa comprovada: os subitens `2.3.3 Requisitos:` de várias seções caíam na página
seguinte ao cabeçalho `2.3 … (CARGO NNN)`.

| Métrica | Fase 16 | Fase 17 |
|---|---|---|
| cargos no HTML | 15 | 15 |
| cargos com `education` | **10** | **15** |
| propostas vinculadas (`role_id`) | 29 | **42** |

`by_code`: `assigned=42, created=15` — todos os 15 cargos oficiais. Exemplo de evidência
real: seção `2.3 … (CARGO 202)` com requisito na página seguinte, associado ao cargo 202.

## Regressão verificada — 3073 e 3057

| Certame | sha (12) | cargos HTML | antes | depois |
|---|---|---|---|---|
| 3073 (Valença) | `40f57dcb5ec0` | 10 | 10 cargos, 29 vinculadas | 10 cargos, **29 vinculadas** |
| 3057 (Cristalina) | `207f0fb0cd4d` | 30 | `explicita=12, ambigua=14` | `explicita=12, ambigua=14` |

- 3073: nenhuma regressão (a reconstrução entre páginas restaura as 29 associações).
- 3057: as 14 ambiguidades são **genuínas** (nomes de seção que correspondem a vários
  cargos com sufixo de localidade) e permanecem pendentes — não se propaga por escolaridade.

## Outros certames

3071 (12 cargos), 3070 (4) e 3055 (4) já eram integralmente cobertos por **código** —
a associação por seção não os altera.

## Integridade

- Escolaridade **não** é chave de identidade (o cabeçalho de nível não associa cargos).
- Vagas indígenas e prazos de isenção: extraídos no mesmo fluxo, sem interferência.
- Evidência sempre casa com o bloco: validação `block["text"][start:end] == quote`
  (0 divergências em 3056/3073/3057).

## Reprocessamento

`[idem] 3073: vinculadas 29→29 | recon repetida = 0 novas` — idempotente.

## Limitações

- Seção por nível/categoria sem cargo específico não é associada (não se usa escolaridade).
- 3057: 14 seções ambíguas (localidade) permanecem pendentes — conservador.
- A base habitual do usuário (`data/`) não existe; a prova usa banco temporário.

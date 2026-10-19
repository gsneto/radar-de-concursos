# Plano — Fase 43: piloto operacional de revisão da SEDUC-PA

Data: 2026-10-19. Base `7f758d9` (F42), schema v21, 1.833 testes.

## Objetivo

Preparar e validar uma revisão real de 10–20 linhas do Anexo II, com decisão independente
por campo, reconciliação assistida e proteção contra evidência obsoleta — sem criar decisões
humanas.

## Passos

1. **Piloto determinístico** (`radar/pilot.py`): `all_groups`, `select` com cotas de caso e
   diversidade, `report` com fichas, progresso e próxima linha, `available`, `prewarm`.
2. **Identidade assistida** (`radar/identity_suggestions.py`): 26 identidades para 381
   linhas, regional como dimensão, recomposição com vocabulário do edital, avisos.
3. **Histórico e consequências** em `review_groups`: últimas decisões por proposta e efeito
   de confirmar/rejeitar por campo.
4. **UI**: painel do piloto com progresso por decisão, próxima pendente, lista de fichas,
   abertura da linha, avisos de unificada, histórico, retomada por hash.
5. **Concorrência**: `ThreadingHTTPServer`; decisões continuam com `evidence_sha256` e
   `BEGIN IMMEDIATE`.
6. **Rotas/CLI**: `/api/revisao/pilotos`, `/api/revisao/piloto`, `/api/revisao/identidades`,
   `/api/revisao/grupos?linha=`; `piloto-revisao`, `pilotos`, `identidades-sugeridas`,
   `revisao-prewarm`.
7. **Testes** `tests/test_pilot_f43.py` (34) e extensão do harness Node.
8. **Validação real da UI** no Chromium: abrir, decidir, bloquear evidência obsoleta,
   recarregar e retomar.
9. **Documentação, revisão independente, commit e push.**

## Critérios de aceite

- Piloto estável, 16 linhas, casos PI/PPIQ/PI-PQ/zero/multipágina, ≥5 regionais, ≥3 cargos.
- 381 linhas → 26 identidades → 24 regionais; soma das linhas = 381.
- Confirmar um campo não altera os demais; identidade só muda por decisão própria.
- Evidência alterada é bloqueada com motivo.
- Abrir linha não cria decisão; progresso só conta decisão registrada.
- Suíte verde; contrato v1 e schema inalterados; base real com 0 decisões.

## Fora de escopo

- Aprovação em lote, rateio de unificadas, nova tabela de piloto, coleta externa.

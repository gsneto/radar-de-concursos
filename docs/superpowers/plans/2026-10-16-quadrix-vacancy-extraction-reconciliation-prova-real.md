# Prova real — Fase 13: extração Quadrix e reconciliação multifonte

Data: 2026-10-16. Bancos **temporários** isolados (`%TEMP%\f13A-*`, `%TEMP%\f13B-*`);
a base habitual do usuário não é tocada. Downloads reais. Script: `%TEMP%\opencode\proof13.py`.

## Prova A — extração de vagas dos editais da Quadrix (Frente A)

Editais reais baixados, analisados por `_analyze_version` (extrator + estratégia Quadrix):

| Certame | documento | sha256 (12) | bytes | páginas | cargos | imediatas (faixa) | reserva (faixa) | indígenas |
|---|---|---|---|---|---|---|---|---|
| 3049 (CRECI-ES) | edital_abertura | `58d6fde13390` | 795.700 | 43 | 22 | 0–6 | 30–74 | coluna PI, **0** |
| 3052 | edital_abertura | `4549b5a3e38e` | 743.673 | 41 | 10 | 0–1 | 30–39 | coluna PI, **0** |
| 3072 (CAU-AP) | edital_abertura | `d88787db1e34` | 694.277 | 35 | 3 | 0–1 | 49–50 | coluna PI, **0** |
| 3056 (Sedes/DF) | edital_retificado | `a806bfe7cabd` | 921.728 | 61 | 14 | 3–133 | 9–399 | sem coluna |

- **Cargos e códigos** identificados (ex.: `200 Profissional de Suporte Técnico…`,
  `206 Analista de Sistemas`), com a linha completa como **evidência** (offset exato no
  bloco/página) e o código preservado no rótulo.
- **Propostas** por cargo: `immediate_vacancies`, `reserve_vacancies` e, quando há coluna,
  `indigenous_vacancies`. Nada validado automaticamente (motivo de ambiguidade =
  "cargo do documento não reconciliado").
- **Idempotência:** reanalisar a mesma versão é recusado ("versão já analisada");
  propostas 133 → 133.
- **Métricas por fonte:** `Instituto Quadrix` — 4 documentos, 4 recuperados, 4 processados,
  **133 propostas** (antes da Fase 13: 0).

### Varredura de 12 editais Quadrix (vagas indígenas)

A coluna indígena (`PI`) existe em 8 dos 12 editais analisados, mas **o valor imediato é 0
em todos os cargos**; a reserva indígena aparece no **cadastro de reserva**. Zero é "zero
confirmado" (coluna presente), não campo ausente. Nenhum cargo com vaga indígena imediata
> 0 foi encontrado na amostra.

## Prova B — reconciliação multifonte (PCI ↔ Quadrix/FGV/DOU)

- PCI real: 4/4 consultas OK, **477** concursos únicos; amostra de **40** candidatos.
- Fila: 40 enfileirados; reconciliação prévia `novo=40`.
- Lote real (resolvers FGV+Quadrix+DOU), 40 processados em ~86s:
  `inconclusivo=13`, `nao_localizado=26`, `fonte_oficial_localizada=1`.
- **14 itens** com referência oficial: 12 Quadrix (páginas/edital), 2 FGV, 1 DOU. Ex.:
  `pci-295024 → https://www.quadrix.org.br/informacoes/2214/` (`fonte_oficial_localizada`).
- **Prioridades (top):** score 25, sinais `inscricoes_abertas_pci, prazo_proximo_pci,
  referencia_pronta` — explicáveis.
- **Idempotência:** reconciliação repetida → mesmos números.

## Limitações

- A maioria dos candidatos Quadrix casou de forma **ambígua** (títulos repetidos no
  catálogo da banca) e ficou `inconclusivo` — comportamento conservador correto (não se
  adivinha o certame); por isso `documentos recuperados=0` **neste lote de reconciliação**
  (a recuperação documental já foi provada na Prova A e na Fase 12).
- A descoberta PCI é nacional; os conectores oficiais cobrem federal (DOU) e as bancas
  FGV/Quadrix. Sem base habitual, as métricas valem para a amostra, não para cobertura
  nacional.

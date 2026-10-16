# Prova real — fila de confirmação documental (Fase 11)

Data da execução: 2026-10-16. Banco **temporário** isolado (`%TEMP%\conf11-*`); a base
habitual do usuário não é tocada.

## Situação da base

A base habitual (`data/`) não existe; não há dados v1 nem candidatos nela. Os 477
candidatos da Fase 10 estão apenas nos bancos temporários de prova. A fila foi
exercitada sobre candidatos PCI **reais** coletados no momento da prova.

## Amostra e reconciliação

- Coleta PCI real: 4/4 consultas OK, **556** resultados observados, **477** únicos;
  amostra de **150** candidatos persistidos e enfileirados.
- Reconciliação multifonte (contra outras fontes presentes na base): `novo=150`,
  `coincidente=0`, `ambíguo=0`, `sem_dados=0`. (Não havia dados de DOU/FGV/v1 na base
  isolada; em uso real a mesma comparação mede sobreposição.)

## Processamento em lotes (referências oficiais reais)

3 lotes de 50 processados (o 4º retorna 0 — nada pendente):

| Lote | Processados | Estado |
|---|---|---|
| 1 | 50 | nao_localizado=48, inconclusivo=2 |
| 2 | 50 | nao_localizado=48, documento_processado=1, inconclusivo=1 |
| 3 | 50 | nao_localizado=45, documento_processado=1, inconclusivo=4 |
| 4 | 0 | — |

Resultado acumulado (150): **nao_localizado=141**, **inconclusivo=7**,
**documento_processado=2**.

## Documentos oficiais registrados (reais)

| Concurso (PCI) | Fonte oficial | URL | sha256 | bytes |
|---|---|---|---|---|
| pci-294824 (SEPLAG/RJ) | FGV Conhecimento | `https://conhecimento.fgv.br/concursos/seplagrj` | `c69007a67fd7…` | 38.113 |
| pci-295588 (CBMERJ) | FGV Conhecimento | `https://conhecimento.fgv.br/concursos/cbmerj22` | `86ac1f0887cf…` | 40.836 |

Extraídos como `outro` (página oficial do concurso na FGV), `extraction_state=parcial`,
com versão imutável e hash. Nenhuma proposta foi criada (a página não traz quadro de
vagas) e **nada** foi validado automaticamente (`revisoes=0`, `valores_atuais=0`).

## Referências oficiais encontradas (9 itens)

- **2** com documento registrado (acima).
- **7** marcadas `inconclusivo` (referência ambígua, para revisão): 5 páginas FGV com
  coincidência parcial de título (`cgmrj23`, `trt13`, `mpsp`, `seplagrj`, `pmespcabo22`)
  e 2 matérias do DOU casando por órgão.

## Idempotência e resumo

- Lote repetido após a conclusão: **processed=0** (concluídos não são reprocessados).
- Fila final: `pendente=0`, `documento_processado=2`, `inconclusivo=7`,
  `nao_localizado=141`.
- Tabela v1 `concursos` **ausente** (a confirmação não escreve o contrato v1).

## Limitações observadas

- A maioria dos candidatos é **municipal**, ausente do DOU (federal) e do catálogo FGV;
  por isso 141/150 ficaram `nao_localizado`. Isso é o resultado **honesto** — a fonte
  de descoberta (PCI) é nacional, mas os conectores de confirmação atuais cobrem
  federal (DOU) e uma banca (FGV).
- O DOU frequentemente casa por órgão com publicações que **não** são o edital do
  concurso; por isso os casamentos parciais ficam `inconclusivo` (nunca `confirmado`).
- O FGV fornece a **página do concurso** (que lista os arquivos), não o edital direto;
  a extração de vagas exigiria seguir os anexos (trabalho futuro).

## Reprodução

Script: `%TEMP%\opencode\proof11.py` (fora do repositório). Testes automatizados (sem
rede): `tests/test_confirmation.py`, `tests/test_official_resolvers.py`,
`tests/test_confirmation_api.py`.

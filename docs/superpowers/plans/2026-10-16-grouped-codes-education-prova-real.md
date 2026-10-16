# Prova real — Fase 15: códigos agrupados, multibanca e elegibilidade

Data: 2026-10-16. Banco **temporário** isolado (`%TEMP%\f15p-*`). Downloads reais.
Script: `%TEMP%\opencode\proof15.py`.

## Frente A — código agrupado (CRECI-ES / Quadrix 3049)

Edital `edital_abertura`, **sha256 `58d6fde13390…`**, 795.700 bytes, 43 páginas.
Página HTML oficial: `https://www.quadrix.org.br/informacoes/3049/` (22 cargos).

| Antes (Fase 14) | Depois (Fase 15) |
|---|---|
| `education` para **8** cargos | `education` para **22/22** cargos |

Blocos agrupados reais reconhecidos: `(CÓDIGOS 200 ATÉ 206)` e `(CÓDIGOS 400 ATÉ 406)`.
Cada cargo do bloco recebeu a **mesma evidência**, cujo `quote` inclui o literal
`CÓDIGOS 400 ATÉ 406) a) Requisitos: …`.

Reconciliação por código: `assigned=147, created=22, reused=125, ambiguous=0, pending=0,
missing_codes=[]` (todos os códigos das faixas existem no HTML oficial).

### Compatibilidade com Sistemas de Informação (3049)

| Código | Cargo | `si_compatibility` |
|---|---|---|
| 208 | PST-Assistente de T.I. | **abrangido_por_categoria** |
| 407 | PAS-Analista de T.I. | **abrangido_por_categoria** |
| 400–406 | PAS-Agente Fiscal | incompativel_com_requisito_explicito (exige Direito etc.) |
| 408–412 | PAS-Especialista | incompativel_com_requisito_explicito |
| 200–207 | PST-Assistente | ambiguo (nível médio, sem área de computação) |

Reprocessamento: propostas 152 → 152; reanálise recusada ("versão já analisada") — idempotente.

## Frente B — multibanca (FGV Conhecimento)

Edital real (tjap26), 74 páginas.

| Estratégia | Resultado |
|---|---|
| Anexo II por cargo (`extract_education`) | 0 (o edital não usa esse formato) |
| Rótulo declarado (`extract_declared_education`) | 1: `education = "Nível Superior – Direito"`, `si_compatibility = incompativel_com_requisito_explicito` |

Mostra o **pipeline comum** aplicado a outro formato, sem regra específica de banca: o
complemento por rótulo cobre a declaração explícita de escolaridade.

## Limitações

- Faixas são expandidas só com marcador explícito e amplitude plausível.
- O complemento por rótulo exige rótulo explícito e palavra de nível; requisitos em
  tabelas com cabeçalhos intercalados podem exigir revisão.
- A base habitual do usuário (`data/`) não existe; a prova usa banco temporário.

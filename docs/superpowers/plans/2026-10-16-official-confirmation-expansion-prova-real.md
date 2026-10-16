# Prova real — Fase 12: fonte oficial Quadrix e documentos completos da FGV

Data: 2026-10-16. Banco **temporário** isolado (`%TEMP%\f12A-*`, `%TEMP%\f12B-*`); a base
habitual do usuário não é tocada. Downloads reais pela rede. Script:
`%TEMP%\opencode\proof12.py`.

## Prova A — nova fonte oficial (Quadrix)

| Passo | Resultado observado |
|---|---|
| Catálogo real (`/index/abertos/?pp=1000`) | 16 certames; união abertos+em andamento+em breve = 27 entradas |
| Descoberta (`discover`, 2 detalhes) | 29 candidatos; páginas + documentos registrados com proveniência |
| Certame focado | **3056 — Secretaria de Desenvolvimento Social do DF (Sedes/DF)** — 25 documentos |
| Tipos classificados | comunicado 4, resultado 7, gabarito 4, retificação 3, cronograma 1, convocação 1, homologação 3, edital_retificado 1, outro 1 |
| Documentos de escopo baixados | 4 (1 edital + 3 retificações), com hash e tamanho reais |

Documentos recuperados (host público `anexos-r2.selecao.net.br`):

| Tipo | sha256 (12) | bytes |
|---|---|---|
| edital_retificado | `a806bfe7cabd` | 921.728 |
| retificacao | `d6a6117c709d` | 312.301 |
| retificacao | `a571b7580ffd` | 212.369 |
| retificacao | `1dc419d0d9ff` | 215.367 |

- **Extração:** os editais do Quadrix geram blocos (43–61), mas **0 propostas** de vagas —
  o layout do quadro de vagas dessa banca ainda não é reconhecido pelo extrator (Fase 8).
  Registrado como **limitação**, não como sucesso.
- **Reexecução:** 0 candidatos novos; versões 4→4 (rebaixar o mesmo edital não duplica).
- **Propostas/valores:** 0 propostas, **0 revisões** — nada auto-validado.

## Prova B — seguir links documentais da FGV

| Passo | Resultado observado |
|---|---|
| Catálogo FGV | 31 certames |
| Descoberta (`max_new_details=5`) | 20 candidatos registrados |
| Certame focado | **tjap26 — TJAP Juiz de Direito Substituto** — status "Em Andamento" |
| Documentos de escopo baixados | 2 (edital retificado + 1ª retificação) |

| Tipo | sha256 (12) | bytes |
|---|---|---|
| edital_retificado | `b8faf5646486` | 912.420 |
| retificacao | `872b49327950` | 257.783 |

- **Extração:** o edital retificado do TJAP gerou **14 propostas** de campos (com evidência),
  **0 revisões** — pendentes de revisão humana.
- **Reexecução com revisão incremental ativa** (`max_refresh_details=2`): 4 candidatos
  reemitidos, **0 URLs novas** — o histórico é preservado e a idempotência por URL evita
  versões/baixas repetidas.

## Métricas (banco de prova)

- Prova A: `documents_found=29`, `documents_recovered=5`, `editais=2`, `retificacoes=4`,
  `propostas=0`.
- Prova B: `documents_found=20`, `documents_recovered=2`, `editais=4`, `retificacoes=5`,
  `propostas=14`.

## Limitações explícitas

- **Cebraspe não integrado:** dados só via API interna não documentada
  (`apis.cebraspe.org.br/...`) ou navegador JS — proibido/insustentável no laço Python.
- **Vunesp/AOCP/Consulplan/IBFC:** 403 (acesso automatizado bloqueado); não contornado.
- **Cesgranrio/IDECAN:** documentos não públicos (portal/login ou 403).
- **Quadrix:** a extração de vagas ainda não reconhece o layout do quadro de vagas dessa
  banca (0 propostas); a recuperação e a classificação documental funcionam.
- Muitos certames do Quadrix recentes ainda não publicaram arquivos (página "em breve"),
  resultando em 0 documentos — comportamento correto, não falha.

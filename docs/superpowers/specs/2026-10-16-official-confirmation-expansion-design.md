# Fase 12 — Expansão da confirmação oficial, nova fonte e documentos completos da FGV

Data: 2026-10-16. Base: `c78d8eb` (Fase 11), 368 testes OK.

## Problema

A descoberta (PCI) é nacional, mas a confirmação oficial cobria apenas o DOU
(federal) e a FGV. Isso deixava a maioria dos candidatos em `nao_localizado`. A
Fase 12 amplia as fontes oficiais e passa a recuperar **documentos completos**
(edital, anexo, retificação) a partir das páginas oficiais, alimentando a extração
de vagas já existente.

## Frente A — escolha da nova fonte oficial

Investigação real (2026-10-16), com requisições HTTP normais (User-Agent de
navegador) e navegador para páginas JS:

| Fonte | Acesso observado | Páginas de certame | Documentos públicos | Veredito |
|---|---|---|---|---|
| **Cebraspe** | SPA Angular (`<base href="/concursos/">`); shell idêntico em todas as rotas | Sim, renderizadas por JS | Sim, PDFs em `cdn.cebraspe.org.br/.../arquivos/<HASH>.pdf`, mas só descobertos via a **API interna não documentada** `apis.cebraspe.org.br/cebraspe/eventos/<slug>` (sem swagger; raiz 403) ou via navegador | **Não integrar** |
| Vunesp | HTTP **403** | — | — | Não |
| AOCP | HTTP **403** | — | — | Não |
| Consulplan | HTTP **403** | — | — | Não |
| IBFC | HTTP **403** | — | — | Não |
| IDECAN | Lista `concurso.idecan.org.br` 200, mas páginas de certame **403** | — | — | Não |
| Cesgranrio | WordPress 200; páginas `/concurso/<slug>/` server-rendered com metadados (vagas, salários, provas) | Sim | **Não** no HTML público (documentos atrás de `concursos.cesgranrio.org.br/portal/login`) | Não |
| FCC / FUNDATEC / Legalle | 200, mas sem links de edital nas páginas públicas | Parcial | Não | Não |
| **Quadrix** | HTML server-rendered; lista em `/`, `/index/<status>/`; páginas `/informacoes/<id>/` | Sim | **Sim**, PDFs/ZIP públicos em `anexos-r2.selecao.net.br/uploads/<org>/concursos/<id>/anexos/<uuid>.(pdf|zip)` | **Integrar** |

### Regras respeitadas na decisão

- **Cebraspe não é integrado** porque os dados só são alcançáveis por (a) uma API
  interna **não documentada** — proibida como atalho — ou (b) navegador JS, que não é
  sustentável no laço de monitoramento Python do Radar (sem dependência de navegador
  no pacote). Decisão documentada; a limitação é registrada.
- Vunesp/AOCP/Consulplan/IBFC bloqueiam acesso automatizado (403): não se contorna.
- Cesgranrio/IDECAN: documentos não públicos.
- **Quadrix** atende: oficialidade (banca organizadora), HTML server-rendered,
  páginas individuais por certame, editais/anexos/retificações públicos, ids estáveis
  (`/informacoes/<id>`), monitoramento incremental, custo baixo, evidências rastreáveis.
- `robots.txt` do Quadrix (`www.quadrix.org.br`): `Disallow: /admin/*`, `/painel/*`,
  `/uploads/*` (só no host do site). Os anexos são servidos pelo host separado
  `anexos-r2.selecao.net.br`, cujo `robots.txt` responde **404** (sem regras). A
  allowlist do Radar autoriza **apenas** o CDN de anexos, com prefixo de caminho
  restrito — nunca o host do site em `/uploads/`.

## Frente B — seguir links documentais da FGV

O conector FGV (Fase 9) só consultava a página de detalhe de **concursos novos**; por
isso retificações e anexos publicados **depois** da primeira visita nunca eram vistos.
A Fase 12 adiciona **revisão incremental de concursos conhecidos**: um orçamento
(`max_refresh_details`) reconsulta as páginas conhecidas mais antigas por
`last_checked_at`, emite os candidatos documentais e deixa a **idempotência por URL**
descartar os já registrados — só documentos novos viram versão. Nada é apagado.

## Classificação documental

O bucket de armazenamento `kind` permanece `edital`/`retificacao`/`outro`
(compatível). Adiciona-se a coluna **aditiva** `documentos.tipo_documental`
(migração **v6**, `ALTER TABLE ... ADD COLUMN`) com a classificação fina:
`edital_abertura`, `edital_retificado`, `retificacao`, `anexo`, `cronograma`,
`comunicado`, `resultado`, `convocacao`, `homologacao`, `gabarito`, `prova`, `outro`.

Regras de classificação (por evidência do título):
- "retifica" no início, ou "retifica" sem "edital" → `retificacao`.
- "edital" + "atualizado"/"retificado"/"consolidado" → `edital_retificado`.
- "edital" puro → `edital_abertura`.
- demais palavras-chave (anexo, cronograma, comunicado, resultado, convoca, homolog,
  gabarito, prova) → tipo correspondente; senão `outro`.
- **Nunca** classificar todo PDF como edital; "Convocações-provas", "Gabarito" e
  "Resultado" não são edital.

## Métricas de efetividade

Função pura `confirmation.metrics(db_path)` (e CLI `confirmacao-metricas`) que separa:
selecionados, páginas oficiais localizadas, documentos encontrados, recuperados,
editais processados, anexos, retificações, propostas, pendentes, falhas, ambíguos,
novos vs. conhecidos-com-documentos. Uma página e um PDF **não** são duas
oportunidades; propostas **não** são valores validados.

## Compatibilidade

- API v1 (`GET /api/concursos`, 18 campos) **inalterada**.
- Nada é promovido a validado sem revisão humana.
- Fila da Fase 11 reutilizada; novos estados não introduzidos (usa os existentes).

# Prova real — terceira fonte (FGV Conhecimento)

Data da execução: 2026-10-16. Banco **temporário** isolado (`%TEMP%\fgv9-*`); a base
habitual do usuário não é tocada.

## Fonte e método

- Catálogo: `https://conhecimento.fgv.br/concursos` (HTTP 200, HTML server-rendered).
- Páginas individuais: `https://conhecimento.fgv.br/concursos/<slug>`.
- Documentos: `https://conhecimento.fgv.br/sites/default/files/concursos/*.pdf`.
- Acesso: leitura pública, User-Agent de navegador, HTTPS, limite de 4 MB por página.
  Nenhuma área autenticada. `robots.txt` não proíbe `/concursos` nem
  `/sites/default/files/concursos/`.

## Resultado observado

| Item | Valor |
|---|---|
| Catálogo (page 0) | 51.464 bytes em ~5 s; **31 entradas** |
| Ciclo 1 (monitoramento) | state=`concluido`; `documents_new=3`; `versions_new=3`; ~24 s |
| Edital baixado | `edital-n-33-2026-edital-de-abertura.pdf` — 895.243 bytes, `sha256 85bd7cfe4818…` |
| Propostas extraídas do edital | **10** (extração `parcial`), `revisões=0` (nada auto-validado) |
| Páginas de concurso registradas | 2 (kind `outro`, conteúdo embutido; marcam "detalhe consultado") |
| Idempotência | redescobrir → **0 candidatos**; concursos conhecidos não re-consultados; **0 URLs duplicadas** |
| v1 | tabela `concursos` **ausente** (a FGV não escreve no contrato v1) |

### Certame com edital + retificação (`tjap26`)

- Página: `https://conhecimento.fgv.br/concursos/tjap26` (status "Em Andamento").
- Documentos associados ao mesmo concurso (2 documentos, 2 versões):
  - **Retificação**: `1ª Retificação` — `retificacao-tjap_.pdf`, 257.783 bytes, `sha256 872b49327950…`.
  - **Edital** (retificado): `tjap.versao-final.13.10.pdf`, 912.420 bytes, `sha256 b8faf5646486…`.
- A classificação distingue **edital** de **retificação** (um edital apenas "retificado"
  continua sendo edital); o vínculo retificação↔concurso usa a mesma página/identidade
  do certame, sem fundir com outros.

## Identidade e deduplicação

- Cada concurso tem identidade própria: `competition_id` = slug (ex.: `tjap26`),
  `source_url` = página individual. Nenhum concurso é fundido por semelhança de título.
- Reexecutar a descoberta não re-consulta detalhes de concursos conhecidos nem cria
  documentos/versões duplicados.

## Limites observados

- O ciclo de descoberta é **incremental**: cada execução consulta o detalhe de poucos
  concursos novos (limite por ciclo), cobrindo o catálogo ao longo de vários ciclos.
- Alguns PDFs podem falhar por instabilidade do servidor (conexão encerrada) ou por
  validação de rede; a falha é registrada sem apagar o histórico (estado `parcial`).
- O catálogo lista certames antigos/encerrados; o estado vem da fonte e não é
  tratado como cancelamento/abertura sem documento.
- PDF digitalizado (sem texto) permanece não extraível.

## Reprodução

Script: `%TEMP%\opencode\proof9.py` (fora do repositório). Testes automatizados
equivalentes (sem rede): `tests/test_fgv_source.py`.

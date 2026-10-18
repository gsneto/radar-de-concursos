# Pesquisa — Fase 33: cobertura oficial e campos decisivos

Data da consulta: 2026-10-17. Objetivo: decidir **o que adotar** para descobrir editais
oficiais, reconciliar identidade e extrair os quatro campos decisivos, sem ampliar dependências
nem violar a política de fontes do projeto.

## Critérios de seleção

1. Extração **determinística** e auditável (nada de "a IA entendeu"), porque cada valor precisa
   de trecho, página e versão.
2. Licença compatível com uso local e **sem** confundir licença do código com direito de
   redistribuir conteúdo de terceiros.
3. Sem conta, assinatura, crédito pago ou dependência de serviço hospedado.
4. Capacidade de dizer "não encontrado" em vez de inventar valor.
5. Compatível com o modelo existente (documento → versão → bloco → evidência → proposta).

## Soluções examinadas

| Solução | O que faz | Decisão | Por quê |
|---|---|---|---|
| `joaosbp/edital-extractor-br` (Apify Actor) — <https://apify.com/joaosbp/edital-extractor-br> | Extrai órgão, vagas, taxas, inscrição e data da prova de PDFs FCC/Cebraspe/FGV; determinístico, sem IA; rejeita escaneado | **Não adotado** | Serviço hospedado e pago (≈US$ 0,001/edital) e *input-driven* (não descobre). Exigiria pagamento e envio de documentos a terceiro. O desenho, porém, **valida** a escolha do projeto: determinístico, `null` quando não acha, cobertura declarada. |
| `devFelipeLongo/concursohub` — <https://github.com/devFelipeLongo/concursohub> | Gem Ruby que raspa o PCI Concursos e devolve PDFs/blocos | **Não adotado** | Fonte é agregador; o projeto usa PCI apenas como **pista de descoberta** (metadado), nunca como conteúdo persistido. Além disso é Ruby, fora da stack. |
| `JoaoSantanaLopes/alerta-concursos` — <https://github.com/JoaoSantanaLopes/alerta-concursos> | Scraper PCI + notificação + resumo por IA (Gemini/Ollama) | **Não adotado** | MIT no código, mas resumo por IA não é evidência citável e a fonte é agregador. |
| `simiao-cavalcante/edital-verticalizado` — <https://github.com/simiao-cavalcante/edital-verticalizado> | Skill que converte edital em plano de estudo (Excel/HTML/DOCX) | **Não adotado** | Resolve outro problema (verticalização para estudo); a extração é heurística e não produz proveniência por página. Útil como referência de separação "extrair uma vez → gerar". |
| `luiz-eduardo-gs/estrategia-concursos-downloader` — <https://github.com/luiz-eduardo-gs/estrategia-concursos-downloader> | Baixa PDFs de curso comercial via API | **Não adotado** | Conteúdo editorial de terceiro e API autenticada; fora do escopo e da política. |

## Robots e condições de acesso

- `https://conhecimento.fgv.br/robots.txt` consultado em 2026-10-17: `Allow` para CSS/JS/imagens;
  `Disallow` para `/admin/`, `/user/`, `/search/`, `/sites/README.txt` etc. **`/concursos/` e
  `/sites/default/files/concursos/` não estão bloqueados**. É a base da aquisição controlada da
  Fase 33.
- `anexos.cdn.selecao.net.br/robots.txt` (`Disallow: /`) continua respeitado: metadado apenas,
  salvo autorização explícita já existente (Fase 29). Nada mudou nesta fase.

## Conclusões que viraram implementação

1. **Não instalar nem contratar extrator externo.** O extrator textual existente + parser
   determinístico cobriu o quadro multipágina (Fase 32) e os quatro campos; o que faltava era
   **cobertura** e **diagnóstico**, não mais uma biblioteca.
2. **Cobertura oficial é denominador, não vaidade.** Página de agregador não conta como
   documento oficial. O funil passa a mostrar 5,7% → 6,5% de documento oficial, e não os 85%
   que contavam notícia de agregador.
3. **Aquisição é do documento que muda regra.** Edital/retificação; lista nominal (nomes, notas,
   inscritos) não é adquirida nem processada, mesmo quando a banca a rotula "Retificação".
4. **Retificação não sobrescreve em silêncio.** O valor mais recente é candidato; o anterior fica
   registrado como substituído e o conflito vai para revisão.
5. **Local de prova ≠ lotação.** A resolução usa apenas evidência do campo de prova; município de
   lotação nunca é promovido.

## Limitações da pesquisa

- Não foi possível avaliar precisão comparada dos extratores externos (o Actor é pago e não foi
  executado). A conclusão de não adotar é por **restrição de política/custo**, não por medição de
  qualidade.
- Não há benchmark público de extração de editais brasileiros; a avaliação é feita sobre a base
  real do projeto (documentos, páginas e trechos).

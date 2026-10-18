# Pesquisa — Fase 37: reconciliação de prazos, contagens e decisão assistida

Data da consulta: **2026-10-18**. Objetivo: resolver os problemas reais da fase (causa de
conflito, contagens que fecham, comparação de trechos) sem adicionar dependência.

## 1. Reconciliação de datas extraídas de documentos

Abordagens examinadas:

- **Normalização por expressão regular com âncora de campo** (o que o projeto já usa). Limite
  conhecido: um padrão genérico de período ("dia X … dia Y") aparece em inscrição, isenção e
  cronograma de provas. Sem contexto, a data é atribuída ao campo errado.
- **Classificação por contexto local** (janela/orção anterior). É o que foi adotado: barato,
  determinístico, auditável e sem modelo estatístico. Falha de forma conservadora (não
  atribui) quando o contexto é ambíguo.
- **Modelos de extração de datas (NLP)**. Descartados: exigiriam dependência pesada, não
  resolvem o problema de **escopo do evento** (o texto é o mesmo) e reduzem a
  reprodutibilidade exigida pela auditoria.

Decisão: manter regex + contexto, com a classificação de evento compartilhada entre extrator e
auditoria (fonte única), para que os dois nunca discordem.

## 2. Comparação de versões de editais e retificações

Referência conceitual: o projeto já guarda `documento → versão (sha256) → bloco → evidência`.
A comparação desta fase não é textual: é **de candidatos**. Cada proposta traz documento,
versão, página, offsets e hash; a auditoria pergunta se o extrator atual reproduz o par
(campo, valor) naquele bloco.

Alternativa descartada: diff textual de PDFs (como fazem ferramentas de change detection).
Não responde "este valor ainda é extraível?" e produz ruído de formatação.

## 3. Auditoria de campos derivados e contagens mutuamente exclusivas

Padrão adotado: **dimensões independentes, cada uma exclusiva e somando o denominador**, com
um bloco de denominador explícito (unidade, universo, filtros, referência). É o mesmo
princípio de relatórios de qualidade de dados (contagem por estado + total), mas implementado
em SQL/Python puro.

Erro corrigido: um estado derivado (`revalidado_na_fonte`) competindo com estados temporais
(`futuro`, `expirado`). A soma parecia não fechar porque o relatório misturou o recorte dos 16
futuros com o universo de 110.

## 4. Processamento de datas e fusos

Mantido `zoneinfo` com `America/Recife` (disponível no ambiente; fallback UTC-3). Regra
reforçada: a data de referência é a local, não a UTC, e a data de coleta nunca é usada como
data de publicação.

## 5. Revisão humana assistida por evidências

Padrão adotado: **ficha de decisão** com (a) todos os candidatos, (b) trecho + contexto,
(c) documento/versão/página/hash/URL, (d) classificação automática da causa, (e) proposta de
correção explicitamente não executada. A decisão continua no fluxo append-only existente
(`review.decide_proposal`), sem tabela paralela.

## 6. Entity resolution e correspondência de cargos

Já resolvido na Fase 35 (`role_identity`), com pontuação estrutural e decisão humana. Esta
fase não altera o mecanismo; apenas garante que a auditoria de prazo não misture escopos de
cargo ao agrupar candidatos (`role_scope`).

## 7. Linhagem documental e histórico de decisões

Mantido o modelo local (documento → versão → evidência → proposta → decisão). A verificação de
documento registra `quem/quando/resultado/hashes` em tabela append-only, sem conteúdo — o
equivalente mínimo do que PROV e OpenLineage descrevem, sem RDF nem barramento de eventos.

## 8. Testes de regressão para relatórios agregados

Padrão adotado: para cada dimensão, afirmar que a soma é igual ao total; para cada item,
afirmar que as dimensões são as esperadas; e reproduzir o caso real (três eventos no mesmo
bloco) como fixture. Isso transforma o erro de contagem em teste, não em revisão manual.

## 9. Fontes e políticas

Nenhuma fonte nova. A verificação usa o catálogo da Fase 29 (`fgv-conhecimento`,
`quadrix`), com `persistencia_permitida` para documento, mesma política e mesmo limite de
tamanho. Nenhuma consulta paga, nenhum crédito, nenhuma coleta massiva.

## 10. O que foi rejeitado

- Biblioteca de NLP para datas: dependência desproporcional e menos auditável.
- Diff textual de PDF: não responde à pergunta da auditoria.
- Escolher o valor mais recente/mais frequente: viola a regra de não decidir por recência.
- Reextrair todos os documentos automaticamente: criaria propostas novas sem decisão humana e
  mudaria a base sem necessidade.

# Pesquisa — Fase 28: revisão humana, priorização e recuperação documental

Data: 2026-10-17. Nenhum código de terceiros foi copiado nesta fase.

## 1. Filas de revisão e decisão auditável

| Referência | O que foi observado | O que foi adotado | O que foi rejeitado |
|---|---|---|---|
| **Talonic — Review Queue / Approval Queue** (documentação do produto) | fila como *consulta* sobre o estado dos campos, não tabela separada; decisão gera célula de promoção + linha append-only no log; `approve` / `correct` / `override`; decisão revisável escreve nova linha e mantém a anterior; triage e *value clusters* | fila derivada do estado real; log append-only com estado anterior; correção como decisão própria; idempotência | *bulk resolve* (aprovação em massa) — proibido nesta fase; tabela de fila própria (drift) |
| **NORA / AKKO** (documentação) | steward aceita, edita, mescla ou rejeita proposta; auditoria com identidade, proposta original e valor aceito; *rollback* pelo log | separação entre proposta e valor aceito; auditoria com origem | fluxo de aprovação em massa e integração com catálogo externo |
| **Ratify** (open source) | proposta → classificação → aprovação → *audit trail* imutável | “proposta não é mudança” e log imutável | dependência/workflow de contratos de dados |
| **SODPUB** (open source, BPMN/PROV-O) | *human review gateway*: inspecionar, aprovar/rejeitar, justificar, gerar proveniência | justificativa obrigatória e proveniência da decisão | Camunda/PostgreSQL/RDF: peso incompatível |

Conclusão: os padrões úteis são (a) fila derivada do estado, (b) decisão append-only com estado
anterior, (c) correção como decisão explícita, (d) proveniência da decisão. Nenhum framework foi
adotado: a implementação é stdlib + SQLite, como o resto do projeto.

## 2. Priorização

Não foi encontrada uma fórmula pronta aplicável: sistemas de *data stewardship* priorizam por
regra de negócio declarada, não por modelo. A decisão foi uma pontuação determinística com
fatores nomeados e visíveis na resposta (ver design), rejeitando:

- **ML/pontuação aprendida**: não há dados de treino nem rótulo de “revisão correta”;
- **prioridade opaca**: impossível auditar por que um item veio primeiro;
- **ordem cronológica**: obrigaria revisar 2023 propostas sem impacto.

## 3. Identidade documental e ingestão manual

| Referência | Padrão observado | Adoção |
|---|---|---|
| **Backdraft** (SPEC) | identidade do documento = SHA-256 dos bytes; URL é proveniência, nunca identidade; versões imutáveis | hash local como identidade do arquivo; URL original como procedência |
| **MemHouse** (arquitetura) | `DocumentVersion` imutável com hash, bytes e estado; ingestão de bytes grava blob endereçado por conteúdo e só cria versão quando o hash muda | `record_version` já fazia isso; a ingestão manual reusa |
| **Mari Kit** (documentação) | identidade estrutural `(source, external_id)` separada do `content_digest` | separação entre documento (URL/identificador) e versão (hash) |
| **PROV-O / proveniência** | origem, atividade, agente e instante explícitos | tabela `ingestoes_documentais` + evento `ingestao_manual` |

Rejeitado: tratar “usuário disse que é oficial” como confirmação; confiar na extensão do arquivo;
executar conteúdo incorporado.

## 4. Documentos bloqueados: alternativa legítima

Medições feitas nesta fase (leitura direta de `robots.txt`):

| Host | `robots.txt` | Consequência |
|---|---|---|
| `anexos.cdn.selecao.net.br` | `User-agent: *` / `Disallow: /` | 48 anexos do IBFC **não** podem ser baixados pelo coletor |
| `anexos-r2.selecao.net.br` | HTTP 404 (sem restrição) | já autorizado no projeto |
| `concursos.ibfc.org.br` | permite `/index/` e `/informacoes/`; bloqueia `/uploads/` | catálogo/detalhe são coletáveis; o site não espelha os PDFs |

Verificações de alternativa:

1. **Espelho no mesmo caminho**: os 35 links do CDN e os 13 do r2 no certame 485 têm slugs
   diferentes — **não há espelho** por caminho idêntico.
2. **Portal do órgão contratante**: pesquisa real encontrou a página oficial de editais do TJPE
   (`portal.tjpe.jus.br/web/concursos-e-selecoes/editais`) com o edital de abertura em PDF. É
   alternativa **legítima**, mas a identidade do documento (qual certame, qual ano) exige
   conferência humana — o mesmo título aparece em concursos diferentes. Por isso não há
   ingestão automática: a tela oferece a pista e a importação manual com procedência.
3. **Diário Oficial**: o DOU é fonte oficial já integrada, mas a busca por ato específico não é
   determinística por identificador; fica como pista de pesquisa humana.
4. **Importação manual**: implementada com hash local, assinatura, canal e estado de revisão.

Rejeitado explicitamente: proxy, *user-agent* alternativo, navegador para contornar bloqueio,
cache de terceiro (não oficial) e cópia por nome de arquivo sem conferência.

## 5. Referências consultadas

- Documentação: Talonic (Review Queue, Approval Queue), NORA/AKKO, Mari Kit, MemHouse,
  Backdraft SPEC, SODPUB, Ratify.
- Código do projeto: `document_store` (revisões/valores), `document_review`, `identity`,
  `association`, `ibfc_source`, `monitoring`, `document_discovery`.
- Dados reais: `propostas_campo`, `evidencias`, `revisoes_campo`, `valores_atuais`,
  `associacoes_documento`, `eventos_documentais`, `ciclos_fontes`.

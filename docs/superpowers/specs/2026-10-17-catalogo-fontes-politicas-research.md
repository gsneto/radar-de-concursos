# Pesquisa — Fase 29: fontes, licenças, custos e aquisição

Data das consultas: 2026-10-17. Nenhum código de terceiros foi copiado nesta fase.

## 1. Fontes de concursos e agregadores

| Fonte | Verificação real | Decisão |
|---|---|---|
| IN.gov.br / DOU | `leiturajornal?secao=do3` responde 200 (HTML); não há API pública documentada | já integrada; catálogo `dou-secao-3` |
| FGV, Quadrix, IBFC | catálogos HTML; IBFC mantém 48 anexos em CDN | já integradas |
| PCI Concursos | robots permite com restrições; MCP público | já integrada; conteúdo editorial não persistível |
| ConcursosNoBrasil | `robots.txt` 200: `Disallow: /wp-admin/`, sitemap público | catalogada; termos não verificados ⇒ persistência não verificada |
| Ache Concursos | `robots.txt` 200 com `Disallow` pontuais e `Allow: /` | catalogada; termos não verificados |
| JC Concursos (UOL) | `robots.txt` 200 `Allow: /` | catalogada; notícia = uso transitório |
| Qconcursos | `robots.txt` respondeu **403** | bloqueada; sem acesso nem licença |
| Questões de Concursos | `robots.txt` respondeu **403** | bloqueada |

Conclusão: agregador é pista, não prova. Nenhum deles foi integrado para persistência nesta fase.

## 2. APIs e repositórios de concursos (GitHub API, 2026-10-17)

| Repositório | Licença | Estrelas | Situação | Decisão |
|---|---|---|---|---|
| `Vinimartinsc/concursosPublicosAPI` | MIT | 33 | scraper de ConcursosNoBrasil; README diz “NÃO USAR EM PRODUÇÃO” | não integrar: licença do software ≠ direito ao conteúdo |
| `Jeiel0rbit/concursos-api-deno` | MIT | 6 | endpoint `concursos-api.deno.dev` respondeu **404**; dados do ConcursosNoBrasil | não integrar |
| `kauafernandomelo/api-concursos-publicos` | **ausente** | 0 | FastAPI + scraper do PCI | bloqueada: sem licença |
| `HenriqueNevB/api-concursos-publicos` | — | — | repositório **404** | não existe |

## 3. APIs de questões e provas

| Fonte | Verificação | Decisão |
|---|---|---|
| Quest API (`gontijogabriel/Quest-API`) | repositório público de documentação; **sem licença**; código em repositórios privados; modelo B2B com API key e billing | bloqueada; exige contrato/credencial — nenhuma assinatura foi feita |
| QAPI Otunac | busca no GitHub sem resultado relevante | não localizada |
| API das Questões | busca sem resultado relevante | não localizada |
| Qconcursos / Questões de Concursos | robots 403, conteúdo pago | bloqueadas |

Nenhum conteúdo educacional de terceiro foi importado. O módulo de estudos continua com questões
criadas pelo próprio usuário.

## 4. Dados abertos

| Fonte | Verificação | Decisão |
|---|---|---|
| Portal Brasileiro de Dados Abertos | API `dados.gov.br/dados/api/publico/conjuntos-dados` respondeu **401**; CKAN `/api/3/action/package_search` também 401 | `aguardando_credencial`; nenhuma conta criada |
| Conecta gov.br | catálogo HTML 200; cada API exige cadastro próprio | catalogada; sem integração |
| **IBGE Localidades** | `servicodados.ibge.gov.br/api/v1/localidades/municipios` 200, **5.570 municípios**, sem chave, dados abertos | **integrada** |

## 5. Padrões técnicos avaliados

| Padrão | Referência observada | Adoção |
|---|---|---|
| conector independente com capacidades declaradas | adaptadores de coleta (padrão comum em ETL) | interface `Connector` + registro |
| rate limit e orçamento antes da chamada | práticas de API gateway | `budget.check_call` com limites por execução |
| deduplicação por identidade + hash | Backdraft/MemHouse (fases anteriores) | reutilizado no fluxo documental |
| checkpoint e retomada | idem | `checkpoint_json` + `save_checkpoint` |
| circuit breaker / backoff | prática de clientes HTTP | backoff já aplicado no download (Fase 28); orçamento interrompe execução |
| proveniência e auditoria | PROV-O (Fase 28) | `fontes_revisoes` append-only + eventos |

Rejeitado: framework de catálogo (DataHub/OpenMetadata), filas externas, SDKs de provedor —
peso desproporcional para um app stdlib + SQLite.

## 6. Decisões de licença registradas

1. **MIT do scraper não licencia o dado.** `Vinimartinsc` e `Jeiel0rbit` são MIT, mas o conteúdo
   pertence ao ConcursosNoBrasil; ficaram como `persistencia_nao_verificada`/não implementadas.
2. **Sem licença = bloqueado.** `kauafernandomelo` e `Quest-API` não declaram licença.
3. **robots 403 = bloqueado.** Qconcursos e Questões de Concursos.
4. **Dados abertos oficiais** (IBGE) podem ser persistidos com atribuição e sem redistribuição
   do produto como base própria.

## 7. Referências

- `https://www.in.gov.br/leiturajornal?secao=do3`
- `https://concursosnobrasil.com/robots.txt`, `https://www.acheconcursos.com.br/robots.txt`,
  `https://www.jcconcursos.com.br/robots.txt`, `https://www.pciconcursos.com.br/robots.txt`,
  `https://www.qconcursos.com/robots.txt`, `https://www.questoesdeconcursos.com.br/robots.txt`
- `https://api.github.com/repos/{Vinimartinsc/concursosPublicosAPI,Jeiel0rbit/concursos-api-deno,kauafernandomelo/api-concursos-publicos,gontijogabriel/Quest-API}`
- `https://dados.gov.br/dados/api/publico/conjuntos-dados`, `https://www.gov.br/conecta/catalogo/apis`
- `https://servicodados.ibge.gov.br/api/v1/localidades/municipios`
